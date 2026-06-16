# SmartPayBot — Contexto para Claude

## O que é este projeto

O **SmartPayBot** é um SaaS em construção que monitora oportunidades de freelas no **99Freelas**, filtra projetos por palavras-chave do usuário e envia alertas via **Telegram**. O objetivo final é gerar **receita recorrente** como produto pago.

Estado atual: beta funcional com pipeline completo (scraping → matching → notificação), sistema de planos Free/Pro implementado e painel admin operacional. Sem pagamento automatizado ainda.

---

## Prioridade absoluta

> **Gerar receita. Não escrever código bonito.**

Toda decisão técnica deve responder a: *"isso ajuda a vender ou a manter o que já vende?"*. Se não, questione antes de implementar.

---

## Regras de trabalho com Claude

### Antes de alterar qualquer arquivo

1. **Proponha um plano** — liste quais arquivos serão tocados e por quê.
2. Aguarde confirmação antes de implementar.
3. Nunca altere mais de um módulo de uma vez sem aprovação explícita.

### Durante a implementação

4. **Liste todos os arquivos alterados** ao final de cada resposta.
5. Marque claramente o que é novo (`NOVO`) vs. o que foi modificado (`ALTERADO`).
6. Nunca renomeie ou mova arquivos sem necessidade técnica clara.
7. Não introduza abstrações que não sejam necessárias para a tarefa atual.

### Após a implementação

8. **Sugira comandos de teste** — ao menos um smoke test executável.
9. **Sugira o commit** com mensagem no padrão do projeto (ver `prompts/padrao-commit.md`).
10. Aponte o próximo passo lógico (uma frase, sem planejar demais).

---

## O que NUNCA fazer

- Reescrever o pipeline de scraping/matching/notificação.
- Alterar `workers/ingestor.py`, `workers/matcher.py` sem necessidade crítica.
- Implementar Stripe antes de validar o beta manual.
- Mover arquivos de lugar sem necessidade.
- Adicionar dependências pesadas sem consultar.
- Versionar `.env` ou qualquer segredo.
- Deixar o banco SQLite quebrado em dev (é o ambiente de trabalho atual).

Ver lista completa em `rules/nao-fazer.md`.

---

## Arquitetura resumida

```
app/          → Flask (rotas, templates, formulários)
domain/       → Modelos, repositórios, serviços de negócio
infrastructure/ → Config, DB, Telegram, logging, scraping
workers/      → ingestor → matcher → notifier → scheduler
scripts/      → Utilitários de bootstrap e seed
docs/         → Documentação do produto e decisões
rules/        → Regras de desenvolvimento
prompts/      → Templates de prompt para sessões futuras
```

Pipeline crítico (NÃO TOCAR sem aprovação):
```
scheduler → crawl_once() → match_recent_projects() → notify_pending()
```

---

## Stack

| Camada | Tecnologia |
|---|---|
| Web | Flask 3.x + Flask-Login + Flask-WTF |
| ORM | SQLAlchemy 2.x (Mapped[]) |
| DB dev | SQLite (`app.db`) |
| DB prod | PostgreSQL (ainda não configurado) |
| Scraping | lxml + httpx async |
| Scheduler | APScheduler (in-process) |
| Alertas | Telegram Bot API |
| Planos | Free (3 kw / 10 alertas/dia) · Pro (ilimitado) |
| Pagamentos | — (futuro: Stripe) |

---

## Contexto de produto

- Público: freelancers brasileiros que trabalham no 99Freelas.
- Proposta: chegar antes da concorrência nas vagas que importam.
- Monetização: assinatura mensal Pro (meta: R$ 47/mês).
- Fase atual: beta — primeiros usuários pagantes via gestão manual.

Ver detalhes em `docs/produto.md` e `docs/monetizacao.md`.

---

## Comandos úteis

```powershell
# Subir o app em dev
.venv\Scripts\python.exe run.py

# Seed de planos (após recriar banco)
.venv\Scripts\python.exe scripts/seed_plans.py

# Redefinir senha de usuário
.venv\Scripts\python.exe scripts/bootstrap_db.py <username> <nova_senha>

# Criar usuário admin
.venv\Scripts\python.exe scripts/create_master.py
```
