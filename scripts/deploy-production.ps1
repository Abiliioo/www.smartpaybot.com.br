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

.PARAMETER BuildReactDist
    Roda npm.cmd run typecheck/build em frontend, valida app/static/dist,
    empacota o dist em um .tar.gz temporario e envia esse artefato
    junto com o deploy. Sem este parametro, o comportamento legado do
    deploy permanece inalterado e nenhum asset React e enviado.

.PARAMETER ValidateReactDistOnly
    Executa somente o gate local do React dist para PR/review:
    typecheck, build, validacao de manifest/assets, empacotamento .tar.gz
    temporario e limpeza. Nao exige branch main, nao consulta Scheduled
    Task, nao abre SSH e nao faz deploy.

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

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\deploy-production.ps1 -BuildReactDist

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\deploy-production.ps1 -ValidateReactDistOnly
#>

[CmdletBinding()]
param(
    [string]$DeployHost = "deploy@187.77.61.137",
    [string]$AppDir = "/home/deploy/apps/www.smartpaybot.com.br",
    [string]$TargetSha = "",
    [switch]$Yes,
    [switch]$DryRun,
    [switch]$BuildReactDist,
    [switch]$ValidateReactDistOnly,
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
    if (Get-Variable -Name reactDistArtifact -Scope Script -ErrorAction SilentlyContinue) {
        if ($script:reactDistArtifact) {
            Remove-Item -LiteralPath $script:reactDistArtifact.TempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "ABORT (local): $Message" -ForegroundColor Red
    exit 1
}

function ConvertTo-LfText {
    param([string]$Text)
    return (($Text -replace "`r`n", "`n") -replace "`r", "`n")
}

function Test-ReactDistRelativePath {
    param([string]$PathValue)
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        Fail-Local "manifest React contem caminho vazio."
    }
    if ([System.IO.Path]::IsPathRooted($PathValue) -or $PathValue -match '^[A-Za-z]:') {
        Fail-Local "manifest React contem caminho absoluto suspeito: '$PathValue'."
    }
    $normalized = $PathValue -replace '\\', '/'
    $segments = $normalized.Split('/')
    if ($segments -contains '..' -or $normalized.StartsWith('/')) {
        Fail-Local "manifest React contem caminho que escapa de dist: '$PathValue'."
    }
}

function Test-ReactDistFile {
    param(
        [string]$DistRoot,
        [string]$RelativePath,
        [string]$Label
    )
    Test-ReactDistRelativePath $RelativePath
    $fullPath = Join-Path $DistRoot $RelativePath
    $resolvedDist = [System.IO.Path]::GetFullPath($DistRoot)
    $resolvedFile = [System.IO.Path]::GetFullPath($fullPath)
    if (-not $resolvedFile.StartsWith($resolvedDist, [System.StringComparison]::OrdinalIgnoreCase)) {
        Fail-Local "${Label} aponta para fora de app/static/dist: '$RelativePath'."
    }
    if (-not (Test-Path -LiteralPath $resolvedFile -PathType Leaf)) {
        Fail-Local "${Label} referenciado no manifest nao existe: '$RelativePath'."
    }
}

function Test-ReactDist {
    param([string]$DistRoot)
    if (-not (Test-Path -LiteralPath $DistRoot -PathType Container)) {
        Fail-Local "React dist nao encontrado em '$DistRoot'. Rode com -BuildReactDist para gerar antes do deploy."
    }

    $manifestPath = Join-Path $DistRoot ".vite\manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        Fail-Local "manifest React nao encontrado: $manifestPath"
    }

    try {
        $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    }
    catch {
        Fail-Local "manifest React invalido: $($_.Exception.Message)"
    }

    $entries = @($manifest.PSObject.Properties)
    if (-not $entries) {
        Fail-Local "manifest React vazio."
    }

    $entry = $entries | Where-Object { $_.Name -eq "index.html" } | Select-Object -First 1
    if (-not $entry) {
        $entry = $entries | Where-Object { $_.Value.PSObject.Properties.Name -contains "isEntry" -and $_.Value.isEntry -eq $true } | Select-Object -First 1
    }
    if (-not $entry) {
        Fail-Local "manifest React nao contem index.html nem entrada isEntry=true."
    }

    if (-not ($entry.Value.PSObject.Properties.Name -contains "file")) {
        Fail-Local "entrada principal do manifest React nao contem 'file'."
    }
    Test-ReactDistFile -DistRoot $DistRoot -RelativePath $entry.Value.file -Label "JS principal React"

    if ($entry.Value.PSObject.Properties.Name -contains "css") {
        foreach ($cssPath in @($entry.Value.css)) {
            Test-ReactDistFile -DistRoot $DistRoot -RelativePath $cssPath -Label "CSS React"
        }
    }

    Write-Host "React dist validado: manifest, JS principal e CSS referenciado existem e permanecem dentro de app/static/dist."
}

