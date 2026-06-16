# SmartPayBot — Modelo de Monetização

## Visão geral

Modelo **Freemium com assinatura mensal**. O plano Free serve como canal de aquisição; o Pro gera receita.

---

## Planos

### Free — R$ 0/mês

- 3 keywords
- 10 alertas/dia
- Sem cartão de crédito
- Objetivo: permitir que o freelancer **sinta o valor** antes de pagar

### Pro — R$ 47/mês (meta inicial)

- Keywords ilimitadas
- Alertas ilimitados
- Suporte prioritário
- Objetivo: freelancers sérios que dependem do produto para ganhar projetos

### Pro Anual — R$ 397/ano (futuro)
- Equivalente a ~R$ 33/mês (~30% de desconto)
- Implementar quando houver base de usuários mensais

---

## Fase atual: beta pago manual

### Como funciona

1. Usuário se cadastra normalmente no SmartPayBot.
2. Usa o plano Free até ver valor ou receber convite.
3. Entra em contato (e-mail, Telegram) para fazer upgrade.
4. Admin recebe o pagamento via **Pix ou transferência**.
5. Admin eleva o plano no painel `/admin/`.
6. Usuário passa a ter acesso Pro imediatamente.

### Por que manual?

- Evita overhead de Stripe antes de validar o modelo.
- Permite flexibilidade de preço durante o beta.
- Força contato com os primeiros usuários (feedback valioso).
- Integração Stripe só faz sentido a partir de ~5 usuários pagantes simultâneos.

### Meta de validação

> **10 usuários pagando R$ 47/mês = R$ 470 MRR**
> Isso valida o modelo e justifica a integração de pagamento automático.

---

## Próxima fase: Stripe

Quando o beta manual atingir 5–10 pagantes, implementar:

1. **Stripe Checkout** — página de pagamento hospedada (mínimo de código).
2. **Webhook `invoice.paid`** — elevar plano automaticamente após pagamento.
3. **Webhook `customer.subscription.deleted`** — rebaixar para Free ao cancelar.
4. **Portal do cliente** — gerenciamento de assinatura via Stripe Customer Portal.

Variáveis necessárias (a adicionar em `.env`):
```
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRO_MONTHLY=price_...
```

---

## Métricas a acompanhar

| Métrica | Onde ver | Meta |
|---|---|---|
| MRR (Receita Mensal Recorrente) | Manual / futuro: Stripe dashboard | R$ 470 (fase 2) |
| Churn rate | Manual | < 10%/mês |
| Conversão Free → Pro | Admin panel | > 5% |
| Usuários ativos (com Telegram vinculado) | Admin panel | > 70% dos cadastros |
| Alertas enviados/dia | Logs / dashboard | — |
| Projetos ganhos declarados | Dashboard KPI | Métrica de retenção |

---

## Argumentos de venda (para o pitch)

**Para o freelancer:**
- "Se você ganhar **um projeto a mais por mês**, o Pro já se pagou."
- Ticket médio de freela técnico no 99Freelas: R$ 300–2.000.
- Chegar primeiro = maior chance de aprovação da proposta.
- 10 alertas/dia no Free vs. ilimitado no Pro = diferença real em vagas aquecidas.

**Objeção comum:** *"Eu posso fazer isso de graça."*
**Resposta:** Pode — mas você vai ter que checar a plataforma manualmente, sem filtro, o dia todo. O SmartPayBot faz isso enquanto você está trabalhando.

---

## Canais de aquisição (curto prazo)

1. **Comunidades de freelancers no Telegram** — divulgação direta.
2. **Grupos de Facebook** — freelancers BR.
3. **99Freelas** — comunidade própria da plataforma.
4. **Boca a boca** — usuários Free satisfeitos que indicam.
5. **SEO** *(futuro)* — landing page com "alerta de freelas".
