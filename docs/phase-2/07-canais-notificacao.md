# Canais de notificacao

## Estado atual

Canal real atual: Telegram.

O notifier envia diretamente via `infrastructure.telegram.send_message()` e usa `notified_at` em `projects_per_user` como marcador de sucesso. Isso funciona para canal unico, mas nao distingue painel, Telegram, email ou resumo.

## Canais futuros

- painel interno;
- Telegram;
- email imediato;
- resumo diario;
- integracoes futuras.

## Principio

Alerta e entrega sao coisas diferentes:

- alerta: oportunidade relevante para o usuario;
- entrega: tentativa de avisar por um canal.

## Estados propostos de entrega

- `pending`;
- `claimed`;
- `sent`;
- `failed`;
- `skipped`;
- `disabled`;
- `exhausted`.

## Idempotencia

Cada entrega deve ter chave logica por:

- `project_per_user_id`;
- `channel`;
- janela/resumo quando aplicavel.

## Preferencias

Preferencias por usuario devem controlar:

- canal habilitado;
- envio imediato;
- resumo diario;
- silencioso por horario futuro;
- fallback quando Telegram nao estiver vinculado.

## Retentativas

Retentativas devem ser por canal, com:

- contador;
- ultimo erro normalizado;
- horario da tentativa;
- limite maximo;
- politica de backoff.

## Recomendacao incremental

1. Preservar Telegram como canal inicial.
2. Criar entrega por canal sem mudar a experiencia do usuario.
3. Passar `notified_at` a representar compatibilidade legada ou derivar de entregas.
4. Adicionar email somente depois de provedor e templates definidos.
5. Adicionar resumo diario como canal separado, nao como efeito colateral do envio imediato.
