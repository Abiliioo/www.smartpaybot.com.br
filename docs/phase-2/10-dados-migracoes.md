# Dados e migracoes

## Schema atual

Tabelas atuais confirmadas:

- `users`;
- `user_keywords`;
- `projects_global`;
- `projects_per_user`;
- `plans`;
- `subscriptions`;
- `user_alerts_daily`.

## Criacao e migracao atual

`infrastructure/db.py` expoe `init_db(create_all=False)`. Em desenvolvimento, `run.py` chama `init_db(create_all=(settings.FLASK_ENV == "development"))`.

Ha scripts manuais:

- `scripts/migrate_bot_active.py`;
- `scripts/migrate_add_project_meta.py`;
- `scripts/seed_plans.py`.

A pasta `migrations/` existe, mas nao possui arquivos rastreados observados.

## Mudancas propostas

Possiveis tabelas:

- `password_reset_tokens`;
- `admin_audit_events`;
- `notification_deliveries`;
- `user_notification_preferences`.

Possiveis campos:

- `projects_per_user.read_at`;
- `projects_per_user.archived_at`;
- `projects_per_user.dismissed_at`;
- `users.is_active`;
- `users.disabled_at`;
- `users.last_login_at`.

## Riscos

- SQLite limita concorrencia.
- `ALTER TABLE` em SQLite tem restricoes.
- Migracoes manuais sao dificeis de reverter.
- Backlog antigo pode distorcer dados ao introduzir inbox.
- `notified_at` pode ficar ambiguo quando houver varios canais.

## Estrategia recomendada

1. Backup antes de qualquer mudanca de schema.
2. Criar migracoes incrementais e reversiveis.
3. Separar mudancas de schema de mudancas de comportamento quando possivel.
4. Validar contagem antes/depois.
5. Manter compatibilidade com campos antigos.
6. Testar rollback em copia local.

## Criterios futuros para PostgreSQL

Migrar quando houver:

- crescimento de usuarios ativos;
- necessidade de concorrencia real;
- fila com claim/lock transacional;
- consultas administrativas pesadas;
- metricas operacionais historicas;
- multiplos workers/processos;
- risco operacional alto em SQLite.

## Rollback de dados

Para cada migracao:

- comando de backup;
- verificacao de integridade;
- plano de reversao;
- criterio de abortar;
- smoke test pos-migracao.
