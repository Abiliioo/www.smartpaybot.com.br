# ADR-004 - Correspondencia lexical de palavras-chave

## Status

Proposta.

## Contexto

O matcher atual usa substring normalizada. Isso faz `excel` casar com `excelente`.

## Decisao

Substituir substring por estrategia lexical, preservando normalizacao, acentos, frases e separadores.

## Consequencias

- Menos falsos positivos.
- Necessidade de matriz de testes.
- Termos curtos como `ia`, `api`, `ads`, `seo` e `vba` precisam de regra explicita.
