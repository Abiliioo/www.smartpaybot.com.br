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

O painel exibindo "0 regras de firewall" **nao comprova** ausencia de firewall dentro do proprio Ubuntu — refletia apenas a ausencia de regras no firewall gerenciado pelo painel Hostinger, distinto do firewall do proprio SO. A Fase D (inspecao read-only real da VPS, 16/08/2026) confirmou UFW ativo dentro do Ubuntu, com politica `incoming=deny`/`outgoing=allow`/`routed=disabled` e liberacao apenas de `22/tcp` (OpenSSH) e `80,443/tcp` (Nginx Full), tambem para IPv6; nftables/iptables refletem a mesma politica (`INPUT`/`FORWARD` com `DROP` padrao, `OUTPUT` `ACCEPT`). Ver secao "Plano de fases subsequentes" (Fase D).

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

Implementado em 08/08/2026 (commit `7e65bd9`, `infrastructure/config.py`, funcao `resolve_app_env`), com producao configurada explicitamente como `APP_ENV=production`: `APP_ENV` com valores `development` / `homologation` / `production`, identificando o contexto operacional, resolucao fail-closed (valor invalido ou `FLASK_ENV=production` sem `APP_ENV` explicito recusam o boot). `FLASK_ENV` continua existindo e controlando o que ja controlava (secret key obrigatoria, `SESSION_COOKIE_SECURE`, `create_all`) por compatibilidade com o codigo atual; o guardrail de `SECRET_KEY` foi estendido para tambem reconhecer `APP_ENV`.

### 4. Banco isolado

Homologacao usa `homolog.db` (ou caminho absoluto equivalente dentro do proprio diretorio de homologacao), nunca `app.db` de producao. Implementado em 08/08/2026 (commit `7e65bd9`, `infrastructure/db.py`, funcao `validate_database_url`, executada antes de `create_engine()`): quando `APP_ENV=homologation`, a aplicacao **recusa subir** se `DATABASE_URL` nao for explicita, nao for SQLite, for `:memory:`, ou nao apontar para um arquivo `homolog.db`. Producao mantem o comportamento anterior inalterado.

### 5. Telegram isolado

Bot Telegram exclusivo de homologacao, nunca reutilizando token ou chat_ids de producao. Duas barreiras, implementadas, testadas e **implantadas e validadas em producao em 09/08/2026** (B3, commits `0c41b25`, `18ac2b1` e `fc3b91c` — detalhes da validacao em `docs/phase-2/01-estado-atual.md`):

- **Intencao declarada**: `TELEGRAM_MODE` (`disabled` / `homologation` / `production`), com resolucao fail-closed simetrica a `APP_ENV` — `homologation` e `production` exigem o proprio valor explicito, sem fallback entre si; `development` aceita `disabled`/`homologation` e rejeita `production`.
- **Identidade fisica**: `TELEGRAM_EXPECTED_BOT_ID` (nao e secret — ID numerico do bot). `infrastructure/telegram.py` centraliza toda chamada de rede Telegram (`send_message`, `get_webhook_info`, `set_webhook`, `delete_webhook`, `get_updates`) atras de um identity guard que valida via `getMe` (lazy, na primeira operacao real — nunca no boot, para nao acoplar disponibilidade do Telegram ao boot do Flask/Gunicorn) que `result.id == TELEGRAM_EXPECTED_BOT_ID` e `result.is_bot == True`. Validacao bem-sucedida e cacheada por processo (por fingerprint do token); falha nunca e cacheada, permitindo nova tentativa na proxima operacao. Falha de identidade bloqueia apenas a operacao Telegram — nunca derruba o processo Flask.

Homologacao usara um bot Telegram dedicado (criacao manual no BotFather, fora do codigo — ver "Pendencias explicitas").

### 6. Ingestao isolada

`INTERNAL_INGEST_TOKEN` exclusivo de homologacao. O coletor residencial real de producao nunca tera conhecimento do endpoint/token de homologacao. Homologacao recebe apenas seed/payload sintetico controlado — nunca scraping real duplicado do 99Freelas.

### 7. Scheduler

