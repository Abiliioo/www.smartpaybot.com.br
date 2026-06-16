# Template de Prompt — Nova Implementação

Use este template ao iniciar uma sessão de desenvolvimento de nova feature ou correção no SmartPayBot.

---

## Template

```
Contexto do projeto:
O SmartPayBot é um SaaS de alertas de freelas (99Freelas → Telegram).
Stack: Flask + SQLAlchemy 2.x + SQLite (dev) + APScheduler + lxml.
Estado atual: [descrever o que já está feito, se relevante]

Objetivo desta sessão:
[Descrever a feature ou correção de forma clara e específica]

Restrições obrigatórias:
- Não alterar workers/ingestor.py, workers/matcher.py (pipeline crítico)
- Não quebrar SQLite em dev
- Não implementar Stripe ainda
- Não mover arquivos de lugar
- Seguir rules/padrao-codigo.md

Antes de implementar:
1. Proponha um plano listando quais arquivos serão criados/alterados
2. Aguarde minha confirmação
3. Implemente em etapas pequenas
4. Liste os arquivos alterados ao final
5. Sugira comandos de teste
6. Sugira o commit
```

---

## Exemplos de uso

### Feature nova

```
Contexto do projeto:
SmartPayBot — sistema de planos Free/Pro já implementado.
Próximo passo: integração com Stripe para automatizar cobranças.

Objetivo desta sessão:
Implementar Stripe Checkout para o plano Pro.
O usuário clica em "Assinar Pro" no dashboard e é redirecionado
para a página de pagamento hospedada do Stripe.
Após pagamento, webhook confirma e eleva o plano automaticamente.

Restrições:
- Não alterar pipeline de scraping/matching/notificação
- Não alterar lógica de planos existente (só adicionar rotas de billing)
- Preservar fluxo de upgrade manual no admin (continuar funcionando)
- SECRET_KEY e STRIPE_SECRET_KEY via .env

Antes de implementar:
[seguir template acima]
```

### Correção de bug

```
Contexto do projeto:
SmartPayBot — notifier.py está enviando alertas duplicados para usuários Pro.

Objetivo desta sessão:
Identificar a causa do bug de duplicação e corrigir sem alterar
o fluxo de deduplicação existente (UNIQUE user_id+global_project_id).

Comportamento atual: [descrever]
Comportamento esperado: [descrever]
Logs relevantes: [colar trecho do log se disponível]

Restrições:
- Não alterar schema do banco
- Não reescrever notify_pending()
- Apenas corrigir o ponto específico

[seguir template acima]
```

---

## Checklist pré-implementação

- [ ] O objetivo está claro e delimitado (feature única)?
- [ ] Há risco de quebrar o pipeline? Se sim, foi avaliado?
- [ ] A feature é para gerar receita ou manter o que já gera?
- [ ] Existe uma forma mais simples de atingir o mesmo objetivo?
- [ ] O banco SQLite em dev vai continuar funcionando?
- [ ] Algum segredo vai ser introduzido? Está no `.env` e não no código?
