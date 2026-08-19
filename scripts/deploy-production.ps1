<#
.SYNOPSIS
    Orquestrador local de deploy controlado de producao do SmartPayBot (SPB-263).

.DESCRIPTION
    Substitui a sequencia manual de comandos SSH por um unico comando local.
    A chave SSH permanece inteiramente sob controle do OpenSSH do Windows
    (~/.ssh/config, ssh-agent, chave default) -- este script NUNCA le, copia
    ou aponta para uma chave privada especifica. Ele apenas invoca o binario
    `ssh` ja disponivel no sistema, exatamente como o operador faria manualmente.

    TARGET_SHA e amarrado criptograficamente ao codigo de deploy executado:
    o conteudo de scripts/deploy-production-remote.sh enviado via SSH e
    obtido de `git show TARGET_SHA:scripts/deploy-production-remote.sh`,
    nunca lido do filesystem local. Isso exige working tree local
    completamente limpo (git status --porcelain vazio) antes de prosseguir.

    Fluxo: preflight local -> confirmacao humana -> pausa do Scheduled Task
    "SmartPayBot Collector" -> envio e execucao do script remoto amarrado
    ao TARGET_SHA na VPS -> religa o Collector no estado original (mesmo em
    erro, via try/finally) -> opcionalmente dispara uma rodada manual do
    Collector, SOMENTE depois de o Collector ja estar restaurado.

.PARAMETER DeployHost
    Destino SSH no formato usuario@host. Default: deploy@187.77.61.137
    Nem usuario nem host podem comecar com "-" (evita disfarcar uma opcao
    do ssh como se fosse o destino).

.PARAMETER AppDir
    Diretorio do clone de producao na VPS. Esta versao do script suporta
    exatamente um diretorio de producao:
    /home/deploy/apps/www.smartpaybot.com.br
    Qualquer valor diferente informado via -AppDir falha imediatamente.

.PARAMETER TargetSha
    SHA git completo (40 hex minusculos) a implantar. Se omitido, usa
    origin/main apos git fetch. Se informado, DEVE ser exatamente igual a
    origin/main -- esta versao nao implanta nenhum outro commit.

.PARAMETER Yes
    Pula a confirmacao interativa "Implantar este SHA em producao? [s/N]".
    Use apenas em contextos ja supervisionados.

.NOTES
    Elevacao: quando o Collector precisa ser pausado (State != Disabled) e
    o deploy NAO e -DryRun, este script exige um PowerShell "Executar como
    Administrador" (Disable-ScheduledTask/Enable-ScheduledTask exigem
    elevacao nesta maquina). A falta de elevacao aborta ANTES da
    confirmacao humana e ANTES de qualquer SSH, com exit local 1.
    -DryRun nunca exige elevacao (e somente leitura).

.PARAMETER DryRun
    Executa somente o preflight local (git, SHA, deteccao do Scheduled
    Task). NAO desabilita o Collector, NAO conecta via SSH, NAO toca
    producao.

.PARAMETER RunCollectorAfter
    Apos um deploy SUCCESS E o Collector ja ter sido CONFIRMADAMENTE
    restaurado ao estado original, dispara manualmente uma rodada (somente
    se ele estava habilitado antes do deploy) e reporta o resultado.
    Funciona como um smoke gate solicitado pelo operador: se
    LastTaskResult != 0, o script termina com exit 8
    (POST_DEPLOY_COLLECTOR_FAILED), sem alterar o DEPLOY_STATUS remoto.
    Nunca inicia uma segunda instancia se uma ja estiver em execucao.
    Nunca imprime o conteudo bruto de logs\collector.log -- somente
    campos seguros do proprio Scheduled Task (State, LastRunTime,
    LastTaskResult).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\deploy-production.ps1 -DryRun

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\deploy-production.ps1
#>