Homologacao inicia com `SCHEDULER=0`. Isso **nao e proteccao suficiente sozinha**, pelos dois vetores documentados no Contexto (`bot-toggle` e ingest). Implementado em 08/08/2026 (commit `7e65bd9`, `workers/scheduler.py`): `start()` (e por extensao `start_scheduler()` e o toggle de monitoramento do dashboard) recusa iniciar o scheduler de scraping real quando `APP_ENV=homologation`, e o ciclo do pipeline pula a etapa de crawling nesse ambiente sem bloquear matcher/notifier. O guardrail de Telegram (item 5) foi implementado, testado e implantado/validado em producao em 09/08/2026 (B3).

### 8. Porta e processo

| | Producao | Homologacao |
|---|---|---|
| Porta | `127.0.0.1:8000` | `127.0.0.1:8001` |
| Servico systemd | `smartpaybot.service` | `smartpaybot-homolog.service` |

Ambos bindados exclusivamente em `127.0.0.1` — nunca expostos diretamente a interfaces publicas. Confirmado na Fase D (16/08/2026, `ss`): `8000` ocupada exclusivamente pelo Gunicorn de producao, `8001` livre, nenhum processo escutando publicamente em nenhuma das duas. **Decisao**: a porta `8001` nao sera aberta no UFW; o futuro Gunicorn de homologacao permanece bindado somente em `127.0.0.1:8001`, acessivel externamente apenas atraves do Nginx em `443` (Fase F).

### 9. Recursos

VPS real (ver Contexto): 1 vCPU, 4 GB RAM, 50 GB disco, 4 TB banda. Com esses numeros, **homologacao pode permanecer ativa 24/7 desde o inicio** (revisando a conclusao antiga baseada na estimativa incorreta de 1 GB). Ponto de atencao permanece a CPU: apenas 1 vCPU compartilhado entre producao e homologacao exige monitorar `load average` quando ambos estiverem sob uso simultaneo. Configuracao: 1 worker Gunicorn, `SCHEDULER=0`, nenhum crawler real, nenhum job pesado continuo.

Essa conclusao foi **confirmada** na inspecao read-only real da VPS (Fase D, 16/08/2026): disco raiz ~48 GB, uso ~2,7 GB (~6%), ~45 GB livres, clone de producao ocupando ~123 MB; memoria total ~3,8 GiB, ~3,3 GiB disponivel, swap 0; `load average` observado 0.00/0.00/0.00. A ausencia de swap nao e bloqueadora no estado atual, mas permanece caracteristica operacional a monitorar. Uma segunda instancia Gunicorn (1 worker, `SCHEDULER=0`, sem crawler real) e compativel com os recursos observados.

### 10. Protecao externa

Homologacao deve ter protecao **antes de chegar ao Flask**. Estrategia preferencial: Cloudflare Access. Fallback: Basic Auth no Nginx. A decisao final entre as duas depende de inspecionar a configuracao real da conta Cloudflare — **decisao aberta**, implementacao futura.

### 11. Indexacao

Requisitos, em camadas (nenhuma e por si so seguranca):

- header `X-Robots-Tag: noindex, nofollow, noarchive`;
- `robots.txt` com `Disallow: /`.

`robots.txt` nao e controle de seguranca — e apenas uma instrucao de cortesia para crawlers bem-comportados. A camada real de protecao e a do item 10.

## Pendencias explicitas

- ~~Inspecao read-only real da VPS (systemd, Nginx, portas, recursos, permissoes, SSL)~~ — **concluida na Fase D (16/08/2026)**, ver secao "Plano de fases subsequentes".
- ~~Firewall interno do Ubuntu (`ufw status verbose`, `nft list ruleset`)~~ — **concluida na Fase D**: UFW ativo, `8000`/`8001` confirmados acessiveis apenas em `127.0.0.1`, nao expostos externamente. Requisito original mantido como fato confirmado.
- Emissao de certificado TLS para `homolog.smartpaybot.com.br` (Fase F) — o certificado atual (`smartpaybot.com.br`, ECDSA, SAN `smartpaybot.com.br`/`www.smartpaybot.com.br`, validade 17/06/2026 a 15/09/2026) nao cobre o subdominio de homologacao. Preferencia arquitetural: certificado separado para homologacao, em vez de acoplar o subdominio ao certificado atual de producao, salvo impedimento operacional descoberto na propria Fase F.
- Configuracao de Nginx para `homolog.smartpaybot.com.br` (Fase F) — ainda nao existe `server_name`/`proxy_pass` para homologacao; producao (`smartpaybot`, sites-enabled) segue com `proxy_pass http://127.0.0.1:8000` inalterado.
- Inspecao manual da configuracao real da Cloudflare (proxy ligado/desligado, Access disponivel) antes de decidir entre Cloudflare Access e Basic Auth.
- Criacao manual do bot Telegram de homologacao no BotFather.

