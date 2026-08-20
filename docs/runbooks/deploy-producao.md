# Runbook — deploy controlado de produção (SmartPayBot)

Este runbook documenta a automação local de deploy de produção introduzida para substituir a sequência manual de comandos SSH por um único comando PowerShell.

Arquivos envolvidos:

- `scripts/deploy-production.ps1` — orquestrador local (roda na máquina Windows do operador).
- `scripts/deploy-production-remote.sh` — script remoto, executado na VPS via stdin. **Nunca é lido do filesystem local** — seu conteúdo é obtido de `git show TARGET_SHA:scripts/deploy-production-remote.sh`, amarrando criptograficamente o `TARGET_SHA` declarado ao código de deploy que efetivamente roda.

## Pré-requisitos

- Chave SSH já configurada e funcional na máquina Windows local (via `~/.ssh/config`, `ssh-agent` ou chave default do OpenSSH). O script **nunca** lê, copia ou aponta para uma chave específica — ele apenas invoca o binário `ssh` já disponível, exatamente como o operador faria manualmente.
- `sudo` não interativo (`sudo -n`) configurado para o usuário `deploy` na VPS, cobrindo `systemctl` e `journalctl` sobre o serviço `smartpaybot`. Esta automação **nunca configura sudoers** — apenas verifica que já funciona, e aborta antes de qualquer alteração se não funcionar.
- Branch local `main` sincronizada com `origin/main` (`git fetch` + comparação de hash, feito automaticamente pelo script).
- Estar na branch `main` no repositório local, **com working tree completamente limpo** (`git status --porcelain` vazio — não apenas sem modificações *tracked*) no momento de rodar o script. Isso é exigido porque o script lê o conteúdo do script remoto do próprio `TARGET_SHA`, e um working tree sujo indicaria incerteza sobre o que realmente está commitado.
- Scheduled Task `SmartPayBot Collector` existente na máquina local.
- `base64` (GNU coreutils, com suporte a `--ignore-garbage`) disponível no `PATH` do usuário `deploy` na VPS — usado apenas para reconstruir os bytes exatos do script de deploy recebidos via stdin (transporte byte-safe; ver etapa 8 abaixo). Presente por padrão em qualquer Debian/Ubuntu.
- **PowerShell "Executar como Administrador"** quando o Collector estiver habilitado no momento do deploy (`State != Disabled`) e o comando **não** for `-DryRun` — `Disable-ScheduledTask`/`Enable-ScheduledTask` exigem elevação nesta máquina. `-DryRun` nunca exige elevação, pois é somente leitura.

