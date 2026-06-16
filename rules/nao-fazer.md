# SmartPayBot — O Que Não Fazer

Lista de proibições com justificativa. Antes de violar qualquer item, documente a razão em `docs/decisoes-tecnicas.md`.

---

## Pipeline e scraping

### ❌ Não reescrever `workers/ingestor.py`
O scraping do 99Freelas funciona e é frágil por natureza (depende de HTML da plataforma). Qualquer reescrita que quebre o parsing faz o produto parar. Alterações só para corrigir bugs reais ou adaptar a mudanças no HTML do site.

### ❌ Não reescrever `workers/matcher.py`
A lógica de matching é simples propositalmente. Substring após normalização de texto é suficiente para o volume atual e o público-alvo. Não adicionar machine learning, embeddings ou similaridade semântica sem demanda validada de usuários.

### ❌ Não alterar a sequência do pipeline
`ingestor → matcher → notifier` é a ordem correta. Não inverter, não paralelizar sem análise de concorrência no banco.

### ❌ Não aumentar SCAN_PAGES arbitrariamente
Mais páginas = mais requisições ao 99Freelas = maior risco de bloqueio de IP. Qualquer aumento deve ser cuidadoso e testado.

---

## Banco de dados

### ❌ Não usar `create_all` em produção
`init_db(create_all=True)` é exclusivo para dev. Em produção, usar Alembic migrations.

### ❌ Não recriar o banco SQLite sem backup
O `app.db` contém usuários e histórico. Nunca deletar sem `cp app.db app.db.bak` antes.

### ❌ Não adicionar FKs em tabelas existentes via `ALTER TABLE` no SQLite
SQLite não suporta isso. Usar migrations Alembic que recriam a tabela quando necessário.

### ❌ Não usar `db.commit()` múltiplas vezes dentro de um loop crítico sem necessidade
Commits frequentes em loops degradam performance. Preferir commit único ao final quando possível.

---

## Segurança

### ❌ Nunca versionar `.env`
O arquivo `.env` contém tokens reais, `SECRET_KEY` e credenciais. Está no `.gitignore`. Nunca fazer `git add .env`.

### ❌ Nunca logar tokens ou senhas
Nenhum `logger.info()` ou `print()` deve conter `TELEGRAM_TOKEN`, `SECRET_KEY`, `password_hash` ou qualquer credencial.

### ❌ Não remover `@csrf.exempt` do webhook Telegram sem alternativa
O Telegram não envia CSRF token. A isenção é correta e intencional. Não "corrigir" isso sem implementar validação de IP/secret do Telegram.

### ❌ Não expor `admin.py` sem `@admin_required`
Qualquer nova rota em `app/routes/admin.py` deve ter `@login_required` e `@admin_required`.

---

## Produto e código

### ❌ Não implementar Stripe antes de ter 3+ usuários pagando manualmente
Stripe adiciona complexidade de webhooks, chaves, testing mode, eventos idempotentes. Validar o modelo de negócio manualmente primeiro.

### ❌ Não adicionar dependências pesadas sem consulta
Antes de `pip install <pacote>`, perguntar: existe uma forma de fazer com o que já está instalado? Dependências são dívida de manutenção.

### ❌ Não mover arquivos de lugar sem necessidade técnica clara
Mover arquivos quebra imports, histórico do git e a memória do Claude. Refatorações de estrutura só quando o benefício for óbvio e documentado.

### ❌ Não criar abstrações prematuras
Three similar lines is better than a premature abstraction. Não criar `BaseService`, `AbstractRepository` ou similares sem necessidade demonstrada.

### ❌ Não adicionar feature flags ou backwards-compatibility shims
Se o código antigo não é mais usado, deletar. Se o novo substitui o antigo, substituir. Não manter os dois em paralelo sem data de remoção definida.

### ❌ Não implementar múltiplas features ao mesmo tempo
Uma feature por sessão de desenvolvimento. Facilita debug, review e rollback.

---

## Overengineering a evitar especificamente

- Não implementar GraphQL (REST simples é suficiente).
- Não implementar WebSockets para o dashboard (polling JSON está ok).
- Não implementar cache Redis antes de ter problema de performance real.
- Não implementar sistema de permissões granular (admin/não-admin é suficiente).
- Não implementar multi-tenancy de banco (schema por usuário, etc.).
- Não implementar i18n (produto é 100% brasileiro por enquanto).
