# SmartPayBot — Regras de Negócio

## Planos

### Free (Gratuito)

| Recurso | Limite |
|---|---|
| Keywords cadastradas | 3 |
| Alertas via Telegram por dia | 10 |
| Histórico de projetos | Ilimitado |
| Dashboard KPIs | Disponível |
| Vinculação Telegram | Disponível |
| Rastreamento de ganhos (won) | Disponível |

### Pro

| Recurso | Limite |
|---|---|
| Keywords cadastradas | Ilimitado |
| Alertas via Telegram por dia | Ilimitado |
| Histórico de projetos | Ilimitado |
| Dashboard KPIs | Disponível |
| Vinculação Telegram | Disponível |
| Rastreamento de ganhos (won) | Disponível |
| Suporte prioritário | Disponível |

---

## Limites: comportamento em detalhe

### Keywords

**Regra:** O sistema bloqueia a adição de novas keywords quando o usuário Free já possui 3.

**Implementação:** `dashboard.py → save_keywords()` chama `can_add_keyword(db, user_id, current_count)` antes de inserir. Retorna HTTP 403 (JSON) ou flash de aviso (HTML) quando o limite é atingido.

**Upgrade:** Usuário Pro pode ter quantas keywords quiser. O limite `-1` no banco significa ilimitado.

**Regra de negócio crítica:** Não silenciar o bloqueio. O usuário deve saber que atingiu o limite e como fazer upgrade.

---

### Alertas diários

**Regra:** O usuário Free recebe no máximo 10 alertas por dia (UTC). Notificações excedentes ficam pendentes e são enviadas no dia seguinte quando o contador resetar.

**Implementação:** `notifier.py → notify_pending()` chama `can_receive_alert_today(db, user_id)`. Se False, pula o envio **sem** incrementar `notify_attempts` (a notificação não é descartada, apenas adiada).

**Contador:** `UserAlertDaily(user_id, date)` com `alerts_sent`. Upsert a cada envio bem-sucedido.

**Reset diário:** Automático por design — a data muda à meia-noite UTC e novos registros são criados.

**Usuário Pro:** `max_alerts_day = -1` → `can_receive_alert_today()` retorna `True` diretamente, sem checar o contador.

---

## Matching

**Regra:** Um projeto é casado com um usuário quando qualquer keyword do usuário é encontrada no título do projeto (substring, case-insensitive, sem acentos).

**Normalização:** Texto e keywords passam por `normalize_text()` — lowercase + remoção de acentos + espaços normalizados.

**Deduplicação:** A constraint `UNIQUE(user_id, global_project_id)` em `projects_per_user` garante que o mesmo projeto nunca é notificado duas vezes para o mesmo usuário.

**Escopo do matching:** Apenas usuários com `subscription.status = 'active'` recebem alertas? ← **Decisão pendente.** Atualmente o matching cobre todos os usuários com keywords, independente de plano. O limite é enforçado apenas no *envio* (notifier). Considerar mover a verificação de plano para o matcher no futuro.

---

## Subscriptions

**Regra:** Cada usuário tem no máximo uma subscription ativa (`UNIQUE user_id` na tabela `subscriptions`).

**Sem subscription = Free implícito.** `get_user_plan()` retorna o plano Free como fallback quando não há registro.

**Troca de plano:** `set_user_plan(db, user_id, plan_slug)` — upsert na tabela, sincroniza `user.is_subscriber` para compatibilidade com código legado.

**Gestão atual:** Manual pelo admin em `/admin/`. Nenhuma automação de cobrança ainda.

---

## Telegram

**Vinculação:** O usuário clica em "Vincular no Telegram" → abre deep-link com `link_code` único → envia `/start <code>` ao bot → webhook registra o `chat_id` → invalida o `link_code`.

**Sem Telegram vinculado:** O usuário não recebe alertas. O notifier registra aviso em log e incrementa `notify_attempts`.

**Desvinculação:** Disponível no dashboard (`/dashboard/unlink`). Gera novo código de vinculação automaticamente.

---

## Rastreamento de projetos ganhos

**Regra:** O usuário pode marcar manualmente um projeto como "ganho" e informar o valor recebido (em centavos internamente, em R$ na UI).

**Dados:** `ProjectPerUser.won` (bool), `won_cents` (int), `won_at` (timestamp).

**KPIs derivados:** Conversão (won/total), ticket médio, receita diária/semanal/mensal — calculados on-the-fly nas rotas de API do dashboard.

**Sem validação externa:** O valor declarado é auto-informado. Não há verificação com a plataforma. Usado apenas para que o usuário acompanhe seu próprio ROI.

---

## Regras de admin

- Apenas usuários com `user.is_admin = True` acessam `/admin/`.
- Admin pode alterar o plano de qualquer usuário via painel.
- Admin vê: plano atual, quantidade de keywords, alertas hoje, total de alertas, se tem Telegram vinculado.
- Admin **não** vê: senha hash, `telegram_link_code`, dados financeiros pessoais.
- Ações do admin são logadas com `user_id` e IP do solicitante.