function Invoke-ReactDistBuild {
    Write-Section "2. REACT DIST LOCAL"
    $frontendDir = Join-Path $RepoRoot "frontend"
    $distRoot = Join-Path $RepoRoot "app\static\dist"
    if (-not (Test-Path -LiteralPath $frontendDir -PathType Container)) {
        Fail-Local "diretorio frontend nao encontrado: $frontendDir"
    }

    Push-Location $frontendDir
    try {
        & npm.cmd run typecheck
        if ($LASTEXITCODE -ne 0) { Fail-Local "npm.cmd run typecheck falhou." }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { Fail-Local "npm.cmd run build falhou." }
    }
    finally {
        Pop-Location
    }

    Test-ReactDist -DistRoot $distRoot
    Write-Host "REACT_DIST_ROOT=$distRoot"
}

function New-ReactDistArtifact {
    param([string]$DistRoot)
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("smartpaybot-react-dist-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    $archivePath = Join-Path $tempRoot "react-dist.tar.gz"

    & tar -czf $archivePath -C $DistRoot .
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        Fail-Local "falha ao empacotar React dist com tar."
    }

    $listing = & tar -tzf $archivePath
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        Fail-Local "falha ao validar listagem do artefato React dist."
    }
    if (-not ($listing | Where-Object { $_ -eq "./.vite/manifest.json" -or $_ -eq ".vite/manifest.json" })) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        Fail-Local "artefato React dist nao contem .vite/manifest.json."
    }

    Write-Host "Artefato React dist criado em diretorio temporario: $archivePath"
    return [pscustomobject]@{ TempRoot = $tempRoot; ArchivePath = $archivePath }
}

