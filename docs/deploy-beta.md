# SmartPayBot — Plano de Deploy Beta

Checklist operacional para o primeiro deploy público.
Baseado na auditoria de produção realizada em 2026-06.

**Legenda:**
- `[OBRIG]` — bloqueia o deploy. Não subir sem isso.
- `[RECOM]` — não bloqueia, mas risco real se omitido.
- `[FUTURO]` — pode esperar até o produto crescer.

**Esforço estimado total (obrigatórios):** ~3–4 horas numa VPS nova

---

## Fase 0 — Segurança pré-deploy
*Fazer antes de qualquer push ou configuração de servidor.*

- [ ] `[OBRIG]` **Rotacionar SECRET_KEY** — o valor atual foi exposto em sessão de IA  
  ```powershell
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
  Substituir em `.env`. **Nunca commitar o .env.**  
  ⏱ 2 min

- [ ] `[OBRIG]` **Rotacionar TELEGRAM_TOKEN** — o token atual foi exposto em sessão de IA  
  Acessar `@BotFather` no Telegram → `/revoke` → gerar novo token → substituir em `.env`  
  ⏱ 5 min

- [ ] `[OBRIG]` **Confirmar que `.env` não está no git**  
  ```powershell
  git log --all --full-history -- .env
  git ls-files .env
  ```
  Ambos devem retornar vazio. Se não, seguir `rules/seguranca.md`.  
  ⏱ 2 min

---

## Fase 1 — Provisionar o VPS
*Hostinger VPS — Ubuntu 22.04 LTS. Mínimo: 1 vCPU / 1 GB RAM.*

- [ ] `[OBRIG]` **Apontar DNS** — registro A do domínio (ex: `smartpaybot.com.br`) para o IP da VPS  
  Propagação pode levar até 24h; fazer primeiro.  
  ⏱ 5 min (+ propagação)

- [ ] `[OBRIG]` **Instalar dependências do sistema**  
  ```bash
  sudo apt update && sudo apt install -y \
    python3.11 python3.11-venv python3.11-dev \
    nginx certbot python3-certbot-nginx \
    git build-essential
  ```
  ⏱ 5–10 min

- [ ] `[OBRIG]` **Clonar o projeto e criar virtualenv**  
  ```bash
  git clone <repositório> /var/www/smartpaybot
  cd /var/www/smartpaybot
  python3.11 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
  ```
  ⏱ 5 min

- [ ] `[OBRIG]` **Criar `.env` de produção na VPS**  
  Copiar `.env.example` e preencher todos os valores reais:
  ```bash
  cp .env.example .env
  nano .env
  ```
  Variáveis críticas:
  ```ini
  FLASK_ENV=production
  SECRET_KEY=<novo valor gerado na Fase 0>
  TELEGRAM_TOKEN=<novo token da Fase 0>
  DATABASE_URL=sqlite:////var/www/smartpaybot/app.db
  SCHEDULER=1
  SCAN_MIN_SECONDS=180
  LOG_LEVEL=INFO
  ```
  ⏱ 10 min

- [ ] `[RECOM]` **Criar usuário de sistema dedicado** (não rodar como root)  
  ```bash
  sudo useradd -m -s /bin/bash smartpaybot
  sudo chown -R smartpaybot:smartpaybot /var/www/smartpaybot
  ```
  ⏱ 5 min

---

## Fase 2 — Banco de dados e seed
*Feito uma única vez. Sem Alembic ainda — criação manual.*

- [ ] `[OBRIG]` **Criar tabelas no banco de produção**  
  ```bash
  cd /var/www/smartpaybot
  FLASK_ENV=development .venv/bin/python -c "
  from infrastructure.db import init_db
  init_db(create_all=True)
  print('Tabelas criadas.')
  "
  ```
  > Nota: `FLASK_ENV=development` é necessário aqui para que `create_all=True` seja executado.
  > Após a criação, alterar de volta para `production` no `.env`.  
  ⏱ 2 min

- [ ] `[OBRIG]` **Rodar seed de planos**  
  Sem isso, toda lógica de Free/Pro falha silenciosamente.  
  ```bash
  .venv/bin/python scripts/seed_plans.py
  ```
  ⏱ 1 min

- [ ] `[OBRIG]` **Criar usuário admin**  
  ```bash
  .venv/bin/python scripts/create_master.py
  ```
  ⏱ 2 min

- [ ] `[RECOM]` **Verificar que o banco foi criado corretamente**  
  ```bash
  .venv/bin/python -c "
  from infrastructure.db import SessionLocal
  from domain.models import Plan
  with SessionLocal() as db:
      plans = db.query(Plan).all()
      print('Planos:', [(p.name, p.max_keywords) for p in plans])
  "
  ```
  Deve retornar Free e Pro com os limites corretos.  
  ⏱ 2 min

---

## Fase 3 — Gunicorn (servidor WSGI)
*O Flask dev server (`python run.py`) é PROIBIDO em produção.*

- [ ] `[OBRIG]` **Criar arquivo de serviço systemd**  
  ```bash
  sudo nano /etc/systemd/system/smartpaybot.service
  ```
  Conteúdo:
  ```ini
  [Unit]
  Description=SmartPayBot Flask App
  After=network.target

  [Service]
  User=smartpaybot
  Group=smartpaybot
  WorkingDirectory=/var/www/smartpaybot
  EnvironmentFile=/var/www/smartpaybot/.env
  ExecStart=/var/www/smartpaybot/.venv/bin/gunicorn \
      --workers 1 \
      --threads 2 \
      --bind 127.0.0.1:8000 \
      --timeout 120 \
      --access-logfile /var/log/smartpaybot/access.log \
      --error-logfile /var/log/smartpaybot/error.log \
      "run:app"
  Restart=always
  RestartSec=5

  [Install]
  WantedBy=multi-user.target
  ```
  > **`--workers 1` é obrigatório.** O APScheduler usa threading lock por processo.
  > Com 2+ workers, o pipeline roda N vezes em paralelo e dispara alertas duplicados.  
  ⏱ 10 min

- [ ] `[OBRIG]` **Criar diretório de logs e habilitar o serviço**  
  ```bash
  sudo mkdir -p /var/log/smartpaybot
  sudo chown smartpaybot:smartpaybot /var/log/smartpaybot
  sudo systemctl daemon-reload
  sudo systemctl enable smartpaybot
  sudo systemctl start smartpaybot
  sudo systemctl status smartpaybot
  ```
  ⏱ 5 min

---

## Fase 4 — Nginx + HTTPS
*O Telegram exige HTTPS para webhooks. Sem isso, vinculação via bot não funciona em produção.*

- [ ] `[OBRIG]` **Criar configuração Nginx**  
  ```bash
  sudo nano /etc/nginx/sites-available/smartpaybot
  ```
  Conteúdo (substituir `seudominio.com.br`):
  ```nginx
  server {
      listen 80;
      server_name seudominio.com.br www.seudominio.com.br;

      location / {
          proxy_pass http://127.0.0.1:8000;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_read_timeout 120s;
      }

      location /static/ {
          alias /var/www/smartpaybot/app/static/;
          expires 7d;
          add_header Cache-Control "public, immutable";
      }
  }
  ```
  ```bash
  sudo ln -s /etc/nginx/sites-available/smartpaybot /etc/nginx/sites-enabled/
  sudo nginx -t
  sudo systemctl reload nginx
  ```
  ⏱ 10 min

- [ ] `[OBRIG]` **Instalar certificado Let's Encrypt**  
  ```bash
  sudo certbot --nginx -d seudominio.com.br -d www.seudominio.com.br
  ```
  Certbot reescreve o Nginx config automaticamente para HTTPS + redirect.  
  ⏱ 5 min

---

## Fase 5 — Telegram webhook de produção

- [ ] `[OBRIG]` **Gerar o secret de autenticação do webhook**  
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```
  Copiar o valor gerado e adicionar ao `.env` de produção:
  ```ini
  TELEGRAM_WEBHOOK_SECRET=<valor gerado acima>
  ```
  Este secret é enviado pelo Telegram em cada requisição no header
  `X-Telegram-Bot-Api-Secret-Token`. O app rejeita qualquer POST sem ele.  
  ⏱ 2 min

