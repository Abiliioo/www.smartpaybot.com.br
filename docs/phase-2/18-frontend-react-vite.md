# Frontend React + TypeScript + Vite

## Objetivo

O SPB-250C-B cria a fundacao minima para migrar a interface do SmartPayBot para React + TypeScript + Vite, sem substituir telas existentes.

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
    layouts/
    pages/
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

## Proximo passo sugerido

SPB-250C-C deve criar um shell React/header/brand isolado ou uma landing React estatica aprovada por print, ainda sem substituir rotas principais.