[CmdletBinding()]
param(
    [string]$DeployHost = "deploy@187.77.61.137",
    [string]$AppDir = "/home/deploy/apps/www.smartpaybot.com.br",
    [string]$TargetSha = "",
    [switch]$Yes,
    [switch]$DryRun,
    [switch]$RunCollectorAfter
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$TaskName = "SmartPayBot Collector"
$RemoteScriptRelPath = "scripts/deploy-production-remote.sh"
$ExpectedAppDir = "/home/deploy/apps/www.smartpaybot.com.br"
$LogDir = Join-Path $RepoRoot "logs\deploy"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogFile = Join-Path $LogDir "deploy-$Timestamp.log"

# Exit codes locais (documentados em docs/runbooks/deploy-producao.md):
#
#   Propagados diretamente do script remoto quando a conexao SSH acontece:
#     0 = DEPLOY_STATUS=SUCCESS
#     1 = DEPLOY_STATUS=FAILED           (abortado antes do restart)
#     2 = DEPLOY_STATUS=ROLLED_BACK      (rollback pos-restart validado)
#     4 = DEPLOY_STATUS=RECOVERY_FAILED  (reversao pre-restart NAO confirmada -- inspecionar a VPS manualmente)
#     5 = DEPLOY_STATUS=ROLLBACK_FAILED  (rollback pos-restart NAO totalmente validado -- inspecionar a VPS manualmente)
#
#   Exclusivos deste script local (a conexao SSH nunca chega a acontecer):
#     3 = operador recusou a confirmacao
#     6 = -DryRun concluido (informativo, nao e erro)
#     1 = tambem usado para qualquer falha LOCAL de preflight/transporte (reaproveita o mesmo significado de "FAILED antes de tocar producao")
#
#   Exclusivos deste script local, DEPOIS de uma tentativa de deploy remoto
#   (a conexao SSH ja aconteceu; sobrescrevem o codigo remoto quando ocorrem,
#   pois passam a ser a falha mais recente e mais urgente a resolver):
#     7 = COLLECTOR_RESTORE_FAILED      (o Collector nao pode ser confirmado
#                                         como restaurado ao estado original
#                                         apos o deploy -- o DEPLOY_STATUS
#                                         remoto pode ter sido SUCCESS, mas
#                                         isso NAO significa sucesso
#                                         operacional total; correcao manual
#                                         necessaria na Scheduled Task)
#     8 = POST_DEPLOY_COLLECTOR_FAILED  (somente quando -RunCollectorAfter
#                                         foi solicitado: a rodada manual
#                                         pos-deploy terminou com
#                                         LastTaskResult != 0; DEPLOY_STATUS
#                                         remoto nao e alterado por isso --
#                                         e uma falha do smoke gate local
#                                         solicitado pelo operador)

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "=== $Title ===" -ForegroundColor Cyan
}

function Fail-Local {
    param([string]$Message)
    Write-Host "ABORT (local): $Message" -ForegroundColor Red
    exit 1
}