## Comando

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy-production.ps1
```

Parâmetros disponíveis:

| Parâmetro | Default | Descrição |
|---|---|---|
| `-DeployHost` | `deploy@187.77.61.137` | Destino SSH (`usuario@host`). Nem usuário nem host podem começar com `-` (evita disfarçar uma opção do `ssh` como destino). |
| `-AppDir` | `/home/deploy/apps/www.smartpaybot.com.br` | Diretório do clone de produção na VPS. **Esta versão suporta exatamente este diretório** — qualquer outro valor informado falha imediatamente. |
| `-TargetSha` | *(vazio → usa `origin/main`)* | SHA git completo (40 hex minúsculos) a implantar. Se informado, **deve ser exatamente igual a `origin/main`** — esta versão nunca implanta um SHA arbitrário, mesmo que seja um ancestral válido. |
| `-Yes` | desligado | Pula a confirmação interativa. Usar apenas em contexto já supervisionado. |
| `-DryRun` | desligado | Executa somente o preflight local (git, working tree limpo, SHA, detecção do Scheduled Task). Não conecta via SSH, não toca o Collector, não implanta nada. |
| `-RunCollectorAfter` | desligado | Após um deploy `SUCCESS` **e** o Collector já ter sido **confirmadamente** restaurado ao estado original, dispara uma rodada manual (somente se ele estava habilitado antes do deploy) e reporta o resultado. Funciona como um *smoke gate* local solicitado pelo operador: se `LastTaskResult != 0`, o script termina com `exit 8` sem alterar o `DEPLOY_STATUS` remoto. Nunca inicia uma segunda instância se uma já estiver em execução. Nunca imprime o conteúdo bruto de `logs\collector.log` — apenas campos seguros do próprio Scheduled Task. |

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

1. Preflight: confirma que o diretório é um repositório git, que a branch atual é `main`, que `git status --porcelain` está **completamente vazio**, faz `git fetch origin` e confirma que `main` local == `origin/main`.
2. Resolve `TARGET_SHA` (default: `origin/main`; se informado explicitamente, exige igualdade exata com `origin/main`, não apenas ancestralidade).
3. Obtém o conteúdo de `scripts/deploy-production-remote.sh` via `git show TARGET_SHA:scripts/deploy-production-remote.sh` — nunca do filesystem local. **Captura em bytes crus:** o processo `git` é invocado diretamente via `System.Diagnostics.Process` (não via pipeline do PowerShell) e o `stdout.BaseStream` é copiado byte a byte para um `MemoryStream` — nunca `@(git show ...)` (array de linhas, perde terminadores), nunca `-join` (reconstrói LF só *entre* linhas, perdendo o newline final do blob) e nunca `Encoding.GetBytes()` sobre uma string já passada pelo pipeline textual do PowerShell (que pode alterar os caracteres Unicode presentes nos comentários do script). O resultado é byte-idêntico ao blob Git, incluindo o LF final — validado por comparação de SHA-256 contra `git cat-file blob <BLOB_SHA>`. Se o processo `git` retornar exit code diferente de 0 ou produzir zero bytes, aborta.
4. Consulta a Scheduled Task `SmartPayBot Collector` (`State`, `LastRunTime`, `LastTaskResult`, `NextRunTime`). Se estiver `Running`, aguarda até 120s antes de prosseguir — nunca mata o processo.
5. Mostra o resumo. Se **não** for `-DryRun` e o Collector estiver `!= Disabled`, valida que o PowerShell está elevado (`WindowsPrincipal.IsInRole(Administrator)`) — **antes** de qualquer prompt de confirmação e antes de qualquer `Disable-ScheduledTask`. Sem elevação: aborta com `exit 1`, sem prompt, sem tocar a Scheduled Task, sem SSH.
6. Pede confirmação (salvo `-Yes`/`-DryRun`).
7. Desabilita o Collector temporariamente (salvo se já estava `Disabled` — nesse caso preserva o estado). A tentativa é envolvida em `try/catch` explícito: se `Disable-ScheduledTask` falhar (ex.: `Acesso negado` por falta de elevação), o script registra o erro no log, **não** tenta `Enable-ScheduledTask` (pois nunca confirmou ter desabilitado a task) e aborta com `exit 1` **antes** de qualquer conexão SSH. Uma flag interna (`collectorDisabledByDeploy`) só passa a `true` depois que `Disable-ScheduledTask` retorna com sucesso, e é essa flag — não o estado original — que decide se o `finally` (passo 10) tentará religar a task.
8. Converte os bytes crus obtidos no passo 3 (`[Convert]::ToBase64String($remoteScriptBytes)`, sem nenhum decode/re-encode textual intermediário do PowerShell) e envia essa string Base64 via stdin para `ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=yes $DeployHost "base64 --decode --ignore-garbage | bash -s -- $TargetSha $AppDir"`, capturando a saída. **Transporte byte-safe:** o Windows PowerShell 5.1 injeta um BOM UTF-8 (`EF BB BF`) no início e um `\r\n` extra no final de qualquer string enviada via pipeline (`$texto | & processo`) a um processo nativo com stdin redirecionado — confirmado por reprodução isolada (branch `fix/deploy-ssh-stdin-transport`) e responsável por um incidente real em produção (ver `CHANGELOG.md`). Converter o script para Base64 (alfabeto ASCII puro) antes do pipeline faz o BOM/CRLF espúrios caírem fora do alfabeto Base64; `base64 --decode --ignore-garbage` do lado remoto os descarta e reconstrói os bytes originais exatamente — validado por comparação de SHA-256 em três pontos (blob Git real, bytes capturados pelo PowerShell, bytes reconstruídos após o decode remoto), sem nunca executar o script localmente. `BatchMode=yes` garante falha rápida (nunca espera senha) se a chave local não estiver funcional; `StrictHostKeyChecking=yes` garante que a fingerprint continua sendo validada pelo `known_hosts` normal do Windows — a verificação de host key **nunca é desabilitada** (nunca `StrictHostKeyChecking=no` nem `UserKnownHostsFile=/dev/null`). **Validado em operação real** no deploy do SPB-254 em 20/08/2026 (primeiro deploy real após o hotfix): `DEPLOY_STATUS=SUCCESS` com `LOCAL_DEPLOY_EXIT_CODE=0`, sem qualquer ocorrência de `numeric argument required`.
9. Interpreta a linha `DEPLOY_STATUS=` da saída remota e define o exit code local de acordo.
10. **Sempre**, mesmo em erro (bloco `finally`), tenta restaurar o Collector ao estado original **somente se `collectorDisabledByDeploy` for `true`** — ou seja, somente se este próprio deploy confirmou tê-lo desabilitado; um estado original `!= Disabled` que nunca chegou a ser efetivamente pausado (ex.: `Disable-ScheduledTask` falhou) não aciona `Enable-ScheduledTask`. Cada operação (`Enable-ScheduledTask`, consulta do estado final) é envolvida em `try/catch` — uma exceção aqui nunca passa despercebida.
11. **Gate fail-closed da restauração do Collector, logo após o `finally`:** se a task foi efetivamente desabilitada por este deploy (`collectorDisabledByDeploy=true`) mas o estado final não pôde ser confirmado como restaurado (permanece `Disabled`, ou a consulta/`Enable-ScheduledTask` lançou exceção), o script **não** propaga o exit code do deploy remoto — encerra imediatamente com `exit 7` (`COLLECTOR_RESTORE_FAILED`), deixando claro que o `DEPLOY_STATUS` remoto pode ter sido `SUCCESS` mas isso **não** significa sucesso operacional total.
12. **Somente se a restauração foi confirmada** — nunca antes —, se o deploy teve `SUCCESS` e `-RunCollectorAfter` foi passado (e o Collector estava habilitado originalmente), dispara uma rodada manual e reporta apenas `State`, `LastRunTime` e `LastTaskResult` do próprio Scheduled Task (**nunca** o conteúdo de `logs\collector.log`, que pode registrar corpo bruto de resposta HTTP de erro). Se `LastTaskResult != 0`, encerra com `exit 8` (`POST_DEPLOY_COLLECTOR_FAILED`) — o `DEPLOY_STATUS` remoto não é alterado por isso, é uma falha do *smoke gate* local solicitado pelo operador.
13. Persiste a saída remota completa e os metadados do deploy (`TARGET_SHA`, exit code, e `COLLECTOR_RESTORE_FAILED=true`/`POST_DEPLOY_COLLECTOR_FAILED=true` quando aplicável) explicitamente em `logs/deploy/deploy-*.log`, além da transcrição da sessão local.

### Remoto (`deploy-production-remote.sh`, executado na VPS)

1. Valida `TARGET_SHA` (regex de SHA git completo, 40 hex minúsculos) e `APP_DIR` (deve ser exatamente `/home/deploy/apps/www.smartpaybot.com.br`) antes de qualquer ação.
2. Confirma que `sudo -n true` funciona (sudo não interativo) — aborta antes de qualquer alteração se não funcionar.
3. Confirma que a branch da VPS é `main`, registra `PRE_DEPLOY_HEAD`, faz `git fetch origin` e exige que `TARGET_SHA == origin/main` exatamente.
4. Confirma que `PRE_DEPLOY_HEAD` é ancestral de `TARGET_SHA` (fast-forward seguro) e que o worktree não tem modificação *tracked* inesperada (`backups/` untracked é aceitável).
5. **Gate de saúde pré-deploy (obrigatório):** `smartpaybot` deve estar `active`, deve haver listener em `127.0.0.1:8000`, **não** deve haver listener em `0.0.0.0:8000`, `HOME` e `LOGIN` devem responder `200`. Se produção já estiver *unhealthy*, aborta — a automação nunca tenta "consertar" via deploy.
6. Gate de configuração completo via `get_settings()` (sem abrir `.env`): exige `APP_ENV=production`, `FLASK_ENV=production`, `TELEGRAM_MODE=production`, `SCHEDULER_ENABLED=False`, e presença (`*_SET=True`) de `TELEGRAM_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `INTERNAL_INGEST_TOKEN`, `SECRET_KEY` — nunca imprime os valores.
7. Backup **online** e consistente do banco: `sqlite3 app.db ".backup 'arquivo'"` (nunca `cp` em banco vivo), `chmod 600`, e o próprio arquivo de backup é validado (`PRAGMA integrity_check` / `foreign_key_check`) antes de prosseguir — aborta se o backup for inválido.
8. `git merge --ff-only $TARGET_SHA`.
9. **Test gate:** roda a suíte completa (`unittest discover`) e `py_compile` dos módulos centrais. Se falhar, executa recuperação (`git reset --hard PRE_DEPLOY_HEAD`), **confirma explicitamente** que o reset funcionou e que `HEAD == PRE_DEPLOY_HEAD` — se a confirmação falhar, emite `DEPLOY_STATUS=RECOVERY_FAILED` em vez de alegar segurança. O serviço nunca é reiniciado nesta etapa.
10. **Gate de configuração de sessão (B4), ainda antes do restart, sem tocar Telegram:** cria a aplicação (`create_app()`) e confere `SESSION_COOKIE_NAME=session`, `SECURE=True`, `HTTPONLY=True`, `SAMESITE=Lax`, `DOMAIN=None`, `PATH=/`. Falha aqui usa a mesma recuperação do passo 9 (recovery pré-restart, sem restart).
11. **Restart do `smartpaybot` (hard gate em cada etapa):** `systemctl restart` **precisa retornar 0** — se não retornar, aciona o rollback imediatamente, sem prosseguir para a checagem de `active` (falha de restart nunca é tratada como "nada aconteceu"; o código novo já está em disco, então a única saída segura é reverter). Só então confirma `active`, depois bind exclusivo em `127.0.0.1:8000` — cada checagem é sequencial e qualquer uma que falhar aciona o rollback antes de prosseguir para os smokes.
12. Smoke HTTP (`/`, `/auth/login`, `/auth/register` → `200`; `/admin/` → redirect).
13. **Gate do cookie real, fail-closed:** requisita `/auth/login` e exige um `Set-Cookie` presente — **a ausência do header é tratada como falha**, nunca como sucesso presumido. Valida nome (`session`), `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, ausência de `Domain`. Nunca imprime o valor do cookie.
14. Gate visual: ausência de qualquer marcador de homologação (`HOMOLOGA`, `AMBIENTE DE TESTES`, `env-homologation`) no HTML da home.
15. **Telegram como gate obrigatório** (não mais informativo): `telegram_ready()` deve ser `True`; `get_webhook_info()` deve retornar `ok=True` e `result.url` deve ser exatamente `https://smartpaybot.com.br/webhook/telegram`. Reporta `pending_update_count` e a **presença booleana** de `last_error_message` (nunca o conteúdo da mensagem). Nunca chama `sendMessage`/`setWebhook`/`deleteWebhook`/`getUpdates`.
16. Checkpoint pós-deploy do banco (`integrity_check`/`foreign_key_check` — gate real; hash apenas informativo, já que uma escrita legítima concorrente é possível).
17. Journal desde o restart: **somente contagem** de ocorrências de padrões de erro (`JOURNAL_ERROR_HITS=N`) — as linhas completas nunca são impressas automaticamente, para não arriscar vazar PII/secret que código futuro possa vir a logar.
18. Emite as linhas máquina-legíveis finais e retorna o exit code correspondente.

