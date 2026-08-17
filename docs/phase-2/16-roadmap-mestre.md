# Roadmap mestre — SmartPayBot

Este documento e a fonte canonica de PRIORIDADE operacional do SmartPayBot a partir desta data. Consolida as conclusoes de quatro auditorias profundas (B4 forense adversarial, UX/UI, arquitetura/seguranca do SPB-263, coletor).

`docs/phase-2/02-roadmap.md` permanece no repositorio como roadmap/historico anterior (Sprint 0 da Fase 2) e nao deve ser apagado. A partir deste documento, a priorizacao corrente passa a ser mantida em `docs/phase-2/16-roadmap-mestre.md`.

Atualizar este documento a cada gate atravessado.

## Estado atual

- SPB-263 B1/B2 concluidos e validados em producao (commit `7e65bd9`, 08/08/2026).
- SPB-263 B3 concluido e validado em producao (commits `0c41b25`/`18ac2b1`/`fc3b91c`, 09/08/2026).
- SPB-263 Fase D (inspecao read-only da VPS) concluida em 16/08/2026, sem bloqueadores.
- SPB-263 B4 implementado, testado (204/204) e auditado localmente na branch `feat/spb-263-homologation-ui-session`, commit:
  `643d2b98ed764f4f487799d988a783686e14f7cb`
- B4 implementado, testado e auditado. Ainda nao implantado em producao. Proximo gate: integracao em `main` e deploy controlado.
- Fases E-I do SPB-263 (clone fisico de homologacao, DNS/Nginx/TLS, protecao externa, isolamento end-to-end, closeout) nao iniciadas.
- ADR-006 (ambiente de homologacao isolado): status **Proposta**.
- SPB-263: **EM ANDAMENTO**.

## Principio de priorizacao

Cadeia de receita do produto:

```
ativacao -> valor percebido -> atrito de limite -> upgrade
```

Findings das auditorias sao priorizados pelo impacto nessa cadeia, nao apenas por severidade tecnica isolada. Risco entra na frente quando bloqueia genuinamente algo na cadeia (ex.: F-01 bloqueia a Fase E). Confiabilidade e valor percebido vem antes de polish visual amplo.

## Trilhos

### TRILHO A — confiabilidade / coletor

```
SPB-264 (correcao: HTTP estrito, parser health, exit codes, retry, log seguro)
   -> SPB-265 (estado persistente + telemetria)
   -> SPB-266 (shadow mode — observacao, sem mudar comportamento real)
   -> SPB-267 (early-stop ativo, condicionado ao gate do shadow)
   -> SPB-268 (cadencia 10 -> 7 -> 5 min)
```

SPB-269 (medir trafego oculto do notifier) roda durante a janela do shadow (SPB-266) e e pre-requisito do gate de cadencia de 7 minutos.

### TRILHO B — homologacao / SPB-263

```
B4 publish (push -> main -> deploy -> closeout)
   -> SPB-270 (F-01: alinhar ingest/DEBUG a APP_ENV)
   -> SPB-271 (guardrail de URL em set_webhook)
   -> SPB-272 (hardening de isolamento pre-Fase E)
   -> Fase E -> Fase F -> Fase G -> Fase H -> Fase I
```

### TRILHO C — UX/UI

```
SPB-254 (correcoes funcionais: chip-x toque, switch teclado)
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

O shadow mode (SPB-266) consome tempo de calendario, nao capacidade de desenvolvimento — permite que o Trilho C avance em paralelo a partir de SPB-250 (sem mudanca visual). O Trilho B (F-01 + Fase E) e preferencialmente concluido antes do redesign pesado (SPB-251 em diante), porque e exatamente o tipo de mudanca que se beneficia de homologacao fisica para validar.

## NOW / NEXT / LATER

**NOW**

- publicar B4 (push -> main -> deploy -> closeout);
- SPB-254;
- SPB-264;
- SPB-270.

**NEXT**

- SPB-265;
- SPB-266 (shadow rodando);
- SPB-269;
- SPB-271;
- SPB-272;
- Fase E / F / G;
- SPB-250.

**LATER**

- SPB-267;
- SPB-268;
- redesign amplo de UI (SPB-255, 251, 256, 257, 258, 259, 252);
- Fase H / I;
- hardening residual (SPB-273, SPB-274).

## Proximos 5 passos

1. Publicar B4 (push da branch -> fast-forward em `main` -> deploy em producao -> closeout documental).
2. SPB-254 — correcoes funcionais de UI.
3. SPB-264 — coletor: correcao (HTTP estrito, exit codes, parser health).
4. SPB-270 — F-01 (desbloqueia a Fase E).
5. SPB-265 — estado persistente + telemetria (prepara o shadow).

## Limite de WIP

- no maximo 1 tarefa de codigo ativa por vez;
- no maximo 1 observacao passiva em andamento (ex.: shadow mode);
- no maximo 1 documento/design em preparacao.

Nao abrir o Trilho C amplo (a partir de SPB-255) enquanto o Trilho B critico (F-01 + Fase E) estiver em andamento, exceto SPB-254 e SPB-250, que sao independentes e sem mudanca visual/comportamental de risco.

## Gates

| Gate | Status |
|---|---|
| `B4_PUSH_GATE` | **APPROVE** |
| `B4_MAIN_INTEGRATION_GATE` | **APPROVE** |
| `B4_PRODUCTION_DEPLOY_GATE` | **APPROVE_WITH_CONDITIONS** — confirmar `FLASK_ENV=production` mantido; cookie de producao continua `session`; nenhum banner de homologacao aparece em producao; suite completa executada na VPS com `.env` real |
| `STRICT_HTTP_READY` | READY_AFTER_FIXES — depende de SPB-264 + observacao de 24-48h |
| `SHADOW_MODE_READY` | BLOCKED — depende de `STRICT_HTTP_READY` + SPB-265 |
| `EARLY_STOP_READY` | BLOCKED — depende de `missed_new_if_active = 0` em janela de 7-14 dias do shadow |
| `CADENCE_7MIN_READY` | BLOCKED — depende de early-stop estavel + SPB-269 concluido |
| `CADENCE_5MIN_READY` | BLOCKED — depende de 7 min estavel por >= 7 dias |
| `PHASE_E_READINESS` | READY_AFTER_FIXES — depende de SPB-270 + SPB-272 + bot Telegram dedicado + procedimento de fingerprint de segredos |
| `PHASE_F_READINESS` | BLOCKED — depende da Fase E + SPB-271 |
| `PHASE_G_READINESS` | BLOCKED — depende da Fase F; ordem obrigatoria: TLS antes de Basic Auth |
| `PHASE_H_COMPLETE` | BLOCKED — depende da matriz de isolamento completa |
| `UI_FOUNDATION_READY` | READY — SPB-254 + SPB-250, sem exigir mudanca visual perceptivel |
| `UI_PRODUCTION_READY` | BLOCKED — depende de regressao visual (1440/768/390px) nas telas afetadas e testes do B4 continuando a passar (banner de homologacao intacto) |

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
- nao iniciar a Fase E antes de SPB-270 (F-01) estar corrigido.
