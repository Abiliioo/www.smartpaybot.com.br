# Roadmap mestre — SmartPayBot

Este documento e a fonte canonica de PRIORIDADE operacional do SmartPayBot a partir desta data. Consolida as conclusoes de quatro auditorias profundas (B4 forense adversarial, UX/UI, arquitetura/seguranca do SPB-263, coletor).

`docs/phase-2/02-roadmap.md` permanece no repositorio como roadmap/historico anterior (Sprint 0 da Fase 2) e nao deve ser apagado. A partir deste documento, a priorizacao corrente passa a ser mantida em `docs/phase-2/16-roadmap-mestre.md`.

Atualizar este documento a cada gate atravessado.

## Estado atual

- SPB-263 B1/B2 concluidos e validados em producao (commit `7e65bd9`, 08/08/2026).
- SPB-263 B3 concluido e validado em producao (commits `0c41b25`/`18ac2b1`/`fc3b91c`, 09/08/2026).
- SPB-263 Fase D (inspecao read-only da VPS) concluida em 16/08/2026, sem bloqueadores.
- SPB-263 B4 (isolamento visual e de sessao entre `development`/`homologation`/`production`) **PUBLICADO e VALIDADO em producao em 18/08/2026** (horario local do operador; 19/08/2026 UTC na VPS), commit `2625a82551efde5b1223334ec47d90affce26caf`: 204/204 local, 204/204 na VPS antes do restart, `DEPLOY_STATUS=SUCCESS`, banco integro, cookie `session` preservado (`Secure`/`HttpOnly`/`SameSite=Lax`/`Path=/`, sem `Domain`), nenhum banner de homologacao em producao, smoke HTTP e Telegram saudaveis, Collector restaurado com `LastTaskResult=0`.
- Primeiro deploy real executado pela automacao controlada (`scripts/deploy-production.ps1` + `scripts/deploy-production-remote.sh`). Incidente local (nao de producao): um bug de transporte do Windows PowerShell 5.1 corrompeu a ultima linha do script remoto enviado via stdin e fez o orquestrador reportar falsamente um rollback (`exit 2`) apos o `DEPLOY_STATUS=SUCCESS` remoto real — producao nunca saiu do ar nem foi revertida. Hotfix definitivo integrado em `main`, commits `ae631128776241ec7429dfcbe3ee861255794abd` e `f02faaac5e2bb1c958014995ffaa48b14f4f5515` (transporte Base64 sobre bytes crus do blob Git, validado por SHA-256).
- Fases E-I do SPB-263 (clone fisico de homologacao, DNS/Nginx/TLS, protecao externa, isolamento end-to-end, closeout) nao iniciadas — SPB-270 ja foi implantado e validado em producao; seguem dependendo de SPB-272 e dos gates operacionais (ver gates).
- ADR-006 (ambiente de homologacao isolado): status **Proposta**.
- SPB-263: **EM ANDAMENTO**.
- Deploy de producao tem automacao local disponivel via `scripts/deploy-production.ps1` + `scripts/deploy-production-remote.sh` (ver `docs/runbooks/deploy-producao.md`), substituindo a sequencia manual de comandos SSH por um unico comando com preflight, gates fail-closed, testes, smoke e rollback automatico. A chave SSH permanece sob controle do operador. Ja usada em um deploy real (B4), com o hotfix de transporte acima aplicado apos o incidente local.
- SPB-254 (correcoes funcionais de UI: chip-x em touch, switch acessivel por teclado) **CONCLUIDO — IMPLANTADO e VALIDADO em producao em 20/08/2026**, commit `588b86167f633faab812f23e3fbe0be0d534918c`: 213/213 testes na VPS, banco integro, HTTP saudavel (`HOME`/`LOGIN`/`REGISTER`=200, `ADMIN`=302), cookie `session` preservado, sem banner de homologacao, Telegram saudavel, Collector restaurado e `LastTaskResult=0` na rodada pos-deploy; validacao manual do operador (desktop, foco por teclado, mobile ~375px, chip-x sem depender de hover) PASS. Este deploy foi tambem a primeira validacao real em producao do hotfix de transporte PowerShell -> SSH (commits `ae63112`/`f02faaa`): `DEPLOY_STATUS=SUCCESS` com `LOCAL_DEPLOY_EXIT_CODE=0`, sem qualquer ocorrencia de `numeric argument required`.
- SPB-264 (Collector: HTTP strict, parser health, exit codes, retry e logs seguros) **CONCLUIDO — MERGEADO e VALIDADO no Collector local real em 20/08/2026**, PR #4, Issue #3 fechada, merge commit `e345fefe900c70636260d8521762c298cbfc1956`: `py_compile` aprovado, `tests.test_collector_push_spb264` 12/12, `run_collector.bat` retornou `EXIT_CODE=0`, gate local com 10/10 paginas OK, parser OK em 10/10, 100 projetos unicos, ingest OK (`received=100`) e segundo ciclo idempotente (`inserted=0`, `updated=0`, `skipped=100`). Sem deploy VPS, sem alteracao de Scheduled Task/cadencia/`--pages 10`.
- SPB-265 (Collector: estado persistente descartavel + telemetria por ciclo) **CONCLUIDO — MERGEADO e VALIDADO pelo Scheduled Task real em 21/08/2026**, PR #11, Issue #10, merge commit `f2b026bc16946bab3c424761e6b1b65917e5d616`: suite local 246/246; estado local em `data/collector/collector_state.json` ignorado pelo Git; telemetria `COLLECTOR_TELEMETRY` observada em ciclos reais com `exit_code=0`, 10/10 paginas OK, parser OK, 100 projetos unicos, ingest `received=100`, `state_status=loaded`, `state_write_status=written`, `recent_ids_count=100`; estado observado com `schema_version=1`, `last_exit_code=0`, `last_success_at=2026-08-22T00:56:40Z`. Sem deploy VPS, sem alteracao de Scheduled Task/cadencia/`--pages 10`, sem early-stop, sem shadow mode.
- SPB-266 (Collector: shadow mode de coleta incremental) **MERGEADO e com primeiro ciclo operacional real PASS em 24/08/2026**, PR #14, Issue #13 ainda aberta, merge commit `523920f7e92e5e2c8f4911e4fa232118bca94391`: Scheduled Task `SmartPayBot Collector` retornou `LastTaskResult=0` e `NumberOfMissedRuns=0`; telemetria `COLLECTOR_TELEMETRY` confirmou coleta real preservada (10/10 paginas OK, parser OK, 100 projetos unicos, ingest `received=100`) e shadow utilizavel (`shadow_enabled=true`, `shadow_hypothetical_stop_page=2`, `shadow_pages_saved_hypothetical=8`, `shadow_missed_new_if_active=0`, `shadow_known_ratio=0.99`, `shadow_cycle_usable=true`, `shadow_reason=stop_found`). Janela de observacao iniciada; sem deploy VPS, sem alteracao de Scheduled Task/cadencia/`--pages 10`, sem early-stop real.
- SPB-268 (Collector Fast/Deep) **CONCLUIDO — MERGEADO e HOMOLOGADO operacionalmente em AUTO+PT5M**: PR #42 adicionou a fundacao Fast/Deep; PR #43 ativou o runner versionado `--mode auto --fast-pages 2 --deep-pages 10`; homologacao C3 em AUTO+PT10M comprovou DEEP completo; homologacao C4 em AUTO+PT5M comprovou `DEEP -> FAST -> DEEP`. Scheduled Task atual: `Interval=PT5M`, `Duration=P3650D`, `MultipleInstances=IgnoreNew`, `ExecutionTimeLimit=PT15M`. Baseline: paginas 1-2 ~a cada 5 min, paginas 1-10 ~a cada 10 min, ~12 GETs/10 min (+20%). SPB-267 continua bloqueado, PT2M nao autorizado e SPB-269 permanece necessario antes de cadencia mais agressiva.
- SPB-270 (F-01: alinhar ingest/DEBUG a `APP_ENV`) **CONCLUIDO — IMPLANTADO e VALIDADO em producao em 21/08/2026**, PR #7, PR #8, Issue #6 fechada: `DEBUG` e ingest sensivel agora seguem `APP_ENV`; `homologation` e `production` sao fail-closed para `DEBUG=true` e ingest sem `INTERNAL_INGEST_TOKEN`. Deploy controlado via `scripts/deploy-production.ps1` atualizou producao de `588b86167f633faab812f23e3fbe0be0d534918c` para `15378dda90840579060e81be7cef3f47939ec6e9`: `DEPLOY_STATUS=SUCCESS`, `LOCAL_DEPLOY_EXIT_CODE=0`, testes remotos 241/241, smoke HTTP OK (`HOME=200`, `LOGIN=200`, `REGISTER=200`, `ADMIN=302`), cookie `session` preservado, banner de homologacao ausente, Telegram read-only OK, banco integro, `JOURNAL_ERROR_HITS=0`, rollback nao executado, Collector restaurado e ciclo automatico pos-deploy com `LastTaskResult=0`.
- SPB-271 (guardrail de URL em `set_webhook`) **IMPLEMENTADO e TESTADO LOCALMENTE, ainda NAO implantado em producao**: `set_webhook` valida `webhook_url` contra `PUBLIC_BASE_URL` antes de `_guard()`/`getMe`, com parsing estrutural, HTTPS, mesma origem/porta efetiva, path canonico e bloqueio fail-closed sem chamada real ao Telegram para URL invalida.
- SPB-250C (React + TypeScript + Vite acoplado ao Flask) avancou com dois marcos mergeados: fundacao/preview React via PR #19 e rota experimental publica `/ui-preview` via PR #21, commit `9e4e14ef30bffd9c18a1c213a1509237cb6af573`. O preview foi validado localmente no navegador via Flask em `127.0.0.1:5000/ui-preview`, com assets JS/CSS retornando 200 no Network. Nenhuma rota real foi substituida; `/`, `/pro`, auth, dashboard e admin continuam Jinja; sem deploy. SPB-250E concluiu o fluxo de build/deploy controlado do React dist; SPB-250F avançou com a primeira rota real controlada, permitindo `/` React atrás de `REACT_LANDING_ENABLED`, com fallback Jinja e sem tocar `/pro`, auth, dashboard ou admin; SPB-250G refinou o visual da landing, SPB-250H ajustou copy/conversão sem alterar backend/env/deploy e SPB-250J inicia o design system premium em React para Home/ProPreview, mantendo `/pro` real em Jinja nesta etapa; SPB-250K redesenha estruturalmente Home/ProPreview para corrigir a direção visual premium antes de nova publicação; SPB-250K-C refina a copy exposta, o FAQ Pro e os sinais do Painel sem backend/deploy; SPB-250K-D aplica o refino final de direção visual/copy antes da validação humana; SPB-250K-E reestrutura a UX funcional com foco no Painel de oportunidades acionável; SPB-250K-F suaviza o sistema de botões/CTAs para reduzir azul dominante. SPB-250I corrige o outbound Telegram de readiness para preferir IPv4 em `getMe`/`getWebhookInfo`, preservando fail-closed após rollback por timeout IPv6.
- SPB-251B reorganiza o dashboard real como fonte de verdade da UX: status operacional de monitoramento, Telegram, plano, uso diario, keywords, oportunidades recentes e proxima melhor acao com dados ja disponiveis. O painel diferencia monitoramento pausado, pendente por falta de Telegram e ativo sem afirmar saude real de pipeline. Sem Landing/Pro, sem migracao React e sem deploy nesta etapa.
- SPB-251C refina estruturalmente o dashboard real: oportunidades recentes passam a ser o nucleo do painel, o resumo de status fica compacto, a proxima melhor acao ganha destaque, palavras-chave viram gestao secundaria e o bloco de resultados redundante sai da tela. Sem React/marketing, sem deploy, sem collector e sem metricas inventadas.
- SPB-251D Etapa 1 implementa a camada real de metricas do dashboard em servico de dominio, sem redesenhar HTML/CSS: oportunidades hoje/7d, serie diaria 7d/30d, mediana de tempo ate alerta com cobertura explicita, keywords produtivas, ranking 30d, keywords maduras sem resultado, ganhos registrados e ultimas 3 oportunidades. `review_count` fica somente como legado temporario ate a Etapa 2. Sem deploy, VPS, Collector, Telegram real ou migration.

