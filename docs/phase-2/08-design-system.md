# Design system

## Direcao visual

Referencia de inspiracao: `https://dribbble.com/shots/26151673-Financial-bank-components-UI-cards`.

A referencia deve orientar composicao, profundidade, contraste, modularidade e clareza. Nao copiar marca, icones, ilustracoes, layout proprietario ou ativos.

Direcao consolidada (auditoria UX/UI): **dark tecnico premium com contencao**. Nao usar glow excessivo, glassmorphism excessivo, nem aparencia de dashboard de template generico. Um destaque visual por vez, nunca varios elementos competindo por atencao na mesma tela.

## Principios visuais

- dashboard dark premium;
- fundo preto, chumbo ou azul-marinho profundo;
- azul intenso como destaque;
- cartoes modulares;
- hierarquia clara;
- alto contraste;
- minimalismo profissional;
- bordas discretas;
- sombras suaves;
- brilho moderado (glow contido, nunca decorativo em excesso);
- microinteracoes contidas;
- responsividade;
- acessibilidade.

## Decisao de shell / navegacao

**Top nav + drawer mobile.** Nao adotar sidebar.

Justificativa: o produto tem poucos destinos de navegacao primaria (Dashboard, Projetos, Pro, Admin condicional), o que nao justifica o custo permanente de largura de uma sidebar nem a complexidade adicional de um padrao de colapso. Top nav mantem a landing e o produto logado com a mesma linguagem de cabecalho, e um drawer mobile resolve a navegacao em telas pequenas sem introduzir um segundo paradigma de layout.

O `EnvironmentBanner` de homologacao (SPB-263 B4) deve permanecer integrado ao mesmo header, nunca como elemento sticky independente, e deve manter destaque visual proprio (nao reutilizar o mesmo tratamento de nenhum outro alerta da interface).

## Tokens conceituais

| token | uso |
|---|---|
| `surface-base` | fundo geral |
| `surface-card` | cards principais |
| `surface-elevated` | dropdowns, modais e overlays |
| `border-subtle` | divisores e contornos |
| `text-primary` | texto principal |
| `text-secondary` | texto auxiliar |
| `accent-primary` | acao primaria e destaques |
| `accent-hover` | estado hover |
| `status-success` | sucesso |
| `status-warning` | atencao |
| `status-error` | erro |

## Componentes esperados

- header (top nav) com drawer mobile;
- StatusBar (estado do sistema: monitoramento ativo, Telegram conectado, alertas do dia) como primeiro elemento do dashboard;
- TelegramStatusCard (estados: desconectado, aguardando codigo, conectado, erro, desabilitado);
- keywords com chip removivel — a acao de remover deve estar sempre acessivel, nunca depender apenas de hover;
- DataList responsivo para projetos (mesmo componente reflui de layout em grid no desktop para bloco empilhado no mobile, sem duplicar markup);
- cards de metricas;
- tabela de usuarios (admin, mais densa que o restante do produto);
- status do coletor;
- status da VPS;
- graficos operacionais;
- filtros;
- formularios;
- modais (substituindo confirmacoes via `confirm()`/`alert()` nativos);
- dropdowns;
- badges;
- skeleton loading;
- estados vazios (padrao unico: icone, titulo do que aconteceu, descricao do motivo, acao do que fazer);
- toasts;
- confirmacoes destrutivas.

## Sequencia canonica de implementacao

Ordem definida no roadmap mestre (`docs/phase-2/16-roadmap-mestre.md`), Trilho C:

```
SPB-254 (correcoes funcionais, sem redesign)
  -> SPB-250 (design tokens)
  -> SPB-255 (app shell: navbar, drawer mobile)
  -> SPB-251 (dashboard: StatusBar)
  -> SPB-256 (TelegramStatusCard + keywords)
  -> SPB-257 (auth + remocao do Tailwind CDN)
  -> SPB-258 (projetos como DataList responsivo)
  -> SPB-259 (landing + Pro migradas para o design system)
  -> SPB-252 (admin)
```

A landing (`app/templates/index.html`) e a pagina `/pro` sao migradas **para** o design system consolidado nesta pagina — nao devem ser tratadas como fonte de CSS a ser copiada para o restante do produto. Hoje ambas usam estilos inline extensivos, o que as torna a parte visualmente mais polida mas menos reutilizavel do produto.

`SPB-257` remove a dependencia de `https://cdn.tailwindcss.com` (hoje carregada em todas as paginas via `base.html`, apesar de usada apenas em login/register) no mesmo sprint em que essas telas sao reescritas com os componentes do design system — nunca isoladamente.

Redesenho amplo de UI (a partir de `SPB-251`) deve, preferencialmente, ser validado em ambiente de homologacao fisico (SPB-263, Fases E-H) antes de producao, quando esse ambiente estiver disponivel. Ate la, cada sprint segue o protocolo de regressao visual manual (1440px, 768px, 390px) descrito no criterio de aceite de cada ticket.

## Acessibilidade

- contraste AA para texto normal;
- foco visivel;
- estados nao dependentes apenas de cor;
- alvos clicaveis confortaveis;
- tabelas legiveis em mobile;
- textos que nao estouram containers.

## Responsividade

Priorizar mobile-first, com:

- navegacao adaptada;
- tabelas com densidade controlada;
- cards que preservam leitura;
- formularios empilhados em telas pequenas.

## Motion

Microinteracoes devem reforcar estado, nao decorar:

- hover leve;
- loading controlado;
- transicoes curtas;
- reducao de movimento respeitando preferencia do sistema.
