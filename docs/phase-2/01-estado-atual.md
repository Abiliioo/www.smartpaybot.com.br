# Estado atual

## Arquitetura atual

Estado confirmado no codigo local:

- `app/`: aplicacao Flask, blueprints, templates Jinja, formularios, decorators e seguranca Flask-Login.
- `domain/`: modelos SQLAlchemy, repositorios e servicos de negocio.
- `infrastructure/`: configuracao, banco, logging, scraping, Telegram, rate limit em memoria e utilitarios.
- `workers/`: ingestor, matcher, notifier e scheduler APScheduler.
- `scripts/`: utilitarios operacionais, migracoes manuais e coletor local.
- `tests/`: testes unitarios de servicos e notifier, probes de scraping.

## Fluxo de coleta

Fluxo operacional atual:

`run_collector.bat -> scripts/local_collector_push.py -> POST /internal/ingest/projects -> SQLite -> matcher -> notifier -> Telegram`

O runner local usa `.venv\Scripts\python.exe` relativo ao diretorio do proprio `.bat` e grava em `logs\collector.log`.

SPB-264 (hardening do Collector: HTTP strict, parser health, exit codes, retry e logs seguros) **CONCLUIDO — MERGEADO e VALIDADO no Collector local real em 20/08/2026**, PR #4, Issue #3 fechada, merge commit `e345fefe900c70636260d8521762c298cbfc1956`: `py_compile` aprovado, `tests.test_collector_push_spb264` 12/12, `run_collector.bat` retornou `EXIT_CODE=0`; gate local real com `pages_attempted=10`, `pages_ok=10`, `pages_failed=0`, `parser_ok=10`, `parser_failed=0`, `projects_collected=100`, `projects_unique=100`, ingest OK (`received=100`; primeiro ciclo `inserted=1`, `updated=20`, `skipped=79`; segundo ciclo `inserted=0`, `updated=0`, `skipped=100`). Nao houve deploy VPS, alteracao de Scheduled Task, cadencia ou `--pages 10`. Observacao futura: o console PowerShell exibiu alguns caracteres com encoding quebrado no log, sem bloquear o gate operacional.

O scheduler interno da VPS esta documentado como desativado operacionalmente, embora o codigo ainda tenha `workers/scheduler.py` e possa iniciar quando `SCHEDULER=1`.

## Fluxo de ingestao

`app/routes/ingest.py` registra o blueprint `/internal` e a rota `POST /ingest/projects`.

A rota:

- exige header `X-Internal-Ingest-Token` quando `INTERNAL_INGEST_TOKEN` esta configurado;
- recusa ingestao sem token em qualquer `APP_ENV != development` (SPB-270);
- aceita payload `{"projects": [...]}`;
- valida `project_id`, `title` e `link`;
- coage campos opcionais de metadados;
- faz upsert em `projects_global`;
- dispara uma thread daemon para `match_recent_projects()` e `notify_pending()` quando houve insercao ou atualizacao.

SPB-270 (alinhamento de `DEBUG` e ingest sensivel a `APP_ENV`) **CONCLUIDO — IMPLANTADO e VALIDADO em producao em 21/08/2026**, PR #7, PR #8, Issue #6 fechada, producao atualizada de `588b86167f633faab812f23e3fbe0be0d534918c` para `15378dda90840579060e81be7cef3f47939ec6e9`: `DEBUG` deixou de derivar de `FLASK_ENV` e passa a usar `APP_ENV` como fonte de verdade; `homologation` e `production` recusam `DEBUG=true` no boot e ingest sem `INTERNAL_INGEST_TOKEN` com 403, mesmo quando `FLASK_ENV=development`. Deploy controlado via `scripts/deploy-production.ps1`: `DEPLOY_STATUS=SUCCESS`, `LOCAL_DEPLOY_EXIT_CODE=0`, testes remotos 241/241, smoke HTTP OK (`HOME=200`, `LOGIN=200`, `REGISTER=200`, `ADMIN=302`), cookie `session` preservado (`Secure`/`HttpOnly`/`SameSite=Lax`/`Path=/`, sem `Domain`), banner de homologacao ausente, Telegram read-only OK, banco integro, `JOURNAL_ERROR_HITS=0`, rollback nao executado, Collector restaurado (`State final Ready`) e ciclo automatico pos-deploy com `LastTaskResult=0`.