## Principio de priorizacao

Cadeia de receita do produto:

```
ativacao -> valor percebido -> atrito de limite -> upgrade
```

Findings das auditorias sao priorizados pelo impacto nessa cadeia, nao apenas por severidade tecnica isolada. Risco entra na frente quando bloqueia genuinamente algo na cadeia (ex.: isolamento inseguro bloqueia a Fase E). Confiabilidade e valor percebido vem antes de polish visual amplo.

## Trilhos

### TRILHO A — confiabilidade / coletor

```
SPB-264 (correcao: HTTP estrito, parser health, exit codes, retry, log seguro) -- CONCLUIDO em 20/08/2026
   -> SPB-265 (estado persistente + telemetria) -- CONCLUIDO em 21/08/2026
   -> SPB-266 (shadow mode — observacao, sem mudar comportamento real)
   -> SPB-267 (early-stop ativo) -- BLOQUEADO
   -> SPB-268 (Fast/Deep AUTO+PT5M) -- CONCLUIDO
```

SPB-266 esta mergeado e em observacao operacional real desde 24/08/2026, mas `shadow_missed_new_if_active` nao deve ser tratado como prova de perda real nem como autorizacao para early-stop. SPB-267 permanece bloqueado. SPB-268 concluiu a estrategia Fast/Deep com AUTO+PT5M homologado operacionalmente, mantendo full scan de 10 paginas aproximadamente a cada 10 minutos. SPB-269 segue relevante para medir o trafego oculto do notifier antes de qualquer cadencia mais agressiva; PT2M nao esta autorizado.

