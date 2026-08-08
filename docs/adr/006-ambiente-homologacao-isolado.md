# ADR-006 - Ambiente de homologacao isolado do SmartPayBot

## Status

Proposta.

## Contexto

O SmartPayBot hoje so tem um ambiente real: producao. Mudancas de codigo sao validadas localmente (SQLite in-memory, testes unitarios) e implantadas direto em producao apos revisao manual. Nao existe `instance/`, `deploy/`, `staging/`, Alembic ou qualquer mecanismo de isolamento de ambiente alem de `FLASK_ENV`/`DATABASE_URL` lidos de um unico `.env` por processo.

Uma auditoria tecnica previa (SPB-240 na numeracao antiga, corrigida para SPB-263 nesta ADR por colisao de ID — ver secao "Numeracao") confirmou os seguintes pontos criticos do codigo real:

- `SCHEDULER=0` impede o boot automatico do APScheduler, mas **nao impede sua ativacao em runtime**: `POST /dashboard/bot-toggle` chama `sched_start()` para qualquer usuario autenticado que ligue o proprio monitoramento, independente do valor de `SCHEDULER` no boot.
- `POST /internal/ingest/projects` dispara `match_recent_projects()`/`notify_pending()` sempre que ha `inserted`/`updated`, **mesmo com `SCHEDULER=0`**.
- Nao existe modo mock/dry-run nativo para envio de Telegram (`infrastructure/telegram.py`).
- Homologacao nao pode reutilizar `app.db`, `SECRET_KEY`, `TELEGRAM_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` ou `INTERNAL_INGEST_TOKEN` de producao, nem chat_ids/usuarios/projetos reais.

Recursos reais da VPS (confirmados pelo proprietario no painel Hostinger em 08/08/2026, corrigindo a estimativa antiga de 1 GB usada na auditoria original):

| Item | Valor |
|---|---|
| Plano | Hostinger KVM 1 |
| Sistema | Ubuntu 24.04 LTS |
| Regiao | Brasil — Campinas |
| CPU | 1 nucleo / 1 vCPU |
| Memoria | 4 GB |
| Disco | 50 GB (uso observado ~3 GB) |
| Banda | 4 TB |
| Uso de memoria observado | ~14% |
| Uso de CPU observado | ~1% |
| Backup Hostinger | Semanal, 2 snapshots exibidos |
| Firewall Hostinger (painel) | 0 regras configuradas |

O painel exibindo "0 regras de firewall" **nao comprova** ausencia de firewall dentro do proprio Ubuntu — UFW/nftables/iptables ainda precisam ser auditados por comandos read-only na VPS (ver "Pendencias").

## Numeracao

O ID `SPB-240` ja esta em uso no backlog (`docs/phase-2/13-backlog.md`) para "Criar entregas por canal", nao relacionado a este ADR. Esta iniciativa foi registrada sob o ID **SPB-263** — proximo ID livre apos o maior ID real do backlog (`SPB-262`), sem reaproveitar nem preencher lacunas antigas.

## Decisao

### 1. Dois clones independentes na mesma VPS

Producao:
```
/home/deploy/apps/www.smartpaybot.com.br
```

Homologacao:
```
/home/deploy/apps/homolog.smartpaybot.com.br
```

Cada um com `.venv`, `.env`, banco SQLite e logs proprios. Motivos: isolamento real sem ferramenta nova, simplicidade operacional, rollback trivial (diretorios independentes), reducao de risco humano (nao ha checkout compartilhado), e os recursos reais da VPS (4 GB RAM, 50 GB disco) comportam a estrategia com folga.

**Nao escolhidas nesta etapa** (nao invalidadas para sempre, apenas descartadas agora): mesmo clone com branches diferentes por servico (risco de checkout cruzado afetar os dois ambientes); branch `staging` permanente (mantem um terceiro estado a sincronizar sem necessidade comprovada); containerizacao via Docker (dependencia de infraestrutura nova, overhead de RAM da propria engine, projeto nao usa Docker hoje); git worktree como solucao principal (mais fragil operacionalmente que dois clones simples).

### 2. Mesmo commit em homologacao e producao

O commit validado em homologacao deve ser exatamente o commit posteriormente implantado em producao. Fluxo:

```
feature/* ou fix/* -> main (fast-forward, ja e o padrao do projeto)
                        -> deploy do hash exato em homologacao
                        -> validacao manual
                        -> deploy do MESMO hash em producao
```

Sem branch `staging` permanente. Deploy sempre referencia um hash explicito, nunca "o que estiver na branch agora".

### 3. `APP_ENV` separado de `FLASK_ENV`

Proposta arquitetural aceita para implementacao futura (nao implementada nesta fase): introduzir `APP_ENV` com valores `development` / `homologation` / `production`, identificando o contexto operacional. `FLASK_ENV` continua existindo e controlando o que ja controla hoje (secret key obrigatoria, `SESSION_COOKIE_SECURE`, `create_all`) por compatibilidade com o codigo atual. `APP_ENV` existe para permitir guardrails especificos de homologacao sem alterar a semantica ja estabelecida de `FLASK_ENV`.

### 4. Banco isolado

Homologacao usa `homolog.db` (ou caminho absoluto equivalente dentro do proprio diretorio de homologacao), nunca `app.db` de producao. Requisito futuro (nao implementado): quando `APP_ENV=homologation`, a aplicacao deve **recusar subir** se `DATABASE_URL` apontar para um caminho incompativel com homologacao.

### 5. Telegram isolado

Bot Telegram exclusivo de homologacao, nunca reutilizando token ou chat_ids de producao. Guardrail futuro (nao implementado): recusar boot em `APP_ENV=homologation` sem uma flag explicita confirmando que o token configurado e de homologacao.

