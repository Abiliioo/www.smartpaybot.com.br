# ADR-001 - Caixa interna como fonte primaria dos alertas

## Status

Proposta.

## Contexto

Hoje o usuario percebe o Telegram como experiencia principal. Isso limita o produto quando o canal falha, nao esta vinculado ou o usuario quer historico interno.

## Decisao

Tratar a caixa interna de alertas como fonte primaria. Canais externos passam a ser formas de entrega, nao a fonte de verdade.

## Consequencias

- O usuario pode consultar alertas sem Telegram.
- O produto ganha historico e estados internos.
- A UI precisa de inbox, filtros e leitura.
- O schema precisa representar estado interno de alerta.