Qualquer falha nos passos 11–16 (depois do restart) aciona o rollback validado (ver seção abaixo).

## Rollback e recuperação

Há duas famílias de reversão, dependendo de o serviço já ter sido reiniciado ou não:

**Recuperação pré-restart** (passos 9–10 da lista remota): se o *test gate* ou o gate de configuração de sessão falharem depois do fast-forward mas antes do restart, o script executa `git reset --hard PRE_DEPLOY_HEAD` e **confirma explicitamente** o resultado (`git rev-parse HEAD == PRE_DEPLOY_HEAD`). Se a confirmação passar, emite `DEPLOY_STATUS=FAILED` (exit 1) — o serviço antigo nunca foi tocado. Se a confirmação **não** passar, emite `DEPLOY_STATUS=RECOVERY_FAILED` (exit 4) — isso significa que o filesystem da VPS pode não corresponder a nenhuma versão conhecida e exige inspeção manual imediata (o serviço continua rodando o binário/processo antigo em memória, mas o código em disco pode estar em estado intermediário).

**Rollback pós-restart** (passo 11 em diante): se o **próprio `systemctl restart` principal retornar diferente de 0**, ou se o serviço não ficar `active`, ou o bind não for exclusivo em `127.0.0.1:8000`, ou qualquer smoke HTTP, o gate do cookie, o gate visual, o gate do Telegram ou a integridade pós-deploy do banco falharem, o script executa e **valida individualmente cada uma** das seguintes condições antes de declarar sucesso do rollback: `git reset --hard` retornou 0; `HEAD == PRE_DEPLOY_HEAD`; `systemctl restart` retornou 0; serviço `active`; listener em `127.0.0.1:8000` presente; **nenhum** listener em `0.0.0.0:8000`; `HOME` retorna `200`. Se **todas** forem verdadeiras, emite `DEPLOY_STATUS=ROLLED_BACK` (exit 2). Se **qualquer uma** falhar, emite `DEPLOY_STATUS=ROLLBACK_FAILED` (exit 5) — produção pode estar degradada e exige inspeção manual imediata. `PRODUCTION_HEAD` é sempre obtido via `git rev-parse HEAD` no momento, nunca presumido.

