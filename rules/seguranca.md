# SmartPayBot — Regras de Segurança

## Segredos e variáveis de ambiente

### ❌ NUNCA versionar `.env`

O arquivo `.env` está no `.gitignore`. Verificar antes de qualquer commit:

```powershell
git status  # .env não deve aparecer
git diff --cached  # .env não deve aparecer no staged
```

Se `.env` aparecer no histórico git, considerar o token comprometido e rotacionar imediatamente.

### ✅ Manter `.env.example` atualizado

O arquivo `.env.example` deve existir na raiz e conter todas as variáveis necessárias com valores fictícios:

```
FLASK_ENV=development
SECRET_KEY=troque-para-uma-chave-secreta-aleatoria
DATABASE_URL=sqlite:///app.db
TELEGRAM_TOKEN=seu-token-aqui
TELEGRAM_BOT_USERNAME=seu_bot
SCHEDULER=0
TZ_NAME=America/Sao_Paulo
LOG_LEVEL=INFO
SCAN_PAGES=10
SCAN_MIN_SECONDS=60
SCAN_MAX_SECONDS=180
```

### Token Telegram

- Nunca logar o token.
- Se o token vazou (git, log, screenshot), revogar imediatamente via @BotFather no Telegram (`/revoke`) e atualizar o `.env`.
- O token atual (`TELEGRAM_TOKEN`) é um segredo de produção — tratar como senha.

### SECRET_KEY

- Deve ser uma string aleatória de pelo menos 32 bytes.
- Geração recomendada: `python -c "import secrets; print(secrets.token_hex(32))"`
- Jamais usar o valor default `"dev-secret-key-change-me"` em produção.

---

## Autenticação e sessão

### Senhas

- Sempre armazenar hash via `werkzeug.security.generate_password_hash()`.
- Nunca armazenar senha em texto plano, log ou banco.
- Verificar com `check_password_hash()` — nunca comparar strings diretamente.

### Flask-Login

- `@login_required` em toda rota que exige autenticação.
- `@admin_required` (do `app/decorators.py`) em toda rota do painel admin.
- Não confiar em `current_user.is_admin` vindo de formulário/JSON — sempre reler do banco se necessário para ações destrutivas.

### Sessão

- `SECRET_KEY` forte é obrigatória — a sessão é assinada com ela.
- `WTF_CSRF_ENABLED = True` — não desativar.

---

## CSRF

- Todos os formulários HTML devem incluir `{{ form.hidden_tag() }}` ou `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.
- Requisições AJAX devem enviar o token no header ou body (já implementado via meta tag `csrf-token`).
- `@csrf.exempt` apenas em rotas de webhook onde o cliente externo não pode enviar CSRF (ex.: `webhook_telegram`). Documentar sempre.

---

## Webhook do Telegram

### Proteção atual (mínima)
O endpoint `/webhook/telegram` aceita qualquer POST. Em produção, adicionar pelo menos uma das seguintes proteções:

**Opção A — Validar header `X-Telegram-Bot-Api-Secret-Token`** (recomendada)
```python
# Ao registrar o webhook:
set_webhook(url, secret_token="token-secreto-aleatório")

# No endpoint:
if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != settings.TELEGRAM_WEBHOOK_SECRET:
    return "", 403
```

**Opção B — Validar que o IP é do Telegram**
IPs oficiais do Telegram: `149.154.160.0/20` e `91.108.4.0/22`.

### Webhook Stripe (futuro)
Quando implementar Stripe, validar a assinatura do webhook **obrigatoriamente**:
```python
import stripe
event = stripe.Webhook.construct_event(
    payload=request.data,
    sig_header=request.headers["Stripe-Signature"],
    secret=settings.STRIPE_WEBHOOK_SECRET,
)
```
Nunca processar eventos Stripe sem validar a assinatura.

---

## Proteção de rotas

### Painel admin

- `/admin/` e sub-rotas: `@login_required` + `@admin_required`.
- Em caso de acesso não autorizado: `abort(403)` — não redirecionar silenciosamente.
- Logar tentativas de acesso com user_id e IP.

### API JSON do dashboard

- Todas as rotas `/dashboard/api/*` têm `@login_required`.
- Retornam dados apenas do `current_user.id` — nunca de outro usuário sem verificação.
- Operações destrutivas (POST/DELETE) verificam que o recurso pertence ao usuário logado antes de modificar.

---

## Injeção e XSS

- Jinja2 faz auto-escape por padrão. Nunca usar `| safe` em dados vindos do usuário.
- Parâmetros de URL (ex.: `page`, `id`) sempre convertidos para tipo explícito: `int(request.args.get("page", 1))`.
- Dados de formulário sempre passados por WTForms com validators — nunca lidos raw e inseridos no banco diretamente.

---

## Logs de segurança

Eventos que **devem** ser logados:

| Evento | Nível | Exemplo |
|---|---|---|
| Login bem-sucedido | INFO | `[auth] login ok: username=X` |
| Login com falha | INFO | `[auth] login fail: username=X` |
| Registro de novo usuário | INFO | `[auth] register ok: user_id=X` |
| Alteração de plano pelo admin | INFO | `[admin] user_id=X → plano=Y por IP=Z` |
| Vínculo Telegram estabelecido | INFO | `[webhook] vínculo ok: user_id=X chat_id=Y` |
| Acesso negado (403) | WARNING | automático pelo Flask |
| Erro de envio Telegram após MAX_ATTEMPTS | ERROR | `[notifier] desistindo id=X` |
