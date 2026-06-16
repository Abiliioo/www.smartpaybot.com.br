# SmartPayBot — Guia Operacional de Deploy na VPS

Guia de execução direta para o primeiro deploy beta.
**Hostinger KVM · Ubuntu 24.04 LTS · Python 3.12 · Gunicorn + Nginx + Systemd**

> Substitua `seudominio.com.br` e `<URL_DO_REPO>` pelos valores reais antes de começar.
> Execute via SSH como `root` salvo quando indicado o contrário.

---

## Checklist cronológico

| Tempo estimado | Etapa |
|---|---|
| T+0 | Apontar DNS e verificar propagação |
| T+5 | SSH na VPS, atualizar sistema |
| T+15 | Instalar dependências de sistema |
| T+20 | Criar usuário, estrutura de diretórios, clonar projeto |
| T+30 | Criar `.env`, virtualenv, instalar dependências pip |
| T+45 | Criar banco, seed de planos, criar admin |
| T+55 | Criar e iniciar serviço systemd (Gunicorn) |
| T+65 | Configurar Nginx |
| T+75 | Certificado HTTPS (Let's Encrypt) |
| T+85 | Registrar webhook Telegram |
| T+90 | Smoke tests |
| T+100 | Backup inicial e cron diário |

---

## Bloco 0 — Antes de conectar à VPS (máquina local)

```powershell
# Confirmar que está na branch de produção
git checkout main
git status                        # deve estar limpo
git log --oneline -3              # confirmar último commit

# Confirmar que .env não está versionado
git ls-files .env                 # deve retornar vazio
git ls-files .env.example         # deve retornar .env.example

# Enviar código para o repositório remoto
git push origin main
```

---

## Bloco 1 — Acesso e atualização do sistema (T+5)

```bash
# Conectar via SSH (IP e senha root disponíveis no painel Hostinger)
ssh root@<IP_DA_VPS>

# Verificar versão do Ubuntu (ajustar comandos se diferente de 24.04)
lsb_release -a
# Esperado: Ubuntu 24.04.x LTS

# Atualizar pacotes
apt update && apt upgrade -y

# Definir fuso horário
timedatectl set-timezone America/Sao_Paulo
timedatectl status                # confirmar: Time zone: America/Sao_Paulo
```

---

## Bloco 2 — Dependências de sistema (T+15)

```bash
apt install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    nginx \
    certbot \
    python3-certbot-nginx \
    git \
    build-essential \
    sqlite3 \
    curl

# Verificar versões
python3.12 --version              # Python 3.12.x
nginx -v                          # nginx/1.x.x
git --version
```

> **Nota — lxml em arquiteturas ARM ou sem wheel disponível:**
> Se `pip install -r requirements.txt` falhar com erro de compilação do `lxml`,
> instalar as bibliotecas de desenvolvimento antes de repetir o pip:
> ```bash
> apt install -y libxml2-dev libxslt1-dev
> ```
> Em VPS x86_64 padrão (Hostinger KVM) isso não é necessário — o pip usa wheel pré-compilado.

---

## Bloco 3 — Usuário e estrutura de diretórios (T+20)

```bash
# Criar usuário dedicado (app nunca roda como root)
useradd -m -s /bin/bash smartpaybot

# Criar diretórios auxiliares
mkdir -p /var/www/smartpaybot
mkdir -p /var/log/smartpaybot
mkdir -p /var/www/smartpaybot/backups

# Clonar o projeto na branch de produção
git clone --branch main <URL_DO_REPO> /var/www/smartpaybot

# Transferir propriedade para o usuário dedicado
chown -R smartpaybot:smartpaybot /var/www/smartpaybot
chown -R smartpaybot:smartpaybot /var/log/smartpaybot

# Confirmar estrutura
ls -la /var/www/smartpaybot/
```

### Estrutura de diretórios esperada após o clone

```
/var/www/smartpaybot/
├── app/
│   ├── routes/
│   ├── static/
│   │   ├── css/
│   │   ├── images/     ← favicon.ico e logos aqui
│   │   └── js/
│   └── templates/
├── domain/
├── infrastructure/
├── workers/
├── scripts/
├── docs/
├── .env.example        ← rastreado no git
├── requirements.txt
├── run.py
└── .venv/              ← criado na próxima etapa (não no git)

/var/log/smartpaybot/
├── access.log          ← criado automaticamente pelo Gunicorn
└── error.log

/var/www/smartpaybot/backups/
└── (vazio — populado pelo cron e por backups manuais)
```

---

## Bloco 4 — Virtualenv e dependências Python (T+25)

```bash
cd /var/www/smartpaybot

# Criar virtualenv como usuário smartpaybot
sudo -u smartpaybot python3.12 -m venv .venv

# Instalar dependências
sudo -u smartpaybot .venv/bin/pip install --upgrade pip
sudo -u smartpaybot .venv/bin/pip install -r requirements.txt

# Confirmar que gunicorn foi instalado
sudo -u smartpaybot .venv/bin/gunicorn --version
# Esperado: gunicorn (version 26.0.0)
```

> Se o `pip install` falhar ao compilar `lxml`, ver nota de `libxml2-dev` no Bloco 2.

---

## Bloco 5 — Arquivo `.env` de produção (T+30)

```bash
cd /var/www/smartpaybot

# Criar .env a partir do exemplo
sudo -u smartpaybot cp .env.example .env
sudo -u smartpaybot nano .env
```

Preencher com os valores reais — todos os campos `<valor>` são obrigatórios:

```ini
# ── Flask ──────────────────────────────────────────────────────────────
FLASK_ENV=production

# Gere com: python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=<64-hex-chars-aleatorios>

# ── Banco de dados ─────────────────────────────────────────────────────
# 4 barras: 3 do protocolo + 1 do caminho absoluto
DATABASE_URL=sqlite:////var/www/smartpaybot/app.db

# ── Telegram ───────────────────────────────────────────────────────────
TELEGRAM_TOKEN=<token-novo-do-botfather>
TELEGRAM_BOT_USERNAME=<username-do-bot-sem-arroba>

# Gere com: python3 -c "import secrets; print(secrets.token_hex(32))"
TELEGRAM_WEBHOOK_SECRET=<64-hex-chars-aleatorios>

# ── Scheduler ──────────────────────────────────────────────────────────
SCHEDULER=1
SCAN_MIN_SECONDS=180
SCAN_MAX_SECONDS=360
SCAN_PAGES=10

# ── Segurança ──────────────────────────────────────────────────────────
CSRF_ENABLED=true
SHOW_WEBHOOK_PANEL=0

# ── Fuso horário e logs ────────────────────────────────────────────────
TZ_NAME=America/Sao_Paulo
LOG_LEVEL=INFO
```

**Proteger o arquivo:**
```bash
chmod 600 /var/www/smartpaybot/.env
chown smartpaybot:smartpaybot /var/www/smartpaybot/.env

# Confirmar que os campos críticos estão preenchidos (não devem conter <valor>)
grep -E "^SECRET_KEY=|^TELEGRAM_TOKEN=|^TELEGRAM_WEBHOOK_SECRET=" /var/www/smartpaybot/.env
```

---

## Bloco 6 — Banco de dados, seed e admin (T+45)

> **ATENÇÃO:** executar ANTES de iniciar o serviço systemd.

```bash
cd /var/www/smartpaybot

# Criar tabelas (FLASK_ENV=development força create_all=True)
sudo -u smartpaybot FLASK_ENV=development .venv/bin/python -c "
from infrastructure.db import init_db
init_db(create_all=True)
print('Tabelas criadas.')
"

# Seed dos planos Free/Pro — obrigatório, sem isso a lógica de planos falha
sudo -u smartpaybot .venv/bin/python scripts/seed_plans.py

# Criar usuário admin
sudo -u smartpaybot .venv/bin/python scripts/create_master.py

# Verificar banco
sudo -u smartpaybot .venv/bin/python -c "
from infrastructure.db import SessionLocal
from domain.models import Plan, User
with SessionLocal() as db:
    plans = db.query(Plan).all()
    admins = db.query(User).filter_by(is_admin=True).count()
    print('Planos:', [(p.name, p.max_keywords) for p in plans])
    print('Admins:', admins)
"
# Esperado:
# Planos: [('Free', 3), ('Pro', None)]
# Admins: 1

# Confirmar que o arquivo do banco foi criado
ls -lh /var/www/smartpaybot/app.db
```

---

## Bloco 7 — Serviço systemd / Gunicorn (T+55)

```bash
nano /etc/systemd/system/smartpaybot.service
```

Colar o conteúdo abaixo:

```ini
[Unit]
Description=SmartPayBot — Alertas de freelas via Telegram
After=network.target
Wants=network-online.target

[Service]
Type=exec
User=smartpaybot
Group=smartpaybot
WorkingDirectory=/var/www/smartpaybot

# Carrega todas as variáveis do .env no processo
EnvironmentFile=/var/www/smartpaybot/.env

# --workers 1 É OBRIGATÓRIO.
# O APScheduler usa threading.Lock por processo.
# Com 2+ workers o pipeline roda em paralelo e gera alertas duplicados.
ExecStart=/var/www/smartpaybot/.venv/bin/gunicorn \
    --workers 1 \
    --threads 2 \
    --worker-class sync \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 5 \
    --access-logfile /var/log/smartpaybot/access.log \
    --error-logfile /var/log/smartpaybot/error.log \
    --log-level info \
    "run:app"

Restart=on-failure
RestartSec=5
StartLimitInterval=60
StartLimitBurst=3

NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

```bash
# Habilitar e iniciar
systemctl daemon-reload
systemctl enable smartpaybot
systemctl start smartpaybot

# Aguardar 5 segundos e verificar
sleep 5
systemctl status smartpaybot
# Esperado: active (running)

# Acompanhar logs por 30 segundos
journalctl -u smartpaybot -n 50 --no-pager
# Deve conter: "Flask app criado. ENV=production"
```

---

## Bloco 8 — Nginx (T+65)

```bash
# Remover site padrão do Nginx
rm -f /etc/nginx/sites-enabled/default

# Criar configuração do SmartPayBot
nano /etc/nginx/sites-available/smartpaybot
```

Colar o conteúdo abaixo (substituir `seudominio.com.br`):

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name seudominio.com.br www.seudominio.com.br;

    # Bloquear acesso a arquivos sensíveis
    location ~ /\.(env|git|venv) {
        deny all;
        return 404;
    }

    # Arquivos estáticos servidos diretamente (sem passar pelo Gunicorn)
    location /static/ {
        alias   /var/www/smartpaybot/app/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location = /favicon.ico {
        alias      /var/www/smartpaybot/app/static/images/favicon.ico;
        access_log off;
        log_not_found off;
    }

    # Tudo o mais passa pelo Gunicorn
    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;

        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        proxy_read_timeout    120s;
        proxy_connect_timeout 10s;
        proxy_send_timeout    60s;
        proxy_buffering       off;
    }
}
```

```bash
# Ativar site e testar configuração
ln -s /etc/nginx/sites-available/smartpaybot /etc/nginx/sites-enabled/
nginx -t
# Esperado: syntax is ok / test is successful

systemctl reload nginx
```

---

## Bloco 9 — Certificado HTTPS / Let's Encrypt (T+75)

> **Pré-requisito:** DNS propagado. Verificar antes:
> ```bash
> nslookup seudominio.com.br
> # Deve retornar o IP da VPS
> ```

```bash
# Emitir certificado e reescrever Nginx automaticamente para HTTPS
certbot --nginx \
    -d seudominio.com.br \
    -d www.seudominio.com.br \
    --agree-tos \
    --no-eff-email \
    --email seuemail@exemplo.com

# Certbot vai:
# 1. Obter certificado válido
# 2. Reescrever o Nginx adicionando listen 443 ssl
# 3. Adicionar redirect 301 HTTP → HTTPS
# 4. Configurar renovação automática via systemd timer

# Verificar HTTPS
curl -I https://seudominio.com.br/
# Esperado: HTTP/2 200

# Verificar redirect HTTP → HTTPS
curl -I http://seudominio.com.br/
# Esperado: 301 → https://

# Verificar renovação automática
certbot renew --dry-run
# Esperado: All simulated renewals succeeded
```

---

## Bloco 10 — Webhook Telegram (T+85)

```bash
cd /var/www/smartpaybot

# Registrar webhook com autenticação por secret
sudo -u smartpaybot .venv/bin/python -c "
from infrastructure.config import get_settings
from infrastructure.telegram import set_webhook
s = get_settings()
print('Secret configurado:', bool(s.TELEGRAM_WEBHOOK_SECRET))
ok = set_webhook(
    'https://seudominio.com.br/webhook/telegram',
    drop_pending=True,
    secret_token=s.TELEGRAM_WEBHOOK_SECRET,
)
print('Webhook:', 'REGISTRADO' if ok else 'FALHA — ver logs')
"

# Confirmar registro via API Telegram
# Nota: usar grep com âncora ^ e -f2- para preservar = no valor do token
TELEGRAM_TOKEN=$(grep "^TELEGRAM_TOKEN=" /var/www/smartpaybot/.env | cut -d= -f2-)
curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN}/getWebhookInfo" | python3 -m json.tool

# Confirmar no JSON retornado:
#   "url": "https://seudominio.com.br/webhook/telegram"
#   "has_custom_certificate": false
#   "pending_update_count": 0
```

---

## Bloco 11 — Testes pós-deploy (T+90)

### Infraestrutura

```bash
# Health check
curl https://seudominio.com.br/healthz
# Esperado: {"status": "ok"}

# Landing page
curl -I https://seudominio.com.br/
# Esperado: HTTP/2 200

# Redirect HTTP → HTTPS
curl -I http://seudominio.com.br/
# Esperado: 301

# Arquivo sensível bloqueado
curl -I https://seudominio.com.br/.env
# Esperado: 404
```

### Autenticação do webhook

```bash
WEBHOOK_SECRET=$(grep "^TELEGRAM_WEBHOOK_SECRET=" /var/www/smartpaybot/.env | cut -d= -f2-)

# Sem secret — deve rejeitar com 403
curl -s -o /dev/null -w "%{http_code}" \
    -X POST https://seudominio.com.br/webhook/telegram \
    -H "Content-Type: application/json" \
    -d '{"message":{"text":"/start abc","chat":{"id":999}}}'
# Esperado: 403

# Com secret correto — deve aceitar com 200
curl -s -o /dev/null -w "%{http_code}" \
    -X POST https://seudominio.com.br/webhook/telegram \
    -H "Content-Type: application/json" \
    -H "X-Telegram-Bot-Api-Secret-Token: ${WEBHOOK_SECRET}" \
    -d '{"message":{"text":"/start abc","chat":{"id":999}}}'
# Esperado: 200
```

### Testes funcionais (via browser)

```
1. https://seudominio.com.br/            → landing page carrega
2. /auth/register                        → criar conta de teste
3. Dashboard                             → adicionar uma keyword
4. Card Telegram                         → clicar no link do bot
5. No bot: /start <codigo>               → "Tudo certo! Conta vinculada"
6. Dashboard (aguardar 5s)               → card atualiza sem F5
7. /admin/                               → login com conta admin, ver usuários e planos
```

### Pipeline rodando

```bash
# Aguardar até 5 minutos (SCAN_MIN_SECONDS=180)
journalctl -u smartpaybot -f --no-pager

# Deve aparecer em sequência:
#   crawl_once iniciado
#   match_recent_projects executado
#   notify_pending executado
```

---

## Bloco 12 — Backup inicial e automação (T+100)

```bash
# Backup manual imediato após confirmar que tudo funciona
cp /var/www/smartpaybot/app.db \
   /var/www/smartpaybot/backups/app.db.$(date +%Y-%m-%d_primeiro-deploy)

ls -lh /var/www/smartpaybot/backups/

# Configurar backup automático diário às 03h com retenção de 7 dias
crontab -u smartpaybot -e
```

Adicionar a linha:
```cron
0 3 * * * cp /var/www/smartpaybot/app.db /var/www/smartpaybot/backups/app.db.$(date +\%Y-\%m-\%d) && find /var/www/smartpaybot/backups/ -name "app.db.*" -mtime +7 -delete
```

```bash
# Verificar que o cron foi salvo
crontab -u smartpaybot -l
```

---

## Atualização futura

```bash
# No computador local: corrigir em dev, mergear em main
git checkout main
git merge dev
git push origin main

# Na VPS
cd /var/www/smartpaybot

# 1. Backup antes de qualquer mudança
cp app.db backups/app.db.pre-$(date +%Y-%m-%d_%H%M)

# 2. Baixar código novo
git pull origin main

# 3. Atualizar dependências (só instala o que mudou)
sudo -u smartpaybot .venv/bin/pip install -r requirements.txt --quiet

# 4. Reiniciar
systemctl restart smartpaybot
sleep 5
systemctl status smartpaybot     # confirmar: active (running)

# 5. Smoke test
curl -s https://seudominio.com.br/healthz
# Esperado: {"status": "ok"}
```

---

## Rollback de emergência

```bash
# 1. Parar imediatamente
systemctl stop smartpaybot
systemctl status smartpaybot     # confirmar: inactive (dead)

# 2. Identificar o problema
journalctl -u smartpaybot -n 100 --no-pager
tail -50 /var/log/smartpaybot/error.log

# 3. Restaurar banco (se corrompido)
ls -lh /var/www/smartpaybot/backups/
cp /var/www/smartpaybot/backups/app.db.<data-anterior> \
   /var/www/smartpaybot/app.db

# 4. Reverter código
cd /var/www/smartpaybot
git log --oneline -10            # identificar hash estável
git checkout <hash-do-commit-estavel>
sudo -u smartpaybot .venv/bin/pip install -r requirements.txt

# 5. Reiniciar e verificar
systemctl start smartpaybot
sleep 5
systemctl status smartpaybot     # confirmar: active (running)
curl https://seudominio.com.br/healthz

# 6. Retornar a main após corrigir o problema em dev
git checkout main
git pull origin main
systemctl restart smartpaybot
```

---

## Referência rápida — Systemd

| Ação | Comando |
|---|---|
| Parar | `systemctl stop smartpaybot` |
| Iniciar | `systemctl start smartpaybot` |
| Reiniciar | `systemctl restart smartpaybot` |
| Status | `systemctl status smartpaybot` |
| Logs em tempo real | `journalctl -u smartpaybot -f` |
| Últimas 100 linhas | `journalctl -u smartpaybot -n 100 --no-pager` |
| Recarregar config systemd | `systemctl daemon-reload` |
| Testar config Nginx | `nginx -t && systemctl reload nginx` |
| Logs de erro Nginx | `tail -f /var/log/nginx/error.log` |

---

*Documento criado em 2026-06. Ubuntu 24.04 LTS + Python 3.12.*
*Revisar ao migrar para PostgreSQL ou ao escalar para múltiplos workers.*