## Fluxo do matcher

`workers/matcher.py` busca projetos globais recentes usando `MATCH_LOOKBACK_MINUTES`, carrega keywords por usuario e chama `fanout_project_to_users`.

`domain/services/projects_service.py` implementa o bug aberto: `match_users_for_title()` normaliza texto e keyword e usa `if nkw in nt`, isto e, substring.

## Fluxo do notifier

`workers/notifier.py` consulta itens elegiveis em `projects_per_user`, filtra antes de aplicar limite por:

- `notified_at IS NULL`;
- `notify_attempts < MAX_ATTEMPTS`;
- `bot_active = true`;
- `chat_id` preenchido.

O notifier respeita limite diario de plano antes de enviar, monta mensagem rica quando ha metadados, envia pelo Telegram e marca `notified_at` em sucesso. Em falha incrementa `notify_attempts`.

## Fluxo do Telegram

`app/routes/webhook_telegram.py` recebe `/webhook/telegram`, valida `X-Telegram-Bot-Api-Secret-Token` quando configurado, processa `/start <codigo>`, vincula `chat_id` ao usuario e invalida `telegram_link_code`.

`infrastructure/telegram.py` centraliza envio e operacoes de webhook.

## Banco atual

Modelos confirmados em `domain/models.py`:

- `users`: usuario, email, hash de senha, flags admin/subscriber, `bot_active`, Telegram e timestamps.
- `user_keywords`: keywords por usuario.
- `projects_global`: projeto global deduplicado por `project_id`, com metadados de scraping.
- `projects_per_user`: projecao do projeto para usuario, keyword, notificacao, tentativas e campos de ganho.
- `plans`: catalogo Free/Pro.
- `subscriptions`: plano por usuario.
- `user_alerts_daily`: contador diario de alertas enviados.

Nao ha modelos atuais para reset de senha, auditoria administrativa, caixa interna com leitura/arquivamento, entregas por canal ou preferencias por canal.

## Autenticacao e autorizacao

- Login e registro ficam em `app/routes/auth.py`.
- Senhas usam hash do Werkzeug.
- Login tem rate limit em memoria via `infrastructure/ratelimit.py`.
- Sessao usa Flask-Login.
- CSRF fica ativo via Flask-WTF, com excecoes explicitas para webhook Telegram e ingestao interna.
- `admin_required` restringe `/admin/` por `current_user.is_admin`.

## Admin atual

`app/routes/admin.py` e `app/templates/admin.html` entregam (SPB-210, implantado e validado em producao em 07/08/2026, commit `c21786e`):

- listagem de usuarios com busca por username/email;
- filtros combinaveis por plano (`Todos`, `Free`, `Pro`, `Admin`, mutuamente exclusivos), monitoramento e Telegram vinculado;
- paginacao;
- plano atual;
- data de subscription;
- quantidade de keywords;
- alertas do dia;
- total de projetos;
- indicador de Telegram vinculado;
- ativar Pro;
- voltar para Free;
- alterar plano por rota.

Ainda nao existe pagina de detalhe, ativacao/desativacao de conta, exclusao, anonimizacao, reset administrativo de senha ou auditoria estruturada.

## Frontend atual

O frontend usa templates Jinja e CSS proprio em `app/static/css/style.css`, com tema dark azul, cards, metricas, formulario de keywords, tabela de Admin e dashboard. `app/static/js/script.js` controla chamadas JSON, CSRF, flashes, graficos, toggles e atualizacao de dados.

