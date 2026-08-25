# Frontend React + TypeScript + Vite

## Objetivo

O SPB-250C-B criou a fundacao minima para migrar a interface do SmartPayBot para React + TypeScript + Vite, sem substituir telas existentes. O SPB-250C-C adiciona um preview visual isolado para validar shell, brand/header, landing, dashboard e Pro antes de qualquer integracao com Flask.

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

## Preview atual

O preview React usa estado local para alternar entre:

- Landing;
- Dashboard;
- Pro.

Todos os dados sao mockados em `frontend/src/api/mockData.ts`. Nao ha chamadas reais para Flask, Telegram, ingest, banco ou collector.

## Proximo passo sugerido

Validar visualmente o preview local em desktop e mobile. Depois disso, a proxima fase deve escolher uma primeira superficie controlada para integracao, ainda mantendo Jinja como rollback.