Em nenhum caso `origin/main` é alterado — toda reversão é puramente local ao clone de produção.

## Interpretação dos exit codes

| Exit code | Origem | Significado |
|---|---|---|
| `0` | remoto | `DEPLOY_STATUS=SUCCESS` — deploy concluído e validado, **e** o Collector foi confirmadamente restaurado (e, se `-RunCollectorAfter`, a rodada pós-deploy também teve sucesso). |
| `1` | local ou remoto | Falha local de preflight/transporte (inclui PowerShell não elevado quando o Collector precisa ser pausado, e falha de `Disable-ScheduledTask`), ou `DEPLOY_STATUS=FAILED` remoto (abortado ou recuperado com sucesso antes do restart). |
| `2` | remoto | `DEPLOY_STATUS=ROLLED_BACK` — rollback pós-restart executado e **totalmente validado**. |
| `3` | local | Operador respondeu não à confirmação — nenhuma ação foi tomada. A conexão SSH nunca chegou a acontecer. |
| `4` | remoto | `DEPLOY_STATUS=RECOVERY_FAILED` — a reversão pré-restart **não pôde ser confirmada**. Inspecionar a VPS manualmente antes de qualquer nova tentativa. |
| `5` | remoto | `DEPLOY_STATUS=ROLLBACK_FAILED` — o rollback pós-restart **não pôde ser totalmente validado**. Produção pode estar degradada; inspecionar manualmente agora. |
| `6` | local | `-DryRun` concluído (informativo, não é erro). A conexão SSH nunca chegou a acontecer. |
| `7` | local, pós-SSH | `COLLECTOR_RESTORE_FAILED` — a restauração operacional do Collector ao estado original **não pôde ser confirmada** (continua `Disabled`, ou a operação lançou exceção). O `DEPLOY_STATUS` remoto (mesmo que `SUCCESS`) é sobrescrito por este código, pois a falha operacional local é a mais urgente a resolver. **Nunca** propagado como exit 0. Ação manual imediata: verificar e religar a Scheduled Task `SmartPayBot Collector`. |
| `8` | local, pós-SSH | `POST_DEPLOY_COLLECTOR_FAILED` — somente quando `-RunCollectorAfter` foi solicitado: a rodada manual pós-deploy terminou com `LastTaskResult != 0`. O `DEPLOY_STATUS` remoto **não é alterado** por isso — é uma falha do *smoke gate* local, não do deploy em si. |

