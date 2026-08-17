# Runbook — deploy controlado de produção (SmartPayBot)

Este runbook documenta a automação local de deploy de produção introduzida para substituir a sequência manual de comandos SSH por um único comando PowerShell.

Arquivos envolvidos:

- `scripts/deploy-production.ps1` — orquestrador local (roda na máquina Windows do operador).
- `scripts/deploy-production-remote.sh` — script remoto, executado na VPS via stdin (não precisa estar previamente copiado lá).

## Pré-requisitos

- Chave SSH já configurada e funcional na máquina Windows local (via `~/.ssh/config`, `ssh-agent` ou chave default do OpenSSH). O script **nunca** lê, copia ou aponta para uma chave específica — ele apenas invoca o binário `ssh` já disponível, exatamente como o operador faria manualmente.
- Branch local `main` sincronizada com `origin/main` (`git fetch` + comparação de hash, feito automaticamente pelo script).
- Estar na branch `main` no repositório local no momento de rodar o script.
- Scheduled Task `SmartPayBot Collector` existente na máquina local.

## Comando

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy-production.ps1
```

Parâmetros disponíveis:

| Parâmetro | Default | Descrição |
|---|---|---|
| `-DeployHost` | `deploy@187.77.61.137` | Destino SSH (`usuario@host`). |
| `-AppDir` | `/home/deploy/apps/www.smartpaybot.com.br` | Diretório do clone de produção na VPS. |
| `-TargetSha` | *(vazio → usa `origin/main`)* | SHA git completo (40 hex) a implantar. Se informado, é validado como ancestral de `origin/main`. |
| `-Yes` | desligado | Pula a confirmação interativa. Usar apenas em contexto já supervisionado. |
| `-DryRun` | desligado | Executa somente o preflight local (git, SHA, detecção do Scheduled Task). Não conecta via SSH, não toca o Collector, não implanta nada. |
| `-RunCollectorAfter` | desligado | Após um deploy `SUCCESS`, dispara uma rodada manual do Collector (somente se ele já estava habilitado antes do deploy) e reporta o resultado. |

Exemplo recomendado antes de qualquer deploy real:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy-production.ps1 -DryRun
```

## Confirmação

Por padrão, antes de tocar produção, o script imprime um resumo (host, diretório remoto, branch, `TARGET_SHA`, estado atual do Collector, URL de produção, caminho do log) e pergunta:

```
Implantar este SHA em producao? [s/N]
```

Somente `s`/`sim` prossegue. Qualquer outra resposta cancela sem tocar em nada (`exit 3`). Use `-Yes` para pular esta etapa apenas em contextos já supervisionados manualmente por outro meio.

## Etapas executadas

### Local (`deploy-production.ps1`)

1. Preflight: confirma que o diretório é um repositório git, que a branch atual é `main`, faz `git fetch origin` e confirma que `main` local == `origin/main`.
2. Resolve `TARGET_SHA` (default: `origin/main`; se informado explicitamente, valida que existe e é ancestral de `origin/main`).
3. Consulta a Scheduled Task `SmartPayBot Collector` (`State`, `LastRunTime`, `LastTaskResult`, `NextRunTime`). Se estiver `Running`, aguarda até 120s antes de prosseguir — nunca mata o processo.
4. Mostra o resumo e pede confirmação (salvo `-Yes`/`-DryRun`).
5. Desabilita o Collector temporariamente (salvo se já estava `Disabled` — nesse caso preserva o estado).
6. Envia `scripts/deploy-production-remote.sh` via stdin para `ssh $DeployHost "bash -s -- $TargetSha $AppDir"` e captura a saída.
7. Interpreta a linha `DEPLOY_STATUS=` da saída remota e define o exit code local de acordo.
8. **Sempre**, mesmo em erro (bloco `finally`), restaura o Collector ao estado original: religa se estava habilitado antes, mantém desabilitado se já estava assim.
9. Se o deploy teve `SUCCESS` e `-RunCollectorAfter` foi passado (e o Collector estava habilitado originalmente), dispara uma rodada manual e reporta `LastTaskResult` + as últimas linhas de `logs\collector.log`.

### Remoto (`deploy-production-remote.sh`, executado na VPS)

1. Valida `TARGET_SHA` (regex de SHA git completo) e `APP_DIR` antes de qualquer ação.
2. Confirma que a branch da VPS é `main`, registra `PRE_DEPLOY_HEAD`, faz `git fetch origin` e exige que `TARGET_SHA == origin/main` (deploy padrão nunca implanta um SHA arbitrário fora da ponta de `main`).
3. Confirma que `PRE_DEPLOY_HEAD` é ancestral de `TARGET_SHA` (fast-forward seguro) e que o worktree não tem modificação *tracked* inesperada (`backups/` untracked é aceitável).
4. Confirma configuração segura via `get_settings()` (sem abrir `.env`): `APP_ENV=production`, `FLASK_ENV=production`; aborta se divergir.
5. Checkpoint do banco: hash SHA-256, `PRAGMA integrity_check`, `PRAGMA foreign_key_check`, backup em `backups/app.db.pre-deploy-<timestamp>.bak` (modo 600).
6. `git merge --ff-only $TARGET_SHA`.
7. Roda a suíte completa (`unittest discover`) e `py_compile` dos módulos centrais. **Se falhar, reverte o código para `PRE_DEPLOY_HEAD` (`git reset --hard`) sem jamais reiniciar o serviço** — o processo antigo continua no ar.
8. Restart do `smartpaybot`, confirmando `active` e bind exclusivo em `127.0.0.1:8000`.
9. Smoke HTTP (`/`, `/auth/login`, `/auth/register`, `/admin/`), gate do cookie (nome `session`, redigido — nunca imprime o valor), gate visual (ausência de qualquer marcador de homologação).
10. Smoke read-only do Telegram (`telegram_ready()`, `getWebhookInfo()` — nunca `sendMessage`/`setWebhook`/`deleteWebhook`).
11. Checkpoint pós-deploy do banco (informativo — divergência de hash sozinha não aciona rollback automático).
12. Amostra do `journalctl` desde o restart.
13. Emite as linhas máquina-legíveis finais e retorna o exit code correspondente.

