# Frontend React + TypeScript + Vite

## Objetivo

O SPB-250C-B criou a fundacao minima para migrar a interface do SmartPayBot para React + TypeScript + Vite, sem substituir telas existentes. O SPB-250C-C adicionou um preview visual isolado para validar shell, brand/header, landing, dashboard e Pro antes de qualquer integracao com Flask. O SPB-250C-C.1 refinou esse preview com fallback local de marca, radius menos arredondados e correcoes de responsividade mobile. O SPB-250C-D adicionou e mergeou, via PR #21, a primeira integracao controlada com Flask pela rota experimental publica `/ui-preview`.

## Estrategia

- Backend permanece Flask.
- Flask continua responsavel por API, autenticacao, sessao, regras de negocio, ingest, Telegram e banco.
- React deve operar same-origin, sem CORS.
- Admin permanece Jinja inicialmente.
- Landing, dashboard, Pro, auth e projetos nao foram migrados nesta fase.

## Estrutura

```text
frontend/
  package.json
  package-lock.json
  vite.config.ts
  tsconfig*.json
  src/
    api/
    assets/
    components/
      BrandMark.tsx
      Button.tsx
      Card.tsx
      KeywordPill.tsx
      MetricCard.tsx
      Pill.tsx
      PlanCard.tsx
      PreviewNav.tsx
      SectionHeader.tsx
      StepCard.tsx
      TelegramPanel.tsx
      UserBadge.tsx
    layouts/
      AppHeader.tsx
      AppShell.tsx
    pages/
      DashboardPreview.tsx
      LandingPreview.tsx
      ProPreview.tsx
    styles/
      index.css
    App.tsx
    main.tsx
```

## Comandos

```powershell
cd frontend
npm install
npm run typecheck
npm run build
```

`npm run dev` e `npm run preview` existem, mas nao sao parte obrigatoria dos gates desta fase.

## Build

O Vite gera assets em:

```text
app/static/dist/
```

O diretorio `app/static/dist/` fica ignorado pelo Git nesta fase. A decisao evita versionar artefatos gerados antes de definir o fluxo final de CI/deploy. Uma fase futura deve decidir se o build roda localmente, em CI ou durante uma etapa controlada antes da publicacao.

O build tambem gera:

```text
app/static/dist/.vite/manifest.json
```

O Flask usa esse manifest para localizar o JS principal e os CSS hashados do Vite. Os caminhos expostos ao template sao sempre relativos ao static folder, por exemplo `dist/assets/index-*.js`, nunca caminhos absolutos do filesystem.

## Deploy controlado do dist

O SPB-250E adicionou suporte para publicar o build React sem instalar Node na VPS e sem versionar `app/static/dist/`. O fluxo fica explicito no deploy local:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy-production.ps1 -BuildReactDist
```

Com `-BuildReactDist`, o orquestrador local roda `npm.cmd run typecheck`, `npm.cmd run build`, valida o manifest/assets dentro de `app/static/dist`, empacota esse diretorio em um `.tar.gz` temporario e envia o artefato junto com o script remoto. A VPS apenas extrai, valida e instala o artefato em `/home/deploy/apps/www.smartpaybot.com.br/app/static/dist`.

Sem `-BuildReactDist`, o deploy legado continua compativel e nenhum asset React e enviado. Nesse caso, `/ui-preview` em producao pode continuar retornando 503 controlado se o dist nao existir. `app/static/dist/` permanece ignorado pelo Git.

Para validar esse fluxo antes de merge/review, sem exigir `main` e sem tocar VPS, Scheduled Task ou deploy, use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy-production.ps1 -ValidateReactDistOnly
```

Esse gate local-only executa typecheck, build, validacao de manifest/assets, empacotamento `.tar.gz` temporario e limpeza. Em sucesso, imprime `REACT_DIST_LOCAL_VALIDATION=PASS`.

## Landing React controlada por flag

O SPB-250F introduz a primeira rota real controlada em React: a home `/` pode renderizar a landing React quando `REACT_LANDING_ENABLED` estiver explicitamente ativo (`1`, `true`, `yes` ou `on`). O padrao seguro continua desligado, mantendo `index.html` Jinja.

Quando a flag esta ativa, Flask usa o mesmo manifest Vite de `/ui-preview` para carregar JS/CSS hashados no `react_shell.html`, mas em modo `landing` com `robots=index, follow`. Se o build/manifest estiver ausente ou invalido, a home cai de volta para `index.html` em vez de retornar 503, preservando a pagina publica principal.

`/ui-preview` continua experimental, navegavel entre Landing/Dashboard/Pro e com `robots=noindex, nofollow`; sem build, segue retornando 503 controlado. A rota `/pro`, auth, dashboard e admin continuam Jinja. A landing React usa CTAs reais para `/auth/register`, `/auth/login`, `/dashboard/` e `/pro` somente quando servida em `/`; no preview, a navegacao interna por estado local continua disponivel.

## Rota experimental `/ui-preview`

`/ui-preview` e uma rota publica e experimental. Ela existe apenas para validar que Flask consegue servir o build React pelo mesmo dominio da aplicacao, sem substituir nenhuma tela real.

Estado atual:

- fundacao React/Vite mergeada via PR #19;
- rota `/ui-preview` mergeada via PR #21;
- visual validado no navegador via Flask local em `127.0.0.1:5000/ui-preview`;
- Network confirmou assets JS/CSS com status 200;
- build local e necessario antes de acessar `/ui-preview`;
- `app/static/dist/` continua ignorado e nao versionado;
- producao ainda nao recebe essa rota sem deploy e sem build no ambiente de publicacao;
- `/`, `/pro`, auth, dashboard e admin continuam Jinja.

Com build presente, a rota renderiza `app/templates/react_shell.html`, que contem:

- HTML minimo em `pt-BR`;
- `<div id="root"></div>`;
- CSS resolvido pelo manifest;
- JS principal com `type="module"`;
- `noindex`;
- sem Tailwind CDN e sem herdar `base.html`.

Se `app/static/dist/.vite/manifest.json` nao existir ou estiver invalido, `/ui-preview` retorna HTTP 503 com a mensagem:

```text
React build nao encontrado. Rode `npm.cmd run build` em `frontend`.
```

Essa falha e intencional e controlada: evita 404 silencioso de assets e deixa claro que o preview depende de um build local.

## Preview atual

O preview React usa estado local para alternar entre:

- Landing;
- Dashboard;
- Pro.

Todos os dados sao mockados em `frontend/src/api/mockData.ts`. Nao ha chamadas reais para Flask, Telegram, ingest, banco ou collector.

O header do preview nao depende de `/static/images/logo.svg` enquanto roda no Vite: a marca usa um icone local em React/CSS, mantendo o wordmark `SmartPayBot` com `SmartPay` claro e `Bot` azul ate a revisao do asset final.

## Proximo passo sugerido

Depois da revisao remota do SPB-250E, executar um deploy gate proprio com `-BuildReactDist` para validar `/ui-preview` em producao. So entao escolher a primeira rota real a migrar, ainda mantendo Jinja como rollback. Nao migrar dashboard antes de existir API/contratos suficientes para usuario atual, plano, Telegram, keywords, alertas e projetos.
