# SmartPayBot — Arquitetura SaaS

## Estado atual (branch `dev`)

### Stack

| Componente | Tecnologia | Observação |
|---|---|---|
| Framework | Flask 3.x | Blueprint-based |
| ORM | SQLAlchemy 2.x (`Mapped[]`) | Typed, moderno |
| DB (dev) | SQLite `app.db` | Adequado para dev/beta |
| DB (prod) | PostgreSQL | A migrar |
| Scheduler | APScheduler in-process | Ponto frágil (ver riscos) |
| Scraping | lxml + httpx async | Funcional, não alterar |
| Alertas | Telegram Bot API (REST) | Com retry exponencial |
| Auth | Flask-Login + Werkzeug hashes | OK para o volume atual |
| CSRF | Flask-WTF | Ativo |
| Planos | Free/Pro (DB) + admin manual | Implementado |
| Pagamentos | — | Futuro: Stripe |
| Migrations | `create_all` em dev | Risco: migrar para Alembic |

---

## Estrutura de pastas

```
SmartPayBot/
├── app/                        # Camada de apresentação (Flask)
│   ├── __init__.py             # Factory create_app()
│   ├── blueprints.py           # (vazio, registro em routes/__init__.py)
│   ├── decorators.py           # admin_required, plan_required
│   ├── forms.py                # WTForms
│   ├── security.py             # AppUser (Flask-Login UserMixin)
│   ├── routes/
│   │   ├── __init__.py         # register_blueprints()
│   │   ├── auth.py             # /auth/login, /auth/register, /auth/logout
│   │   ├── dashboard.py        # /dashboard/* + API JSON
│   │   ├── admin.py            # /admin/ (listar usuários, alterar plano)
│   │   └── webhook_telegram.py # /webhook/telegram (vinculação de chat)
│   ├── static/                 # CSS, JS, imagens
│   └── templates/              # Jinja2 (base, dashboard, admin, auth...)
│
├── domain/                     # Lógica de negócio (sem Flask)
│   ├── models.py               # User, UserKeyword, ProjectGlobal,
│   │                           # ProjectPerUser, Plan, Subscription,
│   │                           # UserAlertDaily
│   ├── repositories.py         # Queries SQLAlchemy (sem regras de negócio)
│   └── services/
│       ├── keywords_service.py # Normalização de texto e keywords
│       ├── telegram_link_service.py # Geração/invalidação de link codes
│       ├── projects_service.py # Upsert global, fanout por usuário
│       └── plan_service.py     # Planos, limites, set_user_plan
│
├── infrastructure/             # Adaptadores externos
│   ├── config.py               # Settings (dataclass + dotenv)
│   ├── db.py                   # Engine, SessionLocal, init_db()
│   ├── logging.py              # configure_logging(), get_logger()
│   ├── telegram.py             # send_message(), webhooks
│   ├── scraping.py             # HttpClient async, parsers 99Freelas
│   └── timeutils.py            # fmt_br()
│
├── workers/                    # Pipeline de background
│   ├── ingestor.py             # crawl_once() — scraping assíncrono
│   ├── matcher.py              # match_recent_projects() — fanout por keyword
│   ├── notifier.py             # notify_pending() — enriquece e envia
│   └── scheduler.py            # APScheduler — orquestra o pipeline
│
├── scripts/                    # Ferramentas de operação
│   ├── bootstrap_db.py         # Redefinir senha de usuário
│   ├── create_master.py        # Criar usuário admin
│   ├── dump_users.py           # Exportar usuários
│   └── seed_plans.py           # Popular tabela plans
│
├── docs/                       # Documentação do projeto
├── rules/                      # Regras de desenvolvimento
├── prompts/                    # Templates de prompt para Claude
├── tests/                      # Testes (a implementar)
├── .env                        # Segredos locais (nunca versionar)
├── .env.example                # Template público (a criar)
├── CLAUDE.md                   # Contexto para Claude Code
└── run.py                      # Entrypoint
```

---

## Pipeline crítico (NÃO ALTERAR sem revisão)

```
APScheduler (intervalo configurável)
    └─► _pipeline_tick()
            ├─► crawl_once(pages=N)          [ingestor.py]
            │       └─► upsert projects_global
            ├─► match_recent_projects()       [matcher.py]
            │       └─► fanout → projects_per_user
            └─► notify_pending()              [notifier.py]
                    ├─► check can_receive_alert_today  [plan_service]
                    ├─► enrich (detalhe + listagem)
                    └─► send_message() via Telegram
```

---

## Modelo de dados

```
plans ──────────────────────────────────────────────┐
  id, slug, name, max_keywords, max_alerts_day       │
                                                     │
users                                                │
  id, username, email, password_hash                 │
  is_admin, is_subscriber (flag legada)              │
  chat_id, telegram_link_code                        │
  │                                                  │
  ├── user_keywords (1:N)                            │
  │     id, keyword                                  │
  │                                                  │
  ├── subscriptions (1:1)  ──────────────────────────┘
  │     id, plan_id, status, expires_at
  │
  ├── user_alerts_daily (1:N)
  │     id, date, alerts_sent
  │
  └── projects_per_user (1:N)
        id, global_project_id, link, title
        matched_keyword, notified_at, notify_attempts
        won, won_cents, won_at

projects_global (global, deduplicado por project_id)
  id, project_id (único), title, link
  published_at, first_seen_at
```

---

## Riscos técnicos atuais

| Risco | Impacto | Mitigação |
|---|---|---|
| APScheduler in-process | Em multi-worker (Gunicorn), pipeline dispara N vezes em paralelo | Usar 1 worker OU migrar para Celery Beat/Redis JobStore |
| SQLite em produção | Sem concorrência real, corrompível | Migrar para PostgreSQL antes de escalar |
| Sem Alembic | Schema muda com `create_all`, sem rollback | Implementar Alembic antes do primeiro deploy em prod |
| Token Telegram no `.env` | Vazamento = bot comprometido | Jamais versionar `.env`; rotacionar token se exposto |
| Bot toggle global | Um usuário pode desligar o pipeline para todos | Remover controle global do dashboard multiusuário |
| Sem rate limiting | Força bruta em /auth/login | Implementar Flask-Limiter + Redis |

---

## Próximos passos técnicos (por prioridade)

1. **Alembic** — migrations controladas (pré-requisito para produção).
2. **PostgreSQL** — trocar `DATABASE_URL` em produção.
3. **Stripe** — Checkout + webhooks para automação de cobrança.
4. **Rate limiting** — Flask-Limiter nas rotas de auth.
5. **Scheduler externo** — APScheduler com Redis JobStore ou processo dedicado.
6. **Testes** — `conftest.py` + banco de teste real + cobertura mínima de serviços.
7. **`.env.example`** — template público sem segredos.
8. **CI/CD** — `.github/workflows/deploy.yml` (atualmente vazio).