- [ ] `[OBRIG]` **Registrar o webhook com secret_token**  
  Após HTTPS ativo e `TELEGRAM_WEBHOOK_SECRET` no `.env`:
  ```bash
  .venv/bin/python -c "
  from infrastructure.config import get_settings
  from infrastructure.telegram import set_webhook
  s = get_settings()
  ok = set_webhook(
      'https://seudominio.com.br/webhook/telegram',
      drop_pending=True,
      secret_token=s.TELEGRAM_WEBHOOK_SECRET,
  )
  print('Webhook registrado.' if ok else 'FALHA — ver logs.')
  "
  ```
  Sem `secret_token` o Telegram não envia o header e o app retorna 403.  
  ⏱ 2 min

- [ ] `[OBRIG]` **Verificar que o webhook está ativo e com secret**  
  ```bash
  curl -s "https://api.telegram.org/bot<TOKEN>/getWebhookInfo" | python3 -m json.tool
  ```
  Conferir: `url` correto, `has_custom_certificate: false`, `pending_update_count: 0`.
  O campo `secret_token` não é retornado pela API (por segurança) — a ausência é normal.  
  ⏱ 2 min

- [ ] `[RECOM]` **Testar que requisições sem secret são rejeitadas**  
  ```bash
  # Deve retornar 403
  curl -s -o /dev/null -w "%{http_code}" \
    -X POST https://seudominio.com.br/webhook/telegram \
    -H "Content-Type: application/json" \
    -d '{"message":{"text":"/start abc","chat":{"id":999}}}'
  # Esperado: 403

  # Deve retornar 200 (com secret correto)
  curl -s -o /dev/null -w "%{http_code}" \
    -X POST https://seudominio.com.br/webhook/telegram \
    -H "Content-Type: application/json" \
    -H "X-Telegram-Bot-Api-Secret-Token: <seu secret>" \
    -d '{"message":{"text":"/start abc","chat":{"id":999}}}'
  # Esperado: 200
  ```
  ⏱ 3 min