### TRILHO B — homologacao / SPB-263

```
B4 publish (push -> main -> deploy -> closeout) -- CONCLUIDO em 18/08/2026
   -> SPB-270 (F-01: alinhar ingest/DEBUG a APP_ENV) -- CONCLUIDO em producao
   -> SPB-271 (guardrail de URL em set_webhook) -- IMPLEMENTADO/TESTADO LOCALMENTE, aguardando review/deploy
   -> SPB-272 (hardening de isolamento pre-Fase E)
   -> Fase E -> Fase F -> Fase G -> Fase H -> Fase I
```

### TRILHO C — UX/UI

```
SPB-254 (correcoes funcionais: chip-x toque, switch teclado) -- CONCLUIDO em 20/08/2026
   -> SPB-250C (React + TypeScript + Vite acoplado ao Flask) -- SPB-250C-D `/ui-preview` experimental CONCLUIDO/MERGEADO, sem deploy
   -> SPB-250E (build/deploy controlado do React dist) -- CONCLUIDO; -> SPB-250F (`/` React atras de feature flag) -- IMPLEMENTACAO LOCAL
   -> SPB-255 (app shell: navbar, drawer mobile)
   -> SPB-251 (dashboard real: status, uso, oportunidades como nucleo, proxima acao e keywords compactas)
   -> SPB-256 (TelegramStatusCard + keywords)
   -> SPB-257 (auth + remocao do Tailwind CDN)
   -> SPB-258 (projetos como DataList responsivo)
   -> SPB-259 (landing + Pro no design system)
   -> SPB-252 (admin)
```