SPB-254 (correcoes funcionais de UI: remocao de keyword em touch, switch de monitoramento acessivel por teclado) **implantado e validado em producao em 20/08/2026**, commit `588b86167f633faab812f23e3fbe0be0d534918c`: `.chip-x` deixou de depender exclusivamente de `:hover` (inutilizavel em touch antes da correcao) e `.switch input` deixou de usar `display:none` (inalcancavel por teclado antes da correcao) — ambos corrigidos somente via CSS, sem mudanca de markup/JS/layout/cor. Deploy: 213/213 testes na VPS, banco integro antes/depois, HTTP saudavel (`HOME`/`LOGIN`/`REGISTER`=200, `ADMIN`=302), cookie `session` preservado, nenhum banner de homologacao, Telegram saudavel, Collector restaurado e `LastTaskResult=0` na rodada pos-deploy. Este foi tambem o primeiro deploy real a exercitar em producao o hotfix de transporte PowerShell -> SSH (ver secao B4 acima): `DEPLOY_STATUS=SUCCESS` com `LOCAL_DEPLOY_EXIT_CODE=0`, sem qualquer ocorrencia de `numeric argument required`.

## Testes atuais

- `tests/test_notifier_queue.py` cobre a fila do notifier, elegibilidade, filtros administrativos e protecao contra starvation.
- Existem probes de scraping em `tests/*_probe.py`.
- `tests/test_services.py` esta vazio no estado atual observado.

## Limitacoes e debito tecnico

- Matching por substring.
- Sem migrations versionadas aplicadas; ha scripts manuais de migracao.
- `migrations/` existe como pasta, mas nao ha arquivos rastreados nela.
- Reset de senha nao implementado.
- Admin limitado.
- Caixa interna de alertas nao existe.
- Entregas por canal nao existem.
- Preferencias de notificacao por canal nao existem.
- Observabilidade ainda depende principalmente de logs.
- SQLite e `NullPool` sao adequados ao beta, mas exigem cuidado com concorrencia.
- O diretorio `backups/` pode aparecer como untracked na VPS: `.gitignore` protege `*.bak`, mas nao ha uma entrada dedicada `backups/` cobrindo outros tipos de arquivo que venham a existir nessa pasta. Avaliar futuramente adicionar `backups/` ao `.gitignore` (nao alterado neste registro, divida pequena).

## Ambiente de homologacao (SPB-263)

Arquitetura definida em `docs/adr/006-ambiente-homologacao-isolado.md`. Nao existe ambiente de homologacao fisico/funcional hoje — producao continua sendo o unico ambiente real em execucao.

Guardrails de codigo da Fase B implantados em producao em 08/08/2026, commit `7e65bd9`:

- B1 — `APP_ENV` (`development`/`homologation`/`production`, resolucao fail-closed), validacao de `DATABASE_URL` antes de `create_engine()`, `SECRET_KEY` obrigatoria e nao-default em `production`/`homologation`.
- B2 — `workers/scheduler.py` recusa iniciar o scheduler de scraping real (`start()`, `start_scheduler()`, toggle de monitoramento do dashboard) e pula a etapa de crawling do pipeline quando `APP_ENV=homologation`, sem bloquear matcher/notifier.

Producao esta configurada com `APP_ENV=production` e mantem `SCHEDULER=0` (arquitetura inalterada: coletor local -> POST `/internal/ingest/projects` -> VPS).

Validacao do deploy B1/B2:

- 32 testes de `tests/test_environment_guardrails.py` e 11 de `tests/test_scheduler_environment_guardrail.py`;
- suite completa em producao: 116/116;
- `py_compile` aprovado;
- `app.db` permaneceu bit a bit inalterado durante os testes e o restart do servico;
- `PRAGMA integrity_check = ok`;
- `PRAGMA foreign_key_check` sem inconsistencias;
- smoke HTTP aprovado apos restart;
- ingest manual pos-deploy aprovado;
- ciclo automatico do coletor aprovado (recebidos=100 -> matcher -> notifier);
- Windows Scheduled Task do coletor terminou com `LastTaskResult=0`.

