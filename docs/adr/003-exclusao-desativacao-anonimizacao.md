# ADR-003 - Desativacao, anonimizacao e exclusao permanente

## Status

Proposta.

## Contexto

O Admin futuro precisa remover ou bloquear usuarios sem confundir operacoes reversiveis, privacidade e destruicao permanente.

## Decisao

Separar tres acoes:

- desativacao;
- anonimizacao;
- exclusao permanente.

Exclusao permanente exige confirmacao forte, backup, transacao, auditoria e bloqueio de autoexclusao do admin.

## Consequencias

- Menor risco operacional.
- Mais clareza para suporte e LGPD futura.
- Requer modelo de auditoria e decisao de retencao.