# ── validacoes defensivas de parametros (secao 24 -- seguranca) ──────────
# Usuario deve comecar com alfanumerico/underscore; host deve comecar com
# alfanumerico. Nenhum dos dois pode comecar com "-" (evita disfarcar uma
# opcao do ssh como se fosse usuario/host).
if ($DeployHost -cnotmatch '^[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9_.-]*$') {
    Fail-Local "DeployHost em formato invalido ou potencialmente perigoso: '$DeployHost' (esperado usuario@host, sem iniciar com '-')."
}
if ($AppDir -ne $ExpectedAppDir) {
    Fail-Local "AppDir informado ('$AppDir') diferente do unico diretorio de producao suportado nesta versao ('$ExpectedAppDir')."
}
if ($TargetSha -ne "" -and $TargetSha -cnotmatch '^[0-9a-f]{40}$') {
    Fail-Local "TargetSha invalido: '$TargetSha' (esperado SHA git completo de 40 caracteres hex minusculos)."
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Write-Section "1. PREFLIGHT LOCAL"

try {
    git rev-parse --is-inside-work-tree | Out-Null
}
catch {
    Fail-Local "diretorio atual nao e um repositorio git: $RepoRoot"
}

$currentBranch = (git branch --show-current).Trim()
Write-Host "branch atual = $currentBranch"
if ($currentBranch -ne "main") {
    Fail-Local "branch atual e '$currentBranch', mas o deploy so pode ser disparado a partir de 'main'. Execute 'git switch main' primeiro."
}

$porcelain = git status --porcelain
if ($porcelain) {
    Write-Host ($porcelain -join "`n") -ForegroundColor Red
    Fail-Local "working tree local NAO esta completamente limpo (git status --porcelain retornou saida). E preciso estar limpo para amarrar TARGET_SHA ao conteudo exato do script remoto."
}
Write-Host "working tree local completamente limpo (git status --porcelain vazio)."

git fetch origin
if ($LASTEXITCODE -ne 0) {
    Fail-Local "git fetch origin falhou."
}

$originMainSha = (git rev-parse origin/main).Trim()
Write-Host "origin/main = $originMainSha"

$localMainSha = ""
try {
    $localMainSha = (git rev-parse main 2>$null).Trim()
}
catch {
    Fail-Local "branch local 'main' nao encontrada."
}

if ($localMainSha -cne $originMainSha) {
    Fail-Local "main local ($localMainSha) diverge de origin/main ($originMainSha). Sincronize antes de tentar o deploy."
}
Write-Host "main local == origin/main ($localMainSha)"

if ($TargetSha -eq "") {
    $TargetSha = $originMainSha
    Write-Host "TargetSha nao informado -- usando origin/main."
}
elseif ($TargetSha -cne $originMainSha) {
    Fail-Local "TargetSha informado ('$TargetSha') difere de origin/main ('$originMainSha'). Esta versao do deploy exige TARGET_SHA == origin/main exatamente."
}
Write-Host "TARGET_SHA=$TargetSha"

# ── amarrar o script remoto ao TARGET_SHA via git show (nunca do filesystem) ──
$remoteScriptLines = @(git show "${TargetSha}:${RemoteScriptRelPath}" 2>$null)
if ($LASTEXITCODE -ne 0 -or $remoteScriptLines.Count -eq 0) {
    Fail-Local "git show ${TargetSha}:${RemoteScriptRelPath} falhou -- nao e seguro prosseguir sem o conteudo exato do script amarrado ao commit."
}
$remoteScriptBlob = $remoteScriptLines -join "`n"
Write-Host "script remoto obtido de ${TargetSha}:${RemoteScriptRelPath} ($($remoteScriptLines.Count) linhas)."

Write-Section "2. SCHEDULED TASK -- SmartPayBot Collector"

$task = $null
try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
}
catch {
    Fail-Local "Scheduled Task '$TaskName' nao encontrada nesta maquina."
}

$taskInfo = $task | Get-ScheduledTaskInfo
Write-Host "State=$($task.State)"
Write-Host "LastRunTime=$($taskInfo.LastRunTime)"
Write-Host "LastTaskResult=$($taskInfo.LastTaskResult)"
Write-Host "NextRunTime=$($taskInfo.NextRunTime)"

$originalState = $task.State

if ($originalState -eq "Running") {
    Write-Host "Collector em execucao -- aguardando terminar antes de prosseguir (timeout 120s)..." -ForegroundColor Yellow
    $waited = 0
    $maxWait = 120
    while ($true) {
        Start-Sleep -Seconds 5
        $waited += 5
        $task = Get-ScheduledTask -TaskName $TaskName
        if ($task.State -ne "Running") {
            $originalState = $task.State
            break
        }
        if ($waited -ge $maxWait) {
            Fail-Local "Collector ainda em execucao apos ${maxWait}s. Abortando sem tocar em nada (nenhum processo foi morto)."
        }
    }
    Write-Host "Collector nao esta mais em execucao (State=$originalState)."
}

Write-Section "3. RESUMO / CONFIRMACAO"

