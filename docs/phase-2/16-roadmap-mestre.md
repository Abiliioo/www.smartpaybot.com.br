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
- SPB-270 (F-01: alinhar ingest/DEBUG a `APP_ENV`) **CONCLUIDO — IMPLANTADO e VALIDADO em producao em 21/08/2026**, PR #7, PR #8, Issue #6 fechada: `DEBUG` e ingest sensivel agora seguem `APP_ENV`; `homologation` e `production` sao fail-closed para `DEBUG=true` e ingest sem `INTERNAL_INGEST_TOKEN`. Deploy controlado via `scripts/deploy-production.ps1` atualizou producao de `588b86167f633faab812f23e3fbe0be0d534918c` para `15378dda90840579060e81be7cef3f47939ec6e9`: `DEPLOY_STATUS=SUCCESS`, `LOCAL_DEPLOY_EXIT_CODE=0`, testes remotos 241/241, smoke HTTP OK (`HOME=200`, `LOGIN=200`, `REGISTER=200`, `ADMIN=302`), cookie `session` preservado, banner de homologacao ausente, Telegram read-only OK, banco integro, `JOURNAL_ERROR_HITS=0`, rollback nao executado, Collector restaurado e ciclo automatico pos-deploy com `LastTaskResult=0`.

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
   -> SPB-265 (estado persistente + telemetria)
   -> SPB-266 (shadow mode — observacao, sem mudar comportamento real)
   -> SPB-267 (early-stop ativo, condicionado ao gate do shadow)
   -> SPB-268 (cadencia 10 -> 7 -> 5 min)
```

SPB-269 (medir trafego oculto do notifier) roda durante a janela do shadow (SPB-266) e e pre-requisito do gate de cadencia de 7 minutos.

### TRILHO B — homologacao / SPB-263

```
B4 publish (push -> main -> deploy -> closeout) -- CONCLUIDO em 18/08/2026
   -> SPB-270 (F-01: alinhar ingest/DEBUG a APP_ENV) -- CONCLUIDO em producao
   -> SPB-271 (guardrail de URL em set_webhook)
   -> SPB-272 (hardening de isolamento pre-Fase E)
   -> Fase E -> Fase F -> Fase G -> Fase H -> Fase I
```

### TRILHO C — UX/UI

```
SPB-254 (correcoes funcionais: chip-x toque, switch teclado) -- CONCLUIDO em 20/08/2026
   -> SPB-250 (design tokens)
   -> SPB-255 (app shell: navbar, drawer mobile)
   -> SPB-251 (dashboard: StatusBar)
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

- SPB-265.

**NEXT**

- SPB-271;
- SPB-272;
- SPB-266 (shadow rodando);
- SPB-269;
- Fase E / F / G;
- SPB-250.

**LATER**

- SPB-267;
- SPB-268;
- redesign amplo de UI (SPB-255, 251, 256, 257, 258, 259, 252);
- Fase H / I;
- hardening residual (SPB-273, SPB-274).

## Proximos 5 passos

1. SPB-265 — estado persistente + telemetria (prepara o shadow).
2. SPB-271 — guardrail de URL em `set_webhook` (continua o Trilho B apos SPB-270).
3. SPB-272 — hardening de isolamento pre-Fase E.
4. SPB-266 — shadow mode do Collector (observacao, sem mudar comportamento real).
5. SPB-269 — medir trafego oculto do notifier.

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
| `SHADOW_MODE_READY` | BLOCKED — depende de `STRICT_HTTP_READY` + SPB-265 |
| `EARLY_STOP_READY` | BLOCKED — depende de `missed_new_if_active = 0` em janela de 7-14 dias do shadow |
| `CADENCE_7MIN_READY` | BLOCKED — depende de early-stop estavel + SPB-269 concluido |
| `CADENCE_5MIN_READY` | BLOCKED — depende de 7 min estavel por >= 7 dias |
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

Projecoes condicionadas ao resultado do shadow (NAO registradas como promessa ao usuario final):

- reducao relevante de GET/hora ao 99Freelas;
- possibilidade futura de cadencia de 5 minutos;
- latencia media de alerta potencialmente menor.

## O que NAO fazer

- nao ativar early-stop sem o shadow mode ter fechado a janela de observacao com `missed_new_if_active = 0`;
- nao reduzir a cadencia para 5 minutos antes de medir o trafego do notifier (SPB-269);
- nao fazer big bang de redesign de UI — um sprint, um PR, um criterio de aprovacao por vez;
- nao criar a homologacao copiando o diretorio ou o `.env` de producao — sempre `git clone` limpo + `.env` gerado do zero;
- nao usar o bot de producao em homologacao — o bot dedicado deve existir antes do provisionamento;
- nao expor a porta `8001` publicamente;
- nao iniciar a Fase E antes de SPB-272 e dos gates operacionais de isolamento estarem corrigidos.
