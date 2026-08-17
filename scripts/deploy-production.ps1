<#
.SYNOPSIS
    Orquestrador local de deploy controlado de producao do SmartPayBot (SPB-263).

.DESCRIPTION
    Substitui a sequencia manual de comandos SSH por um unico comando local.
    A chave SSH permanece inteiramente sob controle do OpenSSH do Windows
    (~/.ssh/config, ssh-agent, chave default) -- este script NUNCA le, copia
    ou aponta para uma chave privada especifica. Ele apenas invoca o binario
    `ssh` ja disponivel no sistema, exatamente como o operador faria manualmente.

    Fluxo: preflight local -> confirmacao humana -> pausa do Scheduled Task
    "SmartPayBot Collector" -> envio e execucao de
    scripts/deploy-production-remote.sh na VPS via stdin -> religa o
    Collector no estado original (mesmo em erro, via try/finally).

.PARAMETER DeployHost
    Destino SSH no formato usuario@host. Default: deploy@187.77.61.137

.PARAMETER AppDir
    Diretorio do clone de producao na VPS. Default:
    /home/deploy/apps/www.smartpaybot.com.br

.PARAMETER TargetSha
    SHA git completo (40 hex) a implantar. Se omitido, usa origin/main
    apos git fetch. Se informado, e validado como ancestral de origin/main.

.PARAMETER Yes
    Pula a confirmacao interativa "Implantar este SHA em producao? [s/N]".
    Use apenas em contextos ja supervisionados.

.PARAMETER DryRun
    Executa somente o preflight local (git, SHA, deteccao do Scheduled
    Task) e imprime o que seria feito. NAO desabilita o Collector, NAO
    conecta via SSH, NAO toca producao.

.PARAMETER RunCollectorAfter
    Apos um deploy SUCCESS, dispara manualmente uma rodada do Collector
    (somente se ele estava habilitado antes do deploy) e reporta o
    resultado. Nunca inicia uma segunda instancia se uma ja estiver
    em execucao.

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
$RemoteScriptPath = Join-Path $RepoRoot "scripts\deploy-production-remote.sh"
$LogDir = Join-Path $RepoRoot "logs\deploy"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogFile = Join-Path $LogDir "deploy-$Timestamp.log"

# Exit codes (documentados em docs/runbooks/deploy-producao.md):
#   0  = deploy concluido com sucesso (DEPLOY_STATUS=SUCCESS remoto)
#   1  = falha local de preflight, transporte SSH, ou DEPLOY_STATUS=FAILED remoto
#   2  = DEPLOY_STATUS=ROLLED_BACK remoto (rollback automatico executado)
#   3  = usuario recusou a confirmacao (nenhum deploy tentado)
#   4  = -DryRun concluido (informativo, nao e erro)

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
if ($DeployHost -notmatch '^[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+$') {
    Fail-Local "DeployHost em formato invalido: '$DeployHost' (esperado usuario@host)."
}
if ($AppDir -notmatch '^[A-Za-z0-9_./-]+$') {
    Fail-Local "AppDir contem caracteres nao permitidos: '$AppDir'."
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

if ($localMainSha -ne $originMainSha) {
    Fail-Local "main local ($localMainSha) diverge de origin/main ($originMainSha). Sincronize antes de tentar o deploy."
}
Write-Host "main local == origin/main ($localMainSha)"

if ($TargetSha -eq "") {
    $TargetSha = $originMainSha
    Write-Host "TargetSha nao informado -- usando origin/main."
}
else {
    git cat-file -e "$TargetSha^{commit}" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Fail-Local "TargetSha '$TargetSha' nao existe como commit apos fetch."
    }
    git merge-base --is-ancestor $TargetSha origin/main
    if ($LASTEXITCODE -ne 0) {
        Fail-Local "TargetSha '$TargetSha' nao e ancestral de origin/main."
    }
}
Write-Host "TARGET_SHA=$TargetSha"

if (-not (Test-Path $RemoteScriptPath)) {
    Fail-Local "script remoto nao encontrado: $RemoteScriptPath"
}
Write-Host "script remoto: $RemoteScriptPath"

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
    exit 4
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

try {
    Write-Section "4. PAUSANDO O COLLECTOR"
    if ($originalState -ne "Disabled") {
        Disable-ScheduledTask -TaskName $TaskName | Out-Null
        Write-Host "Collector desabilitado temporariamente."
    }
    else {
        Write-Host "Collector ja estava Disabled -- mantendo como esta."
    }

    Write-Section "5. EXECUTANDO DEPLOY REMOTO"
    Start-Transcript -Path $LogFile -Append | Out-Null
    try {
        $remoteCommand = "bash -s -- $TargetSha $AppDir"
        Write-Host "Comando remoto: ssh $DeployHost `"$remoteCommand`""
        $remoteOutputLines = Get-Content -Raw -Path $RemoteScriptPath | & ssh $DeployHost $remoteCommand
        $deployExitCode = $LASTEXITCODE
    }
    finally {
        Stop-Transcript | Out-Null
    }

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
        2 { Write-Host "Deploy foi REVERTIDO automaticamente (rollback) apos o restart." -ForegroundColor Yellow }
        default { Write-Host "Codigo de saida remoto inesperado: $deployExitCode" -ForegroundColor Red }
    }

    if ($deployExitCode -eq 0 -and $RunCollectorAfter -and $originalState -ne "Disabled") {
        Write-Section "7. RODADA MANUAL DO COLLECTOR (pos-deploy)"
        $current = Get-ScheduledTask -TaskName $TaskName
        if ($current.State -eq "Running") {
            Write-Host "AVISO: Collector ja em execucao -- nao disparando rodada manual duplicada." -ForegroundColor Yellow
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
            $info = Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo
            Write-Host "LastTaskResult=$($info.LastTaskResult)"
            $logPath = Join-Path $RepoRoot "logs\collector.log"
            if (Test-Path $logPath) {
                Write-Host "--- ultimas linhas de logs\collector.log ---"
                Get-Content -Path $logPath -Tail 15
            }
        }
    }
}
finally {
    Write-Section "8. RESTAURANDO ESTADO DO COLLECTOR"
    if ($originalState -ne "Disabled") {
        Enable-ScheduledTask -TaskName $TaskName | Out-Null
        Write-Host "Collector religado (estado original era '$originalState')."
    }
    else {
        Write-Host "Collector permanece Disabled (estado original preservado)."
    }
    $finalState = (Get-ScheduledTask -TaskName $TaskName).State
    Write-Host "State final do Collector: $finalState"
}

exit $deployExitCode
