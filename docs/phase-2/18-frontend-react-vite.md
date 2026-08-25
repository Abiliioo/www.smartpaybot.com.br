# Frontend React + TypeScript + Vite

## Objetivo

O SPB-250C-B criou a fundacao minima para migrar a interface do SmartPayBot para React + TypeScript + Vite, sem substituir telas existentes. O SPB-250C-C adiciona um preview visual isolado para validar shell, brand/header, landing, dashboard e Pro antes de qualquer integracao com Flask. O SPB-250C-C.1 refina esse preview com fallback local de marca, radius menos arredondados e correcoes de responsividade mobile. O SPB-250C-D adiciona a primeira integracao controlada com Flask pela rota experimental publica `/ui-preview`.

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

## Rota experimental `/ui-preview`

`/ui-preview` e uma rota publica e experimental. Ela existe apenas para validar que Flask consegue servir o build React pelo mesmo dominio da aplicacao, sem substituir nenhuma tela real.

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

Validar visualmente `/ui-preview` servido pelo Flask local em desktop e mobile, incluindo larguras proximas de 390px, 375px e 360px. Confirmar no Network que os assets de `dist/assets/` nao retornam 404. Depois disso, decidir a primeira rota real a migrar, ainda mantendo Jinja como rollback.