### Paralelismo

O shadow mode (SPB-266) consome tempo de calendario, nao capacidade de desenvolvimento — permite que o Trilho C avance em paralelo a partir de SPB-250 (sem mudanca visual). O Trilho B restante (SPB-271/SPB-272 + Fase E) e preferencialmente concluido antes do redesign pesado (SPB-251 em diante), porque e exatamente o tipo de mudanca que se beneficia de homologacao fisica para validar.

## NOW / NEXT / LATER

**NOW**

- SPB-271 — guardrail de URL em `set_webhook` implementado/testado localmente; pendente review, merge e deploy controlado.

**NEXT**

- SPB-272;
- SPB-269;
- Fase E / F / G;
- SPB-250I Telegram IPv4 para destravar deploy da landing React;
- SPB-250.

**LATER**

- SPB-267;
- redesign amplo de UI (SPB-255, 251, 256, 257, 258, 259, 252);
- Fase H / I;
- hardening residual (SPB-273, SPB-274).

## Proximos 5 passos

1. SPB-271 — review, merge e deploy controlado do guardrail de URL em `set_webhook`.
2. SPB-272 — hardening de isolamento pre-Fase E.
3. SPB-269 — medir trafego oculto do notifier antes de cadencia mais agressiva.
4. Fase E / F / G — homologacao fisica apos os gates pendentes.
5. SPB-250I / SPB-250 — seguir o trilho de React conforme gates operacionais.

## Limite de WIP

- no maximo 1 tarefa de codigo ativa por vez;
- no maximo 1 observacao passiva em andamento (ex.: shadow mode);
- no maximo 1 documento/design em preparacao.

Nao abrir o Trilho C amplo (a partir de SPB-255) enquanto o Trilho B critico restante (SPB-271/SPB-272 + Fase E) estiver em andamento, exceto SPB-254 e SPB-250, que sao independentes e sem mudanca visual/comportamental de risco.

## Gates