## Plano de fases subsequentes

Esta ADR cobre apenas a Fase A (arquitetura e formalizacao). Fases seguintes, a ajustar conforme a documentacao real mostrar dependencia diferente:

- **Fase B** — `APP_ENV` + guardrails de ambiente no codigo. **Concluida e implantada em producao**: subfases B1 e B2 (APP_ENV, banco, SECRET_KEY, scheduler/crawler) em 08/08/2026 (commit `7e65bd9`); B3 (Telegram — `TELEGRAM_MODE` + identity guard) em 09/08/2026 (commits `0c41b25`, `18ac2b1`, `fc3b91c`), com validacao operacional completa em producao (runtime, webhook, ciclo automatico do coletor — ver `docs/phase-2/01-estado-atual.md`).
- **Fase C** — seed sintetico + protecao Telegram (bot dedicado). Guardrails de codigo do lado do B3 ja implementados, testados e implantados/validados em producao; permanece pendente apenas a criacao manual do bot Telegram dedicado de homologacao (acao no BotFather, fora do codigo, necessaria somente quando a homologacao fisica for criada).
- **B4** — isolamento visual e de sessao da homologacao. **Implementado e testado localmente, ainda nao implantado em producao** (homologacao fisica tambem ainda nao existe): `SESSION_COOKIE_NAME` derivado deterministicamente de `APP_ENV` (`infrastructure/config.py`, funcao pura `session_cookie_name_for_app_env`, nunca configuravel via variavel de ambiente) — producao/development preservam o cookie legado `"session"`, homologacao usa `"smartpaybot_homolog_session"`; `SESSION_COOKIE_SECURE` passou a depender de `APP_ENV in ("production", "homologation")` (antes dependia de `FLASK_ENV`); `HTTPONLY`, `SAMESITE=Lax`, `DOMAIN=None` e `PATH=/` explicitos em todos os ambientes. Banner global "HOMOLOGACAO — AMBIENTE DE TESTES" integrado ao `<header>` (`app/templates/navbar.html`), classe `env-homologation` no `<body>` e prefixo `[HOMOLOGACAO]` no `<title>` (`app/templates/base.html`), todos condicionados exclusivamente a `APP_ENV` — nunca a hostname/porta/`request.host`. Auditoria confirmou que `login_user()` nao usa `remember=True` em nenhum fluxo, entao nenhum guardrail de `REMEMBER_COOKIE_*` foi necessario neste bloco.
- **Proximo bloco** — criacao fisica completa da homologacao (Fase E em diante), que deve ocorrer somente apos o B4 estar implantado e validado em producao.
- **Fase D** — inspecao read-only real da VPS. **Concluida em 16/08/2026**, sem bloqueadores: dois clones independentes seguem aprovados (apenas `/home/deploy/apps/www.smartpaybot.com.br` existe hoje, sem colisao de diretorio); systemd separado aprovado (apenas `smartpaybot.service` existe, sem colisao de unit); porta `8001` livre, bind loopback confirmado para `8000`/`8001`; firewall (UFW + nftables/iptables) confirmado ativo e consistente com a arquitetura prevista (ver item 8 e "Pendencias explicitas"); recursos confirmados (ver item 9); Nginx atual mapeado (`smartpaybot.com.br`/`www.smartpaybot.com.br` -> `127.0.0.1:8000`, `nginx -t` OK, nenhuma config de homologacao ainda); certificado SSL atual mapeado e confirmado como nao cobrindo `homolog.smartpaybot.com.br` (requisito registrado para a Fase F).
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
