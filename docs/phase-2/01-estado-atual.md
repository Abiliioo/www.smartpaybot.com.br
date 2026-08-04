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

`app/routes/admin.py` e `app/templates/admin.html` entregam:

- listagem simples de usuarios;
- plano atual;
- data de subscription;
- quantidade de keywords;
- alertas do dia;
- total de projetos;
- indicador de Telegram vinculado;
- ativar Pro;
- voltar para Free;
- alterar plano por rota.

Ainda nao existe busca, filtros, pagina de detalhe, ativacao/desativacao de conta, exclusao, anonimizacao, reset administrativo de senha ou auditoria estruturada.

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