Write-Host "Host de deploy   : $DeployHost"
Write-Host "Diretorio remoto : $AppDir"
Write-Host "Branch local     : main"
Write-Host "Target SHA       : $TargetSha"
Write-Host "Collector (State atual): $originalState"
Write-Host "URL de producao  : https://smartpaybot.com.br/"
Write-Host "Log deste deploy : $LogFile"

if ($DryRun) {
    Write-Host ""
    Write-Host "-DryRun: preflight concluido. NAO foi feita conexao SSH, NAO houve alteracao no Scheduled Task, NAO houve deploy." -ForegroundColor Yellow
    "DRY_RUN=true" | Out-File -FilePath $LogFile -Encoding utf8
    "TARGET_SHA=$TargetSha" | Out-File -FilePath $LogFile -Append -Encoding utf8
    "ORIGINAL_COLLECTOR_STATE=$originalState" | Out-File -FilePath $LogFile -Append -Encoding utf8
    exit 6
}

# ── gate de elevacao: exigido somente quando o deploy real precisa pausar
# o Collector (Disable-ScheduledTask/Enable-ScheduledTask exigem admin
# nesta maquina). Roda ANTES da confirmacao humana e ANTES de qualquer
# Disable-ScheduledTask -- nenhum prompt, nenhum SSH, se nao elevado.
if ($originalState -ne "Disabled") {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    $isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Fail-Local "o Collector esta '$originalState' e precisa ser pausado durante o deploy, mas este PowerShell nao esta elevado. Execute o PowerShell como Administrador e tente novamente."
    }
    Write-Host "PowerShell elevado confirmado (necessario pois o Collector ('$originalState') precisa ser pausado)."
}

if (-not $Yes) {
    $answer = Read-Host "Implantar este SHA em producao? [s/N]"
    if ($answer -ne "s" -and $answer -ne "S" -and $answer -ne "sim" -and $answer -ne "Sim") {
        Write-Host "Deploy cancelado pelo operador. Nenhuma alteracao foi feita." -ForegroundColor Yellow
        exit 3
    }
}

# ── a partir daqui: pausa do Collector com garantia de restauracao ───────
$deployExitCode = 1
$remoteOutputLines = @()
$collectorRestoreFailed = $false
$collectorDisabledByDeploy = $false

