# SmartPayBot — Testes Manuais de Onboarding

Execute estes cenários após qualquer alteração nas rotas de auth, dashboard ou Telegram.

**Pré-requisito:** banco seedado e servidor rodando.
```
.venv\Scripts\python.exe scripts\seed_plans.py
.venv\Scripts\python.exe -m flask run
```

---

## Cenário 1 — Registro de novo usuário

**Objetivo:** garantir que o cadastro funciona e o plano Free é aplicado.

Passos:
1. Acesse `http://localhost:5000/auth/register`
2. Preencha username, e-mail e senha válidos → clique em "Criar conta"
3. Verifique redirecionamento para o dashboard
4. No header do dashboard confirme o badge **"Plano Gratuito"**
5. No painel "Seu Plano" confirme: Keywords 0/3, Alertas hoje 0/10

Resultado esperado: cadastro bem-sucedido, plano Free ativo, sem subscription na tabela `subscriptions` (o plano Free é implícito).

---

## Cenário 2 — Login e logout

**Objetivo:** garantir fluxo básico de autenticação.

Passos:
1. Acesse `http://localhost:5000/auth/login`
2. Use as credenciais do Cenário 1 → clique em "Entrar"
3. Verifique redirecionamento para o dashboard
4. Clique em "Sair" no navbar
5. Tente acessar `http://localhost:5000/dashboard` diretamente

Resultado esperado: após logout, redirecionamento para login (302). Dashboard não acessível sem sessão.

---

## Cenário 3 — Vinculação do Telegram (dev com polling)

**Objetivo:** vincular o bot ao usuário via `/start <código>`.

Pré-requisito: `TELEGRAM_TOKEN` válido no `.env`, bot criado via @BotFather.

Passos:
1. Em um terminal separado, inicie o polling:
   ```
   .venv\Scripts\python.exe scripts\telegram_poll.py
   ```
2. No dashboard, localize o card **"Telegram"** → estado "Não vinculado"
3. Anote o código exibido (ex.: `abc123`)
4. No app do Telegram, abra o bot ou pesquise `@TELEGRAM_BOT_USERNAME`
5. Envie: `/start abc123`
6. Aguarde a confirmação do bot no Telegram
7. Recarregue o dashboard

Resultado esperado:
- Bot responde "✅ Tudo certo! Sua conta foi vinculada com sucesso."
- Dashboard exibe estado "Vinculado" com o Chat ID
- Botão "Desvincular Telegram" visível

Verificar também:
- Enviar `/start` sem código → bot explica como usar
- Enviar `/start codigo_errado` → bot informa código inválido

---

## Cenário 4 — Limite de keywords (plano Free)

**Objetivo:** garantir que o Free não pode ter mais de 3 keywords.

Passos:
1. Com usuário Free (sem subscription), acesse o dashboard
2. Adicione a keyword "python" → salvar → confirmar chip aparece
3. Adicione "javascript" → confirmar
4. Adicione "excel" → confirmar (total: 3, no limite)
5. Tente adicionar "vba"

Resultado esperado: na 4ª keyword, exibir mensagem de erro "Limite de keywords atingido. Seu plano Free permite até 3."

Verificar também:
- Chip da 4ª keyword não aparece
- Contagem no painel "Seu Plano" mostra 3/3 (barra vermelha)

---

## Cenário 5 — Downgrade Pro → Free com keywords excedentes

**Objetivo:** garantir que keywords não são deletadas no downgrade, mas o aviso é exibido.

Pré-requisito: usuário existente no banco.

Passos:
1. No admin (`/admin/`), eleve o usuário para Pro
2. No dashboard, adicione 5 keywords (Pro permite ilimitado)
3. No admin, rebaixe o usuário de volta para Free
4. Recarregue o dashboard do usuário

Resultado esperado:
- As 5 keywords ainda aparecem (não foram deletadas)
- Banner laranja de aviso: "Você tem 5 keywords — o plano Gratuito permite 3"
- Barra de keywords mostra 5/3 (cor vermelha)
- Tentativa de adicionar mais uma keyword retorna erro de limite

---

## Cenário 6 — Painel admin (acesso e restrições)

**Objetivo:** garantir que somente admins acessam `/admin/`.

Passos:
1. Como usuário Free (não-admin), acesse `http://localhost:5000/admin/`
   - Resultado esperado: **403 Forbidden**
2. Faça logout
3. Acesse `http://localhost:5000/admin/` sem sessão
   - Resultado esperado: **302 → /auth/login** (login_required executa antes)
4. Faça login como admin (criado via `scripts/create_master.py`)
5. Acesse `http://localhost:5000/admin/`
   - Resultado esperado: tabela de usuários com planos e botões de alteração
6. Altere o plano de um usuário Free para Pro → confirmar flash de sucesso
7. Altere de volta para Free

---

## Comandos úteis para debug

```bash
# Ver usuários e planos no banco
.venv\Scripts\python.exe scripts\dump_users.py

# Resetar banco (APAGA TUDO)
del app.db
.venv\Scripts\python.exe scripts\bootstrap_db.py
.venv\Scripts\python.exe scripts\seed_plans.py
.venv\Scripts\python.exe scripts\create_master.py

# Logs em tempo real
.venv\Scripts\python.exe -m flask run --debug
```
