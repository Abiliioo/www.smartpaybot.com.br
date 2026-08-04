# ADR-002 - Separacao entre alerta e entrega por canal

## Status

Proposta.

## Contexto

`projects_per_user.notified_at` funciona para Telegram unico, mas nao modela email, painel, resumo diario, retentativas ou falhas por canal.

## Decisao

Separar alerta interno de entrega por canal. `projects_per_user` deve permanecer como item central do usuario, e uma tabela de entregas deve registrar status por canal.

## Consequencias

- Melhor idempotencia.
- Retentativas por canal.
- Mais clareza para suporte.
- Migracao e consultas ficam mais complexas.