if ($ValidateReactDistOnly) {
    $script:reactDistArtifact = $null
    Invoke-ReactDistBuild
    $reactDistRoot = Join-Path $RepoRoot "app\static\dist"
    $script:reactDistArtifact = New-ReactDistArtifact -DistRoot $reactDistRoot
    Remove-Item -LiteralPath $script:reactDistArtifact.TempRoot -Recurse -Force -ErrorAction SilentlyContinue
    $script:reactDistArtifact = $null
    Write-Host "REACT_DIST_LOCAL_VALIDATION=PASS"
    exit 0
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
# Captura os bytes CRUS do stdout de `git show` via Process + MemoryStream --
# nunca via `@(git show ...)` (array de linhas, perde terminadores de linha),
# nunca via `-join` do PowerShell (reconstroi LF so ENTRE linhas, perdendo o
# newline final do blob) e nunca via Encoding.GetBytes() sobre uma string ja
# passada pelo pipeline textual do PowerShell (que pode alterar caracteres
# Unicode presentes nos comentarios do script). O objetivo e byte-identidade
# total com o blob Git, LF final incluso -- validado por comparacao de
# SHA-256 contra `git cat-file blob <BLOB_SHA>` (fix/deploy-ssh-stdin-transport).
$gitShowPsi = New-Object System.Diagnostics.ProcessStartInfo
$gitShowPsi.FileName = "git"
# TargetSha ja foi validado (40 hex minusculos) e RemoteScriptRelPath e uma
# constante do proprio script -- nenhum dos dois vem de entrada nao confiavel.
$gitShowPsi.Arguments = "show `"${TargetSha}:${RemoteScriptRelPath}`""
$gitShowPsi.UseShellExecute = $false
$gitShowPsi.RedirectStandardOutput = $true
$gitShowPsi.RedirectStandardError = $true
$gitShowPsi.CreateNoWindow = $true

$gitShowProc = [System.Diagnostics.Process]::Start($gitShowPsi)
$remoteScriptMemStream = New-Object System.IO.MemoryStream
$gitShowProc.StandardOutput.BaseStream.CopyTo($remoteScriptMemStream)
# stderr e lido apenas como texto de diagnostico -- nunca compoe o script.
$gitShowStderr = $gitShowProc.StandardError.ReadToEnd()
$gitShowProc.WaitForExit()

$remoteScriptBytes = $remoteScriptMemStream.ToArray()
if ($gitShowProc.ExitCode -ne 0 -or $remoteScriptBytes.Length -eq 0) {
    Fail-Local "git show ${TargetSha}:${RemoteScriptRelPath} falhou (exit=$($gitShowProc.ExitCode)) -- nao e seguro prosseguir sem o conteudo exato do script amarrado ao commit. $gitShowStderr"
}
Write-Host "script remoto obtido de ${TargetSha}:${RemoteScriptRelPath} ($($remoteScriptBytes.Length) bytes)."

# ── Base64 sobre os bytes crus (transporte byte-safe) ────────────────────
# Windows PowerShell 5.1 injeta um BOM UTF-8 (EF BB BF) no INICIO e um CRLF
# extra no FIM de qualquer string enviada via pipeline ("$texto | & exe") a
# um processo nativo com stdin redirecionado -- confirmado por reproducao
# isolada (fix/deploy-ssh-stdin-transport): a ultima linha do script remoto
# chegava como "exit 0\r", e bash rejeita "0\r" como argumento numerico de
# exit ("numeric argument required", exit code 2), mascarando um
# DEPLOY_STATUS=SUCCESS remoto como um falso ROLLED_BACK local. Converter
# para Base64 (alfabeto ASCII puro) ANTES do pipeline faz o BOM/CRLF
# espurios do transporte carem fora do alfabeto Base64, descartados pelo
# `base64 --decode --ignore-garbage` do lado remoto.
$remoteScriptBase64 = [Convert]::ToBase64String($remoteScriptBytes)
$reactDistArtifact = $null
$reactDistArtifactBase64 = ""
if ($BuildReactDist) {
    Invoke-ReactDistBuild
    $reactDistRoot = Join-Path $RepoRoot "app\static\dist"
    $reactDistArtifact = New-ReactDistArtifact -DistRoot $reactDistRoot
    $reactDistArtifactBytes = [System.IO.File]::ReadAllBytes($reactDistArtifact.ArchivePath)
    $reactDistArtifactBase64 = [Convert]::ToBase64String($reactDistArtifactBytes)
    Write-Host "Artefato React dist pronto ($($reactDistArtifactBytes.Length) bytes)."
}

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
Write-Host "React dist       : $([bool]$BuildReactDist)"

if ($DryRun) {
    Write-Host ""
    Write-Host "-DryRun: preflight concluido. NAO foi feita conexao SSH, NAO houve alteracao no Scheduled Task, NAO houve deploy." -ForegroundColor Yellow
    "DRY_RUN=true" | Out-File -FilePath $LogFile -Encoding utf8
    "TARGET_SHA=$TargetSha" | Out-File -FilePath $LogFile -Append -Encoding utf8
    "ORIGINAL_COLLECTOR_STATE=$originalState" | Out-File -FilePath $LogFile -Append -Encoding utf8
    "BUILD_REACT_DIST=$([bool]$BuildReactDist)" | Out-File -FilePath $LogFile -Append -Encoding utf8
    if ($reactDistArtifact) { Remove-Item -LiteralPath $reactDistArtifact.TempRoot -Recurse -Force -ErrorAction SilentlyContinue }
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
        # base64 --decode --ignore-garbage descarta qualquer byte fora do
        # alfabeto Base64 (o BOM/CRLF espurios do transporte PowerShell 5.1,
        # ver comentario acima) antes de entregar os bytes reconstruidos ao
        # bash via pipe -- $LASTEXITCODE continua refletindo o exit code
        # real do bash remoto (ultimo comando do pipeline remoto).
        if ($BuildReactDist) {
            $remoteWrapper = @"
set -euo pipefail
remote_script="`$(mktemp)"
react_archive="`$(mktemp --suffix=.tar.gz)"
cleanup() { rm -f "`$remote_script" "`$react_archive"; }
trap cleanup EXIT
base64 --decode --ignore-garbage > "`$remote_script" <<'SPB_REMOTE_SCRIPT_B64'
$remoteScriptBase64
SPB_REMOTE_SCRIPT_B64
base64 --decode --ignore-garbage > "`$react_archive" <<'SPB_REACT_DIST_B64'
$reactDistArtifactBase64
SPB_REACT_DIST_B64
bash "`$remote_script" "`$@" "`$react_archive"
"@
            $remoteWrapperLf = ConvertTo-LfText $remoteWrapper
            $remoteWrapperBase64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($remoteWrapperLf))
            $remoteCommand = "base64 --decode --ignore-garbage | bash -s -- $TargetSha $AppDir"
            Write-Host "Comando remoto: ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=yes $DeployHost `"$remoteCommand`" (com React dist artifact)"
            $sshArgs = @("-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=yes", $DeployHost, $remoteCommand)
            $remoteOutputLines = $remoteWrapperBase64 | & ssh @sshArgs
        }
        else {
            $remoteCommand = "base64 --decode --ignore-garbage | bash -s -- $TargetSha $AppDir"
            # BatchMode=yes + ConnectTimeout=15: falha rapido se a chave nao
            # funcionar, nunca espera senha. StrictHostKeyChecking=yes: a
            # fingerprint continua sendo validada pelo known_hosts normal do
            # Windows -- nunca UserKnownHostsFile=/dev/null nem checking=no.
            $sshArgs = @("-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=yes", $DeployHost, $remoteCommand)
            Write-Host "Comando remoto: ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=yes $DeployHost `"$remoteCommand`""
            $remoteOutputLines = $remoteScriptBase64 | & ssh @sshArgs
        }
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
    if ($reactDistArtifact) { Remove-Item -LiteralPath $reactDistArtifact.TempRoot -Recurse -Force -ErrorAction SilentlyContinue }
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
        if ($reactDistArtifact) { Remove-Item -LiteralPath $reactDistArtifact.TempRoot -Recurse -Force -ErrorAction SilentlyContinue }
        exit 8
    }
    Write-Host "Rodada manual do Collector concluida com sucesso (LastTaskResult=0)."
}

if ($reactDistArtifact) {
    Remove-Item -LiteralPath $reactDistArtifact.TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

exit $deployExitCode