| Gate | Status |
|---|---|
| `B4_PUSH_GATE` | **APPROVE** |
| `B4_MAIN_INTEGRATION_GATE` | **APPROVE** |
| `B4_PRODUCTION_DEPLOY_GATE` | **APPROVE** (final) — condicoes comprovadas em 18/08/2026: `FLASK_ENV=production`/`APP_ENV=production` confirmados; cookie de producao continua `session` (`Secure`/`HttpOnly`/`SameSite=Lax`/`Path=/`, sem `Domain`); nenhum banner de homologacao apareceu em producao; suite completa executada na VPS com `.env` real (204/204); banco integro; HTTP saudavel (`HOME`/`LOGIN`/`REGISTER`=200, `ADMIN`=302); Telegram saudavel (`telegram_ready()=True`, webhook OK); Collector com `LastTaskResult=0` apos restauracao |
| `STRICT_HTTP_READY` | **PASS_LOCAL** — SPB-264 mergeado e validado no Collector local real em 20/08/2026 (`EXIT_CODE=0`, 10/10 paginas OK, parser OK 10/10, ingest OK); sem deploy VPS nesta etapa |
| `SHADOW_MODE_READY` | READY — `STRICT_HTTP_READY` e SPB-265 concluidos; proximo passo funcional e SPB-266 em modo shadow, sem mudar comportamento real |
| `EARLY_STOP_READY` | BLOCKED — o shadow atual nao prova seguranca de early-stop; `shadow_missed_new_if_active` nao deve ser usado como evidencia de perda real nem como autorizacao para reduzir cobertura |
| `FAST_DEEP_CUTOVER_READY` | **PASS** — SPB-268 mergeado e homologado com runner AUTO e Scheduled Task PT5M; sequencia real `DEEP -> FAST -> DEEP` comprovada |
| `CADENCE_5MIN_READY` | **PASS** — cadencia PT5M ativada apenas para Fast/Deep AUTO; full scan de 10 paginas preservado aproximadamente a cada 10 min |
| `PHASE_E_READINESS` | READY_AFTER_FIXES — SPB-270 implantado e validado em producao; ainda depende de SPB-272 + bot Telegram dedicado + procedimento de fingerprint de segredos |
| `PHASE_F_READINESS` | BLOCKED — depende da Fase E + SPB-271 |
| `PHASE_G_READINESS` | BLOCKED — depende da Fase F; ordem obrigatoria: TLS antes de Basic Auth |
| `PHASE_H_COMPLETE` | BLOCKED — depende da matriz de isolamento completa |
| `SPB_254_PRODUCTION_VALIDATION` | **PASS** — implantado e validado em producao em 20/08/2026, commit `588b861`: 213/213 na VPS, HTTP/banco/Telegram saudaveis, cookie `session` preservado, sem banner de homologacao, Collector restaurado (`LastTaskResult=0`), validacao manual do operador (desktop/teclado/mobile ~375px) PASS |
| `UI_FOUNDATION_READY` | READY — SPB-254 concluido; segue dependendo tambem de SPB-250 (ainda nao iniciado), sem exigir mudanca visual perceptivel |
| `UI_PRODUCTION_READY` | BLOCKED — depende de regressao visual (1440/768/390px) nas telas afetadas e testes do B4 continuando a passar (banner de homologacao intacto); `SPB_254_PRODUCTION_VALIDATION=PASS` nao equivale a este gate, que segue mais amplo |

## Metricas do coletor

Fatos observados (auditoria de 832 ciclos reais de `logs/collector.log`, periodo de 10 dias):

- 832 ciclos analisados;
- 61/832 ciclos com falha total de coleta (zero paginas coletadas) mas `EXIT_CODE=0` (~7,3%) — falha silenciosa, prioridade de confiabilidade;
- 76.888 projetos enviados no total;
- `inserted` (novos): 1.316 (~1,71%);
- `updated` (metadata alterada): 15.698 (~20,42%);
- `skipped` (inalterado): 59.874 (~77,87%);
- razao `updated`/`inserted`: ~11,9x;
- duracao do ciclo: mediana ~9,3s, p95 ~16,8s, maximo ~51,8s;
- Task Scheduler: `MultipleInstances=IgnoreNew` (ja evita sobreposicao, confirmado por leitura read-only).

**Hipotese, NAO fato**: media de ~2 paginas por ciclo pode bastar para cobrir a maioria dos ciclos. Isso NAO esta provado — apenas o shadow mode (SPB-266), rodando em producao por 7-14 dias, pode provar.

Baseline operacional apos SPB-268:

- paginas 1-2 verificadas aproximadamente a cada 5 minutos;
- paginas 1-10 verificadas aproximadamente a cada 10 minutos;
- ~12 GETs de listagem por 10 minutos (+20% sobre o baseline anterior).

## O que NAO fazer

- nao ativar early-stop; SPB-267 permanece bloqueado porque o shadow atual nao prova seguranca real;
- nao ativar PT2M nem cadencia mais agressiva sem novo gate explicito e sem SPB-269;
- nao fazer big bang de redesign de UI — um sprint, um PR, um criterio de aprovacao por vez;
- nao criar a homologacao copiando o diretorio ou o `.env` de producao — sempre `git clone` limpo + `.env` gerado do zero;
- nao usar o bot de producao em homologacao — o bot dedicado deve existir antes do provisionamento;
- nao expor a porta `8001` publicamente;
- nao iniciar a Fase E antes de SPB-272 e dos gates operacionais de isolamento estarem corrigidos.