**Importante:** `SUCCESS` (exit 0) do deploy remoto **não é, por si só, garantia de sucesso operacional total** — se a restauração do Collector falhar (exit 7) ou o smoke gate pós-deploy solicitado falhar (exit 8), esses códigos sobrescrevem o `deployExitCode` remoto no exit final do script local, precisamente para que um `SUCCESS` aparente nunca esconda uma falha operacional real.

Linhas máquina-legíveis emitidas pelo script remoto (e persistidas explicitamente no log local, além de aparecerem no console):

```
DEPLOY_STATUS=SUCCESS|FAILED|ROLLED_BACK|RECOVERY_FAILED|ROLLBACK_FAILED
PRE_DEPLOY_HEAD=<sha>
PRODUCTION_HEAD=<sha>
TARGET_SHA=<sha>
DATABASE_INTEGRITY=OK|NOT_OK
SESSION_COOKIE_NAME=session
HOMOLOGATION_BANNER_PRESENT=NO|YES
JOURNAL_ERROR_HITS=<contagem>
```

## Log local

Cada execução grava um log em `logs/deploy/deploy-YYYYMMDD-HHMMSS.log` (diretório já coberto pelo `.gitignore` via `logs/`). O log contém a transcrição da sessão local (via `Start-Transcript`/`Stop-Transcript`) **e**, anexada explicitamente após o encerramento do transcript, a saída remota completa (todas as linhas acima, `TARGET_SHA` e o exit code local) — a saída remota é anexada de forma explícita porque `Stop-Transcript` fecha o arquivo antes da impressão do resultado, e depender apenas do transcript perderia essas linhas. Nunca há segredos no log, já que nenhuma etapa local ou remota imprime valores de token/secret/senha/cookie.