B3 (isolamento de Telegram: `TELEGRAM_MODE` fail-closed, identity guard via `TELEGRAM_EXPECTED_BOT_ID`/`getMe` lazy/cacheado, toda chamada de rede Telegram centralizada) foi implementado, hardened (commit `18ac2b1` — `set_webhook` passou a sempre enviar `TELEGRAM_WEBHOOK_SECRET` configurado e bloquear registro de webhook sem secret) e teve o isolamento dos proprios testes corrigido (commit `fc3b91c` — o helper de ambiente controlado dos testes de `tests/test_telegram_guardrails.py` nao neutralizava `TELEGRAM_TOKEN`/`TELEGRAM_WEBHOOK_SECRET`/`TELEGRAM_BOT_USERNAME`, permitindo que valores reais ja presentes no processo contaminassem os testes de configuracao "ausente"). **Implantado e validado em producao em 09/08/2026** (commits `0c41b25`, `18ac2b1`, `fc3b91c`; HEAD de producao `fc3b91c`):

- suite completa: 190/190 (`tests.test_telegram_guardrails` isolado: 64/64); `py_compile` aprovado;
- systemd `smartpaybot` ativo, Gunicorn em `127.0.0.1:8000`, Flask `ENV=production`/`DEBUG=False`, scheduler desabilitado por configuracao;
- `TELEGRAM_MODE=production`, identity guard real confirmado (`telegram_ready()=True`, `getMe` validou o token configurado contra `TELEGRAM_EXPECTED_BOT_ID`);
- smoke HTTP aprovado (Home/Login=200); `POST /webhook/telegram` sem secret recusado com 403; `getWebhookInfo` via guard confirmou `WEBHOOK_API_OK=True`, `pending_update_count=0`, `last_error_date=None`; logs sem `Traceback`/`RuntimeError`/`ERROR`/`CRITICAL`, apenas o warning esperado do webhook sem secret;
- banco: `PRAGMA integrity_check=ok`, `PRAGMA foreign_key_check` vazio, intacto durante deploy/testes pre-restart;
- primeiro ciclo automatico do coletor (Windows Scheduled Task `SmartPayBot Collector`) apos a reativacao terminou com `LastTaskResult=0`, pipeline `ingest -> matcher -> notifier` executado sem `Telegram nao esta pronto/seguro`, identity mismatch, `Traceback`, `RuntimeError`, `ERROR` ou `CRITICAL`.

Fase D (inspecao read-only real da VPS) **concluida em 16/08/2026**, sem bloqueadores (detalhes completos em `docs/adr/006-ambiente-homologacao-isolado.md`):

- apenas o clone de producao existe hoje em `/home/deploy/apps/` e apenas `smartpaybot.service` existe no systemd — sem colisao de diretorio/unit com a futura homologacao;
- porta `8001` livre, bind loopback confirmado (`8000`/`8001` acessiveis apenas em `127.0.0.1`);
- UFW ativo (`incoming=deny`, `22`/`80`/`443` liberados), nftables/iptables consistentes; decisao: `8001` nao sera aberta no firewall, homologacao seguira acessivel externamente somente via Nginx em `443`;
- Nginx atual mapeado (producao -> `127.0.0.1:8000`, `nginx -t` OK), ainda sem configuracao para `homolog.smartpaybot.com.br`;
- certificado SSL atual (`smartpaybot.com.br`, valido 17/06/2026-15/09/2026) nao cobre o subdominio de homologacao — certificado dedicado sera emitido na Fase F;
- recursos confirmados compativeis com uma segunda instancia (disco ~6% de uso, RAM ~3,8 GiB total/~3,3 GiB disponivel, swap 0, `load average` 0.00).

B4 (isolamento visual e de sessao: `SESSION_COOKIE_NAME` derivado de `APP_ENV` — "session" em producao/development, "smartpaybot_homolog_session" em homologacao; `SESSION_COOKIE_SECURE` derivado de `APP_ENV` em vez de `FLASK_ENV`; banner "HOMOLOGACAO — AMBIENTE DE TESTES" no header, classe `env-homologation` no body e prefixo `[HOMOLOGACAO]` no `<title>`, todos condicionados somente a `APP_ENV`, nunca a hostname) **implementado, testado, auditado e implantado em producao em 18/08/2026** (horario local do operador; 19/08/2026 UTC na VPS), commit `2625a82`:

