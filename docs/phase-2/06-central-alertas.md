# Central interna de alertas

## Objetivo

O usuario nao deve depender exclusivamente do Telegram. O painel interno deve ser a fonte confiavel de alertas.

Fluxo futuro:

`projeto encontrado -> alerta persistido -> caixa interna -> canais externos opcionais`

## Estado atual

Hoje `projects_per_user` ja representa um projeto associado a um usuario e contem:

- `matched_keyword`;
- `created_at`;
- `notified_at`;
- `notify_attempts`;
- campos de projeto ganho.

Nao existem campos de leitura, arquivamento, descarte ou entrega por canal.

## Alternativa A - Estender `projects_per_user`

Adicionar campos diretamente:

- `read_at`;
- `archived_at`;
- `dismissed_at`;
- `created_at` ja existe.

Vantagens:

- menor migracao;
- reaproveita historico;
- menor complexidade inicial;
- consulta simples para inbox.

Desvantagens:

- mistura alerta interno, entrega externa e historico de ganho;
- escala pior quando houver varios canais;
- retentativas por canal ficam artificiais.

## Alternativa B - `projects_per_user` como alerta interno + entregas por canal

Manter `projects_per_user` como item central da caixa interna e criar tabelas auxiliares.

`notification_deliveries`:

- `id`;
- `project_per_user_id`;
- `channel`;
- `status`;
- `attempts`;
- `last_error_code`;
- `attempted_at`;
- `sent_at`;
- `created_at`;
- `updated_at`.

`user_notification_preferences`:

- `user_id`;
- `channel`;
- `enabled`;
- `immediate`;
- `digest_frequency`.

Vantagens:

- separa alerta de entrega;
- permite Telegram, email e painel sem duplicidade;
- melhora auditoria;
- facilita idempotencia;
- permite retentativas por canal;
- prepara resumo diario.

Desvantagens:

- exige migracao;
- aumenta consultas;
- requer desenho de estados.

## Comparacao

| criterio | Alternativa A | Alternativa B |
|---|---|---|
| complexidade | baixa | media |
| migracao | pequena | media |
| auditoria | limitada | forte |
| idempotencia | limitada | melhor |
| Telegram | simples | rastreavel por entrega |
| email | improvisado | natural |
| painel | bom | bom |
| retentativas | global | por canal |
| historico | misturado | separado |
| escalabilidade | limitada | melhor |

## Recomendacao

Adotar a Alternativa B, com evolucao incremental:

1. adicionar estado interno minimo em `projects_per_user`;
2. criar `notification_deliveries` antes de adicionar email;
3. criar preferencias por usuario quando houver mais de um canal real.

## Funcionalidades esperadas

- listar alertas;
- indicar nao lidos;
- marcar como lido;
- marcar todos como lidos;
- arquivar;
- descartar;
- pesquisar por titulo;
- filtrar por keyword, periodo e status;
- abrir projeto no 99Freelas;
- mostrar metadados ricos;
- mostrar status por canal;
- paginacao;
- estados vazios;
- loading;
- atualizacao automatica controlada.
