# SmartPayBot — Contexto para Claude

## Governança local

Este repositório adota o Abilio Dev OS como referência leve de governança:

- versão: `v0.1.1-dev`
- pin: `31943dd76fe76cabc4a10de21e604b11f32c80c7`
- unidade de trabalho da adoção: GitHub Issue `#1`

O arquivo canônico para agentes é `AGENTS.md`. Regras locais mais restritivas do SmartPayBot vencem qualquer orientação geral do Dev OS.

## Idioma obrigatório

Responda, comente o status, relate o progresso e produza todos os documentos exclusivamente em português do Brasil (pt-BR).

Termos técnicos, nomes de arquivos, comandos, caminhos, slugs, hashes e mensagens de commit podem permanecer em inglês quando fizer sentido.

A regra abrange: respostas ao proprietário, comentários de andamento, planos de execução, diagnósticos, auditorias, relatórios intermediários, relatórios finais, documentação Markdown, explicações técnicas, mensagens de validação, perguntas de esclarecimento, planos de implementação, relatórios de testes, relatórios de homologação, procedimentos de deploy, análises de segurança e análises operacionais.

Não traduzir artificialmente: nomes de arquivos, nomes de funções, classes, variáveis, comandos, caminhos, slugs, hashes, nomes de branches, mensagens de commit já definidas, nomes de serviços, nomes de endpoints, ou termos técnicos cuja tradução prejudique a clareza.

Esta regra:

- vale para todas as próximas tarefas deste repositório;
- deve ser seguida mesmo quando o prompt não repetir a instrução;
- vale para qualquer modelo Claude utilizado no projeto;
- tem prioridade sobre o idioma predominante dos logs, ferramentas, bibliotecas ou documentação técnica consultada durante a execução;
- não autoriza traduzir código ou identificadores técnicos;
- não autoriza alterar conteúdo técnico apenas para traduzir nomenclaturas;
- não exige tradução de output produzido diretamente por ferramentas externas quando isso prejudicar a fidelidade do diagnóstico.

Quando logs, comandos ou ferramentas retornarem conteúdo em inglês, o Claude deve: (1) preservar o conteúdo técnico original quando necessário; (2) explicar seu significado em português do Brasil.

---

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
| DB prod atual | SQLite |
| DB prod futuro/proposto | PostgreSQL |
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
