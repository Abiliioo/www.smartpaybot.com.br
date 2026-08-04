# ADR-005 - Criterios para evoluir de SQLite para PostgreSQL

## Status

Proposta.

## Contexto

SQLite atende o beta, mas limita concorrencia, locks, fila com claim e volume administrativo.

## Decisao

Manter SQLite enquanto o volume e a operacao permitirem, mas preparar migracoes e criterios claros para PostgreSQL.

## Gatilhos

- multiplos workers;
- claim/lock de fila;
- crescimento de usuarios ativos;
- consultas administrativas pesadas;
- necessidade de relatorios historicos;
- risco operacional alto em SQLite.

## Consequencias

- Evita complexidade antes da hora.
- Obriga migracoes controladas antes de schema critico.
- Define PostgreSQL como caminho natural de escala.