---

## Fase 6 — Segurança pós-deploy

- [x] ~~`[RECOM]` **Autenticação no webhook Telegram**~~ — implementado. Ver Fase 5.

- [ ] `[RECOM]` **Implementar rate limiting no login/registro**  
  Instalar `flask-limiter` e limitar `/auth/login` (10/min) e `/auth/register` (5/hora).  
  ⏱ 30 min (requer implementação de código)

- [x] ~~`[RECOM]` **Cookies de sessão seguros**~~ — implementado em `app/__init__.py`.  
  `SECURE=True` quando `FLASK_ENV=production` (requer HTTPS); `HTTPONLY` e `SAMESITE=Lax` sempre ativos.  
  Nenhuma variável de ambiente adicional necessária.

- [ ] `[FUTURO]` Configurar logrotate para `/var/log/smartpaybot/`
- [ ] `[FUTURO]` Backup diário do `app.db` via cron
- [ ] `[FUTURO]` Monitoramento de erros (Sentry)
- [ ] `[FUTURO]` Migrar para PostgreSQL quando >20 usuários ativos
- [ ] `[FUTURO]` Alembic para migrations versionadas (obrigatório antes do primeiro ALTER TABLE em produção)

---

## Fase 7 — Verificação final (smoke test)

- [ ] `[OBRIG]` **Health check**  
  ```bash
  curl https://seudominio.com.br/healthz
  # Esperado: {"status": "ok"}
  ```

- [ ] `[OBRIG]` **Landing page acessível**  
  ```bash
  curl -I https://seudominio.com.br/
  # Esperado: HTTP/2 200
  ```

- [ ] `[OBRIG]` **Fluxo de cadastro funcional**  
  Criar uma conta de teste via browser → ver dashboard → sem erros 500.

- [ ] `[OBRIG]` **Vinculação Telegram funcional**  
  Adicionar keyword → usar link do Telegram no dashboard → enviar `/start <codigo>` no bot → confirmar que o card atualiza automaticamente.

- [ ] `[OBRIG]` **Pipeline rodando**  
  ```bash
  sudo journalctl -u smartpaybot -f
  ```
  Aguardar 3–5 min. Deve aparecer: `crawl_once`, `match_recent_projects`, `notify_pending`.

- [ ] `[RECOM]` **Painel admin acessível**  
  Acessar `/admin/` com o usuário master → ver lista de usuários → confirmar planos.

---

## Referência rápida — variáveis de ambiente obrigatórias

| Variável | Descrição | Valor de produção |
|---|---|---|
| `FLASK_ENV` | Modo da aplicação | `production` |
| `SECRET_KEY` | Assinatura de sessão | 64 hex chars, único, secreto |
| `TELEGRAM_TOKEN` | Token do bot | Gerado pelo @BotFather |
| `DATABASE_URL` | URL do banco | `sqlite:////var/www/smartpaybot/app.db` |
| `SCHEDULER` | Ligar pipeline | `1` |
| `SCAN_MIN_SECONDS` | Intervalo entre ciclos | `180` (3 min mínimo) |
| `LOG_LEVEL` | Verbosidade dos logs | `INFO` |
| `CSRF_ENABLED` | Proteção de formulários | `true` |

---

## Riscos ativos no deploy (para ciência)

| Risco | Severidade | Status |
|---|---|---|
| APScheduler explode com >1 Gunicorn worker | Crítico | Mitigado por `--workers 1` |
| Webhook sem autenticação | Alto | `TELEGRAM_WEBHOOK_SECRET` + 403 | ✅ Mitigado |
| SQLite sob escrita concorrente (APScheduler + Flask) | Médio | Aceito para beta pequeno |
| Sem rate limiting em `/auth/login` | Médio | Aberto — fase 6 pendente |
| Sem rotação de logs | Baixo | Aceito para beta curto |

---

*Documento criado em 2026-06. Revisar antes de qualquer migração para PostgreSQL.*
