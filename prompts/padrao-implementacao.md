# Template de Prompt — Nova Implementação

Use este template ao iniciar uma sessão de desenvolvimento de nova feature ou correção no SmartPayBot.

---

## Template

```
Contexto do projeto:
O SmartPayBot é um SaaS de alertas de freelas (99Freelas → Telegram).
Stack: Flask + SQLAlchemy 2.x + SQLite (dev) + APScheduler + lxml.
Governança: seguir AGENTS.md; Abilio Dev OS v0.1.1-dev é referência leve, e regras locais mais restritivas vencem.
Estado atual: [descrever o que já está feito, se relevante]

Objetivo desta sessão:
[Descrever a feature ou correção de forma clara e específica]

Restrições obrigatórias:
- Não alterar workers/ingestor.py, workers/matcher.py (pipeline crítico)
- Não quebrar SQLite em dev
- Não implementar Stripe ainda
- Não mover arquivos de lugar
- Seguir rules/padrao-codigo.md
- Executar quality gates proporcionais ao risco da mudança

Antes de implementar:
1. Proponha um plano listando quais arquivos serão criados/alterados
2. Aguarde minha confirmação
3. Implemente em etapas pequenas
4. Liste os arquivos alterados ao final
5. Sugira comandos de teste
6. Sugira o commit
7. Não fazer push, PR, deploy, SSH ou escrita em Scheduled Task sem pedido explícito
```

---

## Exemplos de uso

### Correção pequena de UI

```
Contexto do projeto:
SmartPayBot — dashboard funcional com monitoramento e keywords já implementados.

Objetivo desta sessão:
Corrigir um bug visual pequeno no dashboard sem alterar regras de negócio.

Comportamento atual: [descrever]
Comportamento esperado: [descrever]

Restrições:
- Não alterar pipeline de scraping/matching/notificação
- Não iniciar pagamento automatizado fora de tarefa própria
- Não mover arquivos
- Executar validações proporcionais ao risco
- Não fazer push, deploy ou SSH sem pedido explícito

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
- [ ] O quality gate escolhido é proporcional ao risco?
- [ ] A mudança respeita `AGENTS.md` e as regras locais do SmartPayBot?
