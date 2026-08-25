# SmartPayBot frontend

Setup React + TypeScript + Vite para a migracao de UI do SmartPayBot.

## Scripts

```powershell
npm install
npm run typecheck
npm run build
npm run preview
```

`npm run dev` inicia o servidor Vite local para desenvolvimento quando uma fase futura pedir isso explicitamente.

## Estrategia

- Flask continua responsavel por API, autenticacao, sessao, regras de negocio, ingest, Telegram e banco.
- React roda same-origin e deve usar `fetch` nativo com cookies de sessao do Flask.
- O build do Vite sai em `../app/static/dist`.
- `app/static/dist/` nao e versionado nesta fase; o deploy futuro deve gerar o build localmente ou em CI antes de publicar.

## Escopo atual

Este frontend ainda nao substitui nenhuma tela Jinja. O app atual e um preview visual isolado com shell, brand/header, landing, dashboard e Pro usando dados mockados.
