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

O scheduler interno da VPS esta documentado como desativado operacionalmente, embora o codigo ainda tenha `workers/scheduler.py` e possa iniciar quando `SCHEDULER=1`.

## Fluxo de ingestao

`app/routes/ingest.py` registra o blueprint `/internal` e a rota `POST /ingest/projects`.

A rota:

- exige header `X-Internal-Ingest-Token` quando `INTERNAL_INGEST_TOKEN` esta configurado;
- recusa ingestao sem token em `FLASK_ENV=production`;
- aceita payload `{"projects": [...]}`;
- valida `project_id`, `title` e `link`;
- coage campos opcionais de metadados;
- faz upsert em `projects_global`;
- dispara uma thread daemon para `match_recent_projects()` e `notify_pending()` quando houve insercao ou atualizacao.

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

Escopo do SPB-263 que permanece em aberto: criacao fisica do ambiente de homologacao (`homolog.smartpaybot.com.br`, Fases D-I da ADR-006) e o proximo bloco de guardrails, **B4 — isolamento visual e de sessao da homologacao** (cookie/sessao separado, banner global de "HOMOLOGACAO", diferenciacao visual inequivoca de producao), ainda nao iniciado.

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