try {
    Write-Section "4. PAUSANDO O COLLECTOR"
    if ($originalState -ne "Disabled") {
        try {
            Disable-ScheduledTask -TaskName $TaskName -ErrorAction Stop | Out-Null
            $collectorDisabledByDeploy = $true
            Write-Host "Collector desabilitado temporariamente."
        }
        catch {
            Add-Content -Path $LogFile -Value "COLLECTOR_DISABLE_FAILED=true"
            Add-Content -Path $LogFile -Value "COLLECTOR_DISABLE_ERROR=$($_.Exception.Message)"
            Fail-Local "Disable-ScheduledTask falhou para '$TaskName': $($_.Exception.Message). Nenhuma conexao SSH sera feita -- o script nao confirmou que o Collector foi pausado, entao nao tentara religa-lo."
        }
    }
    else {
        Write-Host "Collector ja estava Disabled -- mantendo como esta."
    }

    Write-Section "5. EXECUTANDO DEPLOY REMOTO"
    Start-Transcript -Path $LogFile -Append | Out-Null
    try {
        $remoteCommand = "bash -s -- $TargetSha $AppDir"
        # BatchMode=yes + ConnectTimeout=15: falha rapido se a chave nao
        # funcionar, nunca espera senha. StrictHostKeyChecking=yes: a
        # fingerprint continua sendo validada pelo known_hosts normal do
        # Windows -- nunca UserKnownHostsFile=/dev/null nem checking=no.
        $sshArgs = @("-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=yes", $DeployHost, $remoteCommand)
        Write-Host "Comando remoto: ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=yes $DeployHost `"$remoteCommand`""
        $remoteOutputLines = $remoteScriptBlob | & ssh @sshArgs
        $deployExitCode = $LASTEXITCODE
    }
    finally {
        Stop-Transcript | Out-Null
    }

    # Persistencia explicita da saida remota no log -- Stop-Transcript ja
    # fechou o arquivo antes de imprimirmos o resultado, entao anexamos
    # diretamente em vez de depender do transcript para essas linhas.
    Add-Content -Path $LogFile -Value ""
    Add-Content -Path $LogFile -Value "--- remote stdout (persistido explicitamente) ---"
    if ($remoteOutputLines) {
        $remoteOutputLines | Add-Content -Path $LogFile
    }
    Add-Content -Path $LogFile -Value ""
    Add-Content -Path $LogFile -Value "LOCAL_TARGET_SHA=$TargetSha"
    Add-Content -Path $LogFile -Value "LOCAL_DEPLOY_EXIT_CODE=$deployExitCode"

    Write-Host ""
    Write-Host "--- saida remota (stdout) ---"
    $remoteOutputLines | ForEach-Object { Write-Host $_ }

    Write-Section "6. RESULTADO"
    $status = ($remoteOutputLines | Where-Object { $_ -match '^DEPLOY_STATUS=' })
    if ($status) {
        Write-Host $status
    }
    else {
        Write-Host "AVISO: nenhuma linha DEPLOY_STATUS= recebida -- tratar como falha de transporte." -ForegroundColor Red
        if ($deployExitCode -eq 0) { $deployExitCode = 1 }
    }

    switch ($deployExitCode) {
        0 { Write-Host "Deploy concluido com SUCESSO." -ForegroundColor Green }
        1 { Write-Host "Deploy FALHOU antes do restart -- servico antigo continua rodando." -ForegroundColor Red }
        2 { Write-Host "Deploy foi REVERTIDO automaticamente (rollback validado) apos o restart." -ForegroundColor Yellow }
        4 { Write-Host "RECOVERY_FAILED: a reversao pre-restart NAO PODE ser confirmada. INSPECIONAR A VPS MANUALMENTE AGORA." -ForegroundColor Red }
        5 { Write-Host "ROLLBACK_FAILED: o rollback pos-restart NAO PODE ser totalmente validado. INSPECIONAR A VPS MANUALMENTE AGORA." -ForegroundColor Red }
        default { Write-Host "Codigo de saida remoto inesperado: $deployExitCode" -ForegroundColor Red }
    }
}
finally {
    Write-Section "7. RESTAURANDO ESTADO DO COLLECTOR"
    if ($collectorDisabledByDeploy) {
        try {
            Enable-ScheduledTask -TaskName $TaskName -ErrorAction Stop | Out-Null
            Write-Host "Collector religado (estado original era '$originalState')."
        }
        catch {
            Write-Host "ERRO ao tentar religar o Collector: $($_.Exception.Message)" -ForegroundColor Red
            $collectorRestoreFailed = $true
        }
    }
    elseif ($originalState -eq "Disabled") {
        Write-Host "Collector permanece Disabled (estado original preservado)."
    }
    else {
        # originalState != Disabled mas $collectorDisabledByDeploy == $false:
        # o script nunca confirmou ter desabilitado a task (ex.: Disable
        # falhou antes). Nao ha nada para restaurar -- tentar Enable aqui
        # seria alterar um estado que este deploy nao mudou.
        Write-Host "Collector nao foi desabilitado por este deploy -- nenhuma restauracao necessaria."
    }

    $finalState = $null
    try {
        $finalState = (Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop).State
        Write-Host "State final do Collector: $finalState"
    }
    catch {
        Write-Host "ERRO ao consultar estado final do Collector: $($_.Exception.Message)" -ForegroundColor Red
        $collectorRestoreFailed = $true
    }

    if ($collectorDisabledByDeploy -and $finalState -eq "Disabled") {
        Write-Host "FALHA OPERACIONAL: o Collector deveria ter sido religado mas continua Disabled. Verificar manualmente." -ForegroundColor Red
        $collectorRestoreFailed = $true
    }
}

if ($collectorRestoreFailed) {
    Write-Host ""
    Write-Host "COLLECTOR_RESTORE_FAILED: a restauracao operacional do Collector NAO PODE ser confirmada." -ForegroundColor Red
    if ($status) {
        Write-Host "O deploy remoto pode ter terminado como '$status', mas isso NAO significa sucesso operacional total -- a task '$TaskName' precisa ser verificada/religada manualmente agora." -ForegroundColor Red
    }
    Write-Host "Acao manual: 'Get-ScheduledTask -TaskName `"$TaskName`"' e, se necessario, 'Enable-ScheduledTask -TaskName `"$TaskName`"'." -ForegroundColor Red
    Add-Content -Path $LogFile -Value "COLLECTOR_RESTORE_FAILED=true"
    Add-Content -Path $LogFile -Value "LOCAL_DEPLOY_EXIT_CODE_BEFORE_COLLECTOR_CHECK=$deployExitCode"
    exit 7
}

# ── rodada manual do Collector, SOMENTE depois de confirmado restaurado (fora do try/finally) ──
if ($deployExitCode -eq 0 -and $RunCollectorAfter -and $originalState -ne "Disabled") {
    Write-Section "8. RODADA MANUAL DO COLLECTOR (pos-deploy, com o Collector ja restaurado)"
    $current = Get-ScheduledTask -TaskName $TaskName
    if ($current.State -eq "Running") {
        Write-Host "Collector ja em execucao (ciclo normal) -- aguardando essa execucao terminar em vez de disparar outra." -ForegroundColor Yellow
        $waited = 0
        $maxWait = 300
        while ($true) {
            Start-Sleep -Seconds 5
            $waited += 5
            $t = Get-ScheduledTask -TaskName $TaskName
            if ($t.State -ne "Running") { break }
            if ($waited -ge $maxWait) {
                Write-Host "AVISO: execucao em andamento ainda nao terminou apos ${maxWait}s -- nao aguardando mais." -ForegroundColor Yellow
                break
            }
        }
    }
    else {
        Start-ScheduledTask -TaskName $TaskName
        $waited = 0
        $maxWait = 300
        while ($true) {
            Start-Sleep -Seconds 5
            $waited += 5
            $t = Get-ScheduledTask -TaskName $TaskName
            if ($t.State -ne "Running") { break }
            if ($waited -ge $maxWait) {
                Write-Host "AVISO: rodada manual do Collector ainda em execucao apos ${maxWait}s -- nao aguardando mais." -ForegroundColor Yellow
                break
            }
        }
    }
    # Somente dados seguros do proprio Scheduled Task -- nunca o conteudo
    # bruto de logs\collector.log, que pode registrar corpo de resposta
    # HTTP de erro (titulos, JSON de erro, etc.).
    $info = Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo
    Write-Host "State=$((Get-ScheduledTask -TaskName $TaskName).State)"
    Write-Host "LastRunTime=$($info.LastRunTime)"
    Write-Host "LastTaskResult=$($info.LastTaskResult)"

    if ($info.LastTaskResult -ne 0) {
        Write-Host ""
        Write-Host "POST_DEPLOY_COLLECTOR_FAILED: a rodada manual do Collector solicitada via -RunCollectorAfter terminou com LastTaskResult=$($info.LastTaskResult) (esperado 0)." -ForegroundColor Red
        Write-Host "O DEPLOY_STATUS remoto nao e alterado por isso -- esta e uma falha do smoke gate solicitado pelo operador, reportada separadamente." -ForegroundColor Red
        Add-Content -Path $LogFile -Value "POST_DEPLOY_COLLECTOR_FAILED=true"
        Add-Content -Path $LogFile -Value "POST_DEPLOY_COLLECTOR_LAST_TASK_RESULT=$($info.LastTaskResult)"
        exit 8
    }
    Write-Host "Rodada manual do Collector concluida com sucesso (LastTaskResult=0)."
}

exit $deployExitCode
