# SmartPayBot — Decisões Técnicas

Registro cronológico de decisões de arquitetura e implementação. Serve para evitar reabrir discussões já resolvidas e entender o contexto de escolhas passadas.

---

## 2026-06

### DT-001 — SQLAlchemy 2.x com `Mapped[]` (typed ORM)

**Decisão:** Usar a API moderna do SQLAlchemy 2.x com `Mapped[T]` e `mapped_column()` em vez da API legada 1.x.

**Motivo:** Autocomplete mais preciso, verificação de tipos em tempo de desenvolvimento, menor boilerplate. O projeto nasceu já na 2.x.

**Consequência:** Qualquer novo modelo deve seguir o mesmo padrão. Não misturar estilos.

---

### DT-002 — SQLite em desenvolvimento, PostgreSQL em produção

**Decisão:** Manter SQLite (`app.db`) como banco padrão em dev.

**Motivo:** Zero configuração, não exige Docker ou serviço externo para rodar localmente. Acelera o ciclo de desenvolvimento.

**Risco aceito:** SQLite não suporta concorrência real. Em produção (quando houver), usar PostgreSQL obrigatoriamente.

**Quando revisar:** Antes de qualquer deploy em produção real.

---

### DT-003 — `create_all` em dev, sem Alembic ainda

**Decisão:** Usar `init_db(create_all=True)` em modo `development` para criar tabelas automaticamente.

**Motivo:** MVP em fase inicial; evitar overhead de Alembic antes de o schema estabilizar.

**Risco aceito:** Sem migrations versionadas. Mudanças de schema em produção requerem intervenção manual.

**Quando revisar:** Antes do primeiro deploy em produção. Alembic deve ser implementado junto com PostgreSQL.

---

### DT-004 — APScheduler in-process

**Decisão:** Usar `BackgroundScheduler` do APScheduler rodando dentro do processo Flask.

**Motivo:** Zero infraestrutura adicional. Simples de ligar (`SCHEDULER=1` no `.env`). Adequado para servidor único.

**Risco aceito:** Em Gunicorn com múltiplos workers, o pipeline seria executado N vezes em paralelo. Em produção, usar **1 worker Gunicorn** (ou `--preload`) até migrar para scheduler externo.

**Quando revisar:** Quando houver necessidade de múltiplos workers ou resiliência a reinicializações.

---

### DT-005 — Pipeline sem fila de mensagens

**Decisão:** Pipeline síncrono no mesmo processo: `crawl → match → notify` em sequência, com lock de threading para evitar sobreposição.

**Motivo:** Fila (Celery, RQ) adiciona Redis como dependência obrigatória e aumenta a complexidade operacional. Para o volume atual (dezenas de usuários, centenas de projetos/ciclo), não é necessário.

**Quando revisar:** Quando o tempo de execução de um ciclo ultrapassar o intervalo de agendamento (SCAN_MIN_SECONDS), ou quando houver mais de 100 usuários ativos.

---

### DT-006 — Plano determinado por Subscription, com fallback Free

**Decisão:** `get_user_plan(db, user_id)` retorna o plano Free como fallback quando o usuário não tem subscription ativa. Não há subscription automática ao registrar.

**Motivo:** Evita criar registros desnecessários no banco para usuários Free. Simplifica o seed e o registro.

**Consequência:** Código que verifica plano nunca deve assumir que subscription existe. Sempre usar `get_user_plan()`.

---

### DT-007 — `is_subscriber` (flag legada) mantido em sincronia

**Decisão:** Manter o campo `User.is_subscriber` (boolean) e sincronizá-lo com o plano real ao usar `set_user_plan()`.

**Motivo:** O campo existia antes do sistema de planos. Código legado pode depender dele. Sincronização evita quebras.

**Consequência:** `is_subscriber = True` ↔ plano Pro. `is_subscriber = False` ↔ plano Free (ou sem subscription).

**Quando remover:** Após auditoria confirmando que nenhuma rota/template usa `is_subscriber` diretamente. Nesse ponto, migrar para verificação via `get_user_plan()`.

---

### DT-008 — Limite de alertas enforçado no notifier, não no matcher

**Decisão:** O `matcher.py` não verifica limites de plano. Apenas `notifier.py` verifica `can_receive_alert_today()` antes de enviar.

**Motivo:** Separação de responsabilidades. O matcher cria registros `ProjectPerUser` (dados), o notifier decide se envia (regra de negócio de plano).

**Consequência:** Usuários Free acumulam `ProjectPerUser` pendentes além do limite (10/dia). Eles serão enviados nos dias seguintes. Isso é intencional — não são perdidos.

**Trade-off aceito:** Registros pendentes antigos podem se acumular para Free users muito ativos. Implementar TTL de limpeza no futuro (ex.: descartar não-notificados com mais de 7 dias).

---

### DT-009 — Telegram Bot único para todos os usuários

**Decisão:** Um único token de bot Telegram (`TELEGRAM_TOKEN`) compartilhado por todos os usuários.

**Motivo:** Simplicidade. Criar um bot por usuário seria complexo demais e desnecessário para o volume atual.

**Risco aceito:** Se o token for revogado, todos os usuários param de receber alertas. Rotacionar imediatamente se exposto.

---

### DT-010 — Admin panel simples sem framework de admin

**Decisão:** Implementar o painel admin como blueprint Flask simples (`/admin/`), sem usar Flask-Admin, Django Admin ou similar.

**Motivo:** A funcionalidade necessária é mínima (listar usuários, alterar plano). Um framework de admin adicionaria dependências e opções desnecessárias.

**Quando revisar:** Se o painel admin crescer para incluir edição de modelos, bulk actions, logs — considerar Flask-Admin ou solução similar.