- suite completa local: 204/204 (14 testes novos dedicados em `tests/test_homologation_ui_session.py`, incluindo prova de que Host header nao altera banner/cookie); suite completa na VPS antes do restart: 204/204; `py_compile` aprovado;
- auditoria de `login_user()` confirmou ausencia de `remember=True` em qualquer fluxo — nenhum guardrail de `REMEMBER_COOKIE_*` foi necessario neste bloco;
- producao preserva exatamente o cookie legado `"session"` (`Secure`/`HttpOnly`/`SameSite=Lax`/`Path=/`, sem `Domain`), confirmado apos o deploy real — nenhum logout global ocorreu;
- nenhum elemento visual de homologacao (banner, classe `env-homologation`, prefixo `[HOMOLOGACAO]`) apareceu em producao apos o deploy;
- banco integro (`PRAGMA integrity_check=ok`, `foreign_key_check` vazio), servico `active`, smoke HTTP aprovado (`HOME`/`LOGIN`/`REGISTER`=200, `ADMIN`=302), Telegram saudavel (`telegram_ready()=True`, webhook OK apontando para a URL esperada, `pending_update_count=0`), Collector restaurado com `LastTaskResult=0` apos o deploy.

Quatro auditorias profundas adicionais foram concluidas na branch de preparacao do B4 (B4 forense adversarial, UX/UI, arquitetura/seguranca do SPB-263, coletor local) e consolidadas em `docs/phase-2/16-roadmap-mestre.md`, que passa a ser a fonte canonica de prioridade operacional do projeto. A auditoria do coletor identificou, sobre 832 ciclos reais, uma falha silenciosa de coleta (~7,3% dos ciclos com `EXIT_CODE=0` apesar de zero paginas coletadas) como prioridade de confiabilidade; o hardening minimo dessa falha foi concluido no SPB-264. Os proximos passos do trilho do Collector seguem em SPB-265/SPB-266, sem early-stop ou telemetria persistente ainda.

O primeiro deploy real usou a automacao controlada (`scripts/deploy-production.ps1` + `scripts/deploy-production-remote.sh`, ver `docs/runbooks/deploy-producao.md`): o deploy remoto terminou `DEPLOY_STATUS=SUCCESS`, mas um bug de transporte do Windows PowerShell 5.1 (injecao de BOM/CRLF espurios ao enviar o script via pipeline stdin a um processo nativo) corrompeu a ultima linha do script remoto e fez o orquestrador local reportar falsamente um rollback (`exit 2`) que nunca ocorreu — producao permaneceu saudavel durante todo o incidente, confirmado por validacao posterior (`service active`, `HOME`/`LOGIN`=200). Hotfix definitivo (transporte via Base64 + captura dos bytes crus do blob Git via `System.Diagnostics.Process`/`MemoryStream`, decodificado remotamente com `base64 --decode --ignore-garbage`, validado por comparacao de SHA-256 entre o blob original e os bytes reconstruidos) implantado em `main`, commits `ae63112` e `f02faaa`. Nenhum novo deploy foi necessario para aplicar o hotfix (ele corrige o mecanismo local do proximo deploy, nao o estado de producao).

Escopo do SPB-263 que permanece em aberto: SPB-271 (guardrail de URL em `set_webhook`), SPB-272 (hardening de isolamento pre-Fase E) e as Fases E-I da ADR-006 (clone/systemd/porta 8001, DNS/Nginx/SSL, protecao externa + noindex, matriz de isolamento/smoke, fechamento documental). SPB-270 ja foi implantado e validado em producao; a Fase E segue dependendo de SPB-272 e dos gates operacionais em `docs/phase-2/16-roadmap-mestre.md`.

## Incidentes resolvidos

1. Coletor parou apos mudanca de `C:` para `D:`.
2. Runner local tinha caminho absoluto.
3. Tarefa do Windows apontava para caminho antigo.
4. Notifier sofria starvation por usuario sem `chat_id`.
5. Usuario teste e backlog historico foram tratados.
6. Tarefa passou para frequencia de 10 minutos.
7. Telegram foi validado com envio controlado.

## Bug aberto

`excel` corresponde indevidamente a `excelente`, pois o matcher atual usa substring normalizada.