## Rollback

Rollback automático (dentro do script remoto) acontece **somente depois do restart**, quando:

- o serviço não fica `active`;
- o serviço aparece bindado em `0.0.0.0:8000` em vez de `127.0.0.1:8000`;
- algum smoke HTTP falha (`/`, `/auth/login`, `/auth/register` fora do esperado; `/admin/` sem redirect);
- o cookie de produção não se chama `session`;
- o banner de homologação aparece em produção;
- a integridade do banco pós-deploy falha.

Nesses casos, o script executa `git reset --hard $PRE_DEPLOY_HEAD`, reinicia o serviço, roda um smoke mínimo e emite `DEPLOY_STATUS=ROLLED_BACK` (exit 2). **`origin/main` nunca é alterado** — o rollback é puramente local ao clone de produção.

Se algum gate falhar **antes** do restart (config, banco pré, testes), o script aborta com `DEPLOY_STATUS=FAILED` (exit 1) sem jamais tocar o serviço em execução — não há necessidade de rollback porque nada mudou em runtime.

## Interpretação dos exit codes

| Exit code | Significado |
|---|---|
| `0` | `DEPLOY_STATUS=SUCCESS` — deploy concluído e validado. |
| `1` | Falha local de preflight, falha de transporte SSH, ou `DEPLOY_STATUS=FAILED` remoto (abortado antes do restart). |
| `2` | `DEPLOY_STATUS=ROLLED_BACK` remoto — rollback automático executado com sucesso. |
| `3` | Operador respondeu não à confirmação — nenhuma ação foi tomada. |
| `4` | `-DryRun` concluído (informativo, não é erro). |

Linhas máquina-legíveis emitidas pelo script remoto (e propagadas ao log local):

```
DEPLOY_STATUS=SUCCESS|FAILED|ROLLED_BACK
PRE_DEPLOY_HEAD=<sha>
PRODUCTION_HEAD=<sha>
TARGET_SHA=<sha>
DATABASE_INTEGRITY=OK|NOT_OK
SESSION_COOKIE_NAME=session
HOMOLOGATION_BANNER_PRESENT=NO|YES
```

## Log local

Cada execução grava um log em `logs/deploy/deploy-YYYYMMDD-HHMMSS.log` (diretório já coberto pelo `.gitignore` via `logs/`). O log contém a transcrição completa da sessão (via `Start-Transcript`/`Stop-Transcript`), incluindo timestamps, gates e status — nunca segredos, já que nenhuma etapa local ou remota imprime valores de token/secret/senha.

## Segurança

- A chave SSH nunca é lida, copiada ou referenciada por caminho — o OpenSSH do Windows resolve a identidade da forma já configurada pelo operador.
- Nenhum parâmetro (`-DeployHost`, `-TargetSha`, `-AppDir`) é interpolado via `Invoke-Expression`; o script chama `ssh` diretamente pelo operador de chamada (`&`), passando argumentos como elementos de array, nunca como uma string concatenada e reavaliada por um shell.
- `TargetSha` é validado por regex estrita de 40 caracteres hexadecimais **minúsculos** (`-cmatch`, sensível a maiúsculas/minúsculas — `-match` do PowerShell é case-insensitive por padrão e aceitaria incorretamente hex maiúsculo se usado sem o `c`).
- `DeployHost` e `AppDir` são validados por regex restrita antes de qualquer uso.
- O script remoto revalida `TARGET_SHA`/`APP_DIR` de forma independente (defesa em profundidade — nunca confia cegamente no lado que o chamou).
- Nenhum secret é lido (`.env` nunca é aberto) nem impresso em nenhuma etapa, local ou remota.

## Troubleshooting

- **"branch atual e 'X', mas o deploy so pode ser disparado a partir de 'main'"**: rode `git switch main` antes.
- **"main local diverge de origin/main"**: rode `git pull --ff-only` (ou investigue por que divergiu) antes de tentar de novo.
- **"Collector ainda em execucao apos 120s"**: aguarde o ciclo atual terminar e rode novamente; o script nunca mata o processo.
- **`DEPLOY_STATUS=FAILED` com testes falhando**: o código já foi revertido automaticamente para `PRE_DEPLOY_HEAD` na VPS; investigue a falha localmente antes de tentar de novo.
- **`DEPLOY_STATUS=ROLLED_BACK`**: o serviço já está de volta ao código anterior; use o log em `logs/deploy/` e o `journalctl` remoto para diagnosticar a causa antes de tentar novamente.
- **Prompt de senha do SSH aparece**: a chave configurada não está sendo aceita automaticamente pelo agente; resolva a configuração SSH normalmente (fora deste script) antes de tentar o deploy.

## Futura automação CI/CD

Este runbook e os dois scripts foram desenhados para poderem ser reaproveitados futuramente por um workflow de GitHub Actions, sem reescrita:

```
GitHub-hosted runner
  -> Environment "production" (com approval manual obrigatório)
  -> chave SSH dedicada e restrita (não a chave pessoal do operador)
  -> execução do mesmo scripts/deploy-production-remote.sh na VPS
```

Essa migração **não é implementada nesta versão** e não deve ser feita alterando `.github/workflows/deploy.yml` sem uma tarefa dedicada, com decisão explícita sobre gestão de segredos do GitHub Actions (secrets do repositório, ambiente protegido, rotação da chave dedicada).