## Segurança

- A chave SSH nunca é lida, copiada ou referenciada por caminho — o OpenSSH do Windows resolve a identidade da forma já configurada pelo operador. A conexão usa `-o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=yes` para falhar rápido se a chave não funcionar (nunca espera senha), **com** a verificação de host key mantida ativa (a fingerprint continua validada pelo `known_hosts` normal do Windows — nunca `StrictHostKeyChecking=no` nem `UserKnownHostsFile=/dev/null`).
- A restauração operacional do Collector é **fail-closed**: se não puder ser confirmada, o script encerra com `exit 7` em vez de um `exit 0` enganoso — um `DEPLOY_STATUS=SUCCESS` remoto nunca mascara uma falha operacional local. Da mesma forma, `logs\collector.log` nunca é impresso automaticamente (pode conter corpo bruto de resposta HTTP de erro); apenas campos estruturados e seguros do próprio Scheduled Task (`State`, `LastRunTime`, `LastTaskResult`).
- Nenhum parâmetro (`-DeployHost`, `-TargetSha`, `-AppDir`) é interpolado via `Invoke-Expression`; o script chama `ssh` diretamente pelo operador de chamada (`&`), passando argumentos como elementos de array, nunca como uma string concatenada e reavaliada por um shell.
- `TargetSha` é validado por regex estrita de 40 caracteres hexadecimais **minúsculos** (`-cmatch`, sensível a maiúsculas/minúsculas — `-match` do PowerShell é case-insensitive por padrão e aceitaria incorretamente hex maiúsculo se usado sem o `c`), e deve ser **exatamente** `origin/main`, não apenas um ancestral.
- `DeployHost` é validado por regex que proíbe usuário ou host começando com `-` (evita disfarçar uma opção do `ssh` como se fosse o destino).
- `AppDir` deve ser **exatamente** `/home/deploy/apps/www.smartpaybot.com.br` — qualquer outro valor (relativo, com `..`, ou outro diretório de produção legítimo) é recusado.
- O conteúdo do script remoto é obtido de `git show TARGET_SHA:...`, nunca do filesystem local — exige working tree completamente limpo (`git status --porcelain` vazio), amarrando criptograficamente o SHA declarado ao código executado.
- O script remoto revalida `TARGET_SHA`/`APP_DIR` de forma independente (defesa em profundidade — nunca confia cegamente no lado que o chamou).
- Todas as chamadas `sudo` no script remoto usam `sudo -n` (não interativo); se a permissão não estiver configurada, o script aborta antes de qualquer alteração, em vez de travar esperando senha com o Collector já pausado.
- Nenhum secret é lido (`.env` nunca é aberto) nem impresso em nenhuma etapa, local ou remota. O valor do cookie de sessão nunca é impresso — apenas seus atributos (nome, presença de `Secure`/`HttpOnly`/`Domain`, valor de `SameSite`/`Path`).

## Troubleshooting