### 6. Ingestao isolada

`INTERNAL_INGEST_TOKEN` exclusivo de homologacao. O coletor residencial real de producao nunca tera conhecimento do endpoint/token de homologacao. Homologacao recebe apenas seed/payload sintetico controlado — nunca scraping real duplicado do 99Freelas.

### 7. Scheduler

Homologacao inicia com `SCHEDULER=0`. Isso **nao e proteccao suficiente sozinha**, pelos dois vetores documentados no Contexto (`bot-toggle` e ingest). Guardrails adicionais (item 3-5 acima) serao implementados antes da ativacao real do ambiente — nenhum usuario sintetico de homologacao tera `chat_id` real vinculado, o que contem o pior caso mesmo que o scheduler seja ligado em runtime.

### 8. Porta e processo

| | Producao | Homologacao |
|---|---|---|
| Porta | `127.0.0.1:8000` | `127.0.0.1:8001` |
| Servico systemd | `smartpaybot.service` | `smartpaybot-homolog.service` |

Ambos bindados exclusivamente em `127.0.0.1` — nunca expostos diretamente a interfaces publicas.

### 9. Recursos

VPS real (ver Contexto): 1 vCPU, 4 GB RAM, 50 GB disco, 4 TB banda. Com esses numeros, **homologacao pode permanecer ativa 24/7 desde o inicio** (revisando a conclusao antiga baseada na estimativa incorreta de 1 GB). Ponto de atencao permanece a CPU: apenas 1 vCPU compartilhado entre producao e homologacao exige monitorar `load average` quando ambos estiverem sob uso simultaneo. Configuracao: 1 worker Gunicorn, `SCHEDULER=0`, nenhum crawler real, nenhum job pesado continuo.

Essa conclusao **ainda precisa ser confirmada** na inspeccao read-only real da VPS (`free -h`, `uptime`, `df -h`, `ss -ltnp`), nao apenas no painel Hostinger.

### 10. Protecao externa

Homologacao deve ter protecao **antes de chegar ao Flask**. Estrategia preferencial: Cloudflare Access. Fallback: Basic Auth no Nginx. A decisao final entre as duas depende de inspecionar a configuracao real da conta Cloudflare — **decisao aberta**, implementacao futura.

### 11. Indexacao

Requisitos, em camadas (nenhuma e por si so seguranca):

- header `X-Robots-Tag: noindex, nofollow, noarchive`;
- `robots.txt` com `Disallow: /`.

`robots.txt` nao e controle de seguranca — e apenas uma instrucao de cortesia para crawlers bem-comportados. A camada real de protecao e a do item 10.

## Pendencias explicitas

- Inspecao read-only real da VPS (systemd, Nginx, portas, recursos, permissoes, SSL) — comandos ja identificados na auditoria previa, nao executados.
- Firewall interno do Ubuntu (`ufw status verbose`, `nft list ruleset`) — "0 regras" no painel Hostinger nao comprova ausencia de firewall no SO. Requisito fixado: `8000` e `8001` devem permanecer acessiveis apenas em `127.0.0.1`, nunca expostos externamente.
- Inspecao manual da configuracao real da Cloudflare (proxy ligado/desligado, Access disponivel) antes de decidir entre Cloudflare Access e Basic Auth.
- Criacao manual do bot Telegram de homologacao no BotFather.

## Plano de fases subsequentes

Esta ADR cobre apenas a Fase A (arquitetura e formalizacao). Fases seguintes, a ajustar conforme a documentacao real mostrar dependencia diferente:

- **Fase B** — `APP_ENV` + guardrails de ambiente no codigo.
- **Fase C** — seed sintetico + protecao Telegram (bot dedicado).
- **Fase D** — inspecao read-only real da VPS.
- **Fase E** — clone + `.venv` + `.env` + `homolog.db` + systemd na porta 8001.
- **Fase F** — DNS/Nginx/SSL para `homolog.smartpaybot.com.br`.
- **Fase G** — Cloudflare Access ou Basic Auth + noindex.
- **Fase H** — matriz de isolamento e smoke tests.
- **Fase I** — fechamento documental + CHANGELOG + backlog.

## Riscos P0 documentados (bloqueadores antes de subir homologacao)

- Homologacao usar `app.db` de producao.
- `SECRET_KEY` compartilhada entre ambientes.
- `TELEGRAM_TOKEN` compartilhado entre ambientes.
- `chat_id` real presente em banco de homologacao.
- `INTERNAL_INGEST_TOKEN` compartilhado entre ambientes.
- Scheduler/notifier disparado acidentalmente enviando alerta real.
- Porta `8001` exposta publicamente.
- Dados reais copiados para homologacao.
- Restart/deploy de homologacao afetando o servico de producao.

## Consequencias

- Isolamento real de ambiente pela primeira vez no projeto, sem introduzir dependencia de infraestrutura nova (sem Docker, sem Alembic, sem orquestrador).
- Exige nova variavel `APP_ENV` e guardrails de codigo antes da ativacao real (fases subsequentes, nao cobertas por esta ADR).
- Exige acao humana fora do repositorio: criar bot Telegram dedicado, provisionar DNS/subdominio, configurar Cloudflare Access ou Basic Auth.
- Consumo adicional de RAM/CPU na VPS compartilhada, mitigado pelos recursos reais confirmados (4 GB RAM, 1 vCPU com uso atual ~1%), mas ainda sujeito a confirmacao por inspecao real.
- O ID `SPB-240` permanece reservado para "Criar entregas por canal"; esta iniciativa segue como `SPB-263`.