- **"branch atual e 'X', mas o deploy so pode ser disparado a partir de 'main'"**: rode `git switch main` antes.
- **"working tree local NAO esta completamente limpo"**: `git status` para ver o que falta commitar/limpar; o script exige zero saída de `git status --porcelain` (inclusive arquivos não rastreados fora dos já ignorados) antes de amarrar o `TARGET_SHA`.
- **"main local diverge de origin/main"**: rode `git pull --ff-only` (ou investigue por que divergiu) antes de tentar de novo.
- **"TargetSha informado difere de origin/main"**: esta versão só implanta a ponta de `main`; se a intenção é outra, isso exige decisão explícita fora do escopo desta automação.
- **"Collector ainda em execucao apos 120s"**: aguarde o ciclo atual terminar e rode novamente; o script nunca mata o processo.
- **"o Collector esta '...' e precisa ser pausado ... mas este PowerShell nao esta elevado"**: feche o terminal atual e abra um novo PowerShell via "Executar como Administrador" antes de rodar o deploy novamente. `-DryRun` não exige elevação.
- **"Disable-ScheduledTask falhou ... Acesso negado"**: mesma causa raiz da elevação acima (ou permissão local restritiva na Scheduled Task). O script já garante que nenhum SSH ocorreu e que `Enable-ScheduledTask` **não** foi chamado — a task permanece no estado em que já estava antes da tentativa. Corrija a elevação/permissão e rode novamente.
- **"sudo nao-interativo indisponivel"**: configure `sudo -n` para o usuário `deploy` na VPS (fora desta automação) antes de tentar novamente.
- **"producao ja esta unhealthy antes do deploy"**: investigue e resolva a causa manualmente; a automação nunca tenta "consertar" via deploy.
- **`DEPLOY_STATUS=FAILED` com testes falhando**: o código já foi revertido e a reversão foi **confirmada** na VPS; investigue a falha localmente antes de tentar de novo.
- **`DEPLOY_STATUS=RECOVERY_FAILED`**: pare imediatamente e inspecione a VPS manualmente — a reversão do código pré-restart não pôde ser confirmada. Não tente um novo deploy automatizado até entender o estado real do filesystem.
- **`DEPLOY_STATUS=ROLLED_BACK`**: o serviço já está de volta ao código anterior e **foi validado** (git, restart, listener, HOME 200); use o log em `logs/deploy/` para diagnosticar a causa antes de tentar novamente.
- **`DEPLOY_STATUS=ROLLBACK_FAILED`**: pare imediatamente e inspecione a VPS manualmente — produção pode estar degradada e o rollback não pôde ser totalmente validado.
- **Prompt de senha do SSH aparece**: não deveria — `BatchMode=yes` faz o `ssh` falhar rápido em vez de esperar. Se a conexão falhar por credencial, resolva a configuração SSH normalmente (fora deste script) antes de tentar o deploy.
- **`ssh` falha com erro de host key**: `StrictHostKeyChecking=yes` está ativo de propósito — se a fingerprint do host mudou legitimamente (ex.: reinstalação da VPS), atualize `known_hosts` manualmente pelo fluxo normal do OpenSSH antes de tentar o deploy. Este script nunca contorna essa verificação.
- **`exit 7` (`COLLECTOR_RESTORE_FAILED`)**: o deploy remoto pode ter sido `SUCCESS`, mas a Scheduled Task `SmartPayBot Collector` não pôde ser confirmada como restaurada. Rode `Get-ScheduledTask -TaskName "SmartPayBot Collector"` para ver o estado real e, se necessário, `Enable-ScheduledTask -TaskName "SmartPayBot Collector"` manualmente.
- **`exit 8` (`POST_DEPLOY_COLLECTOR_FAILED`)**: só ocorre com `-RunCollectorAfter`. O deploy em si foi `SUCCESS` e o Collector foi religado, mas a rodada de teste solicitada terminou com `LastTaskResult != 0`. Investigue o ciclo mais recente do Collector separadamente (fora deste script) antes de assumir que está saudável.
- **`bash: exit: 0: numeric argument required` no stderr remoto, com `exit 2` local logo após um `DEPLOY_STATUS=SUCCESS` real**: sintoma do bug de transporte já corrigido (ver `CHANGELOG.md`) — o PowerShell 5.1 anexava um `\r` à última linha do script antes da versão com transporte Base64. Se este erro reaparecer, confirme que a versão em uso já inclui o transporte Base64 (`base64 --decode --ignore-garbage | bash -s -- ...` no comando remoto, não mais `bash -s -- ...` direto) antes de investigar outra causa.

## Futura automação CI/CD

Este runbook e os dois scripts foram desenhados para poderem ser reaproveitados futuramente por um workflow de GitHub Actions, sem reescrita:

```
GitHub-hosted runner
  -> Environment "production" (com approval manual obrigatório)
  -> chave SSH dedicada e restrita (não a chave pessoal do operador)
  -> execução do mesmo scripts/deploy-production-remote.sh na VPS,
     amarrado ao SHA do workflow run via git show
```

Essa migração **não é implementada nesta versão** e não deve ser feita alterando `.github/workflows/deploy.yml` sem uma tarefa dedicada, com decisão explícita sobre gestão de segredos do GitHub Actions (secrets do repositório, ambiente protegido, rotação da chave dedicada).
