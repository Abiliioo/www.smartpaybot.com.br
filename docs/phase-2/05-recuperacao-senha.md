# Recuperacao e redefinicao de senha

## Estado atual

O projeto tem login e registro com hash de senha via Werkzeug. Nao ha fluxo de "Esqueci minha senha", token de reset, envio de email ou invalidacao de sessoes.

## Fluxo do usuario

1. Usuario acessa "Esqueci minha senha".
2. Informa email.
3. Sistema retorna resposta neutra, sem revelar se o email existe.
4. Se houver conta elegivel, gera token de uso unico com expiracao.
5. Envia link seguro por email.
6. Usuario informa nova senha.
7. Sistema valida token, expiracao e uso unico.
8. Senha e atualizada com hash.
9. Token e invalidado.
10. Opcionalmente invalida sessoes existentes.

## Fluxo administrativo

1. Admin abre detalhe do usuario.
2. Admin inicia redefinicao.
3. Admin nao visualiza senha atual.
4. Admin nao define senha em texto aberto.
5. Sistema gera link ou token temporario.
6. Acao fica registrada em auditoria.

## Modelo proposto

Tabela `password_reset_tokens`:

- `id`;
- `user_id`;
- `token_hash`;
- `created_at`;
- `expires_at`;
- `used_at`;
- `requested_ip_hash`;
- `requested_user_agent_hash`;

Nunca persistir o token em texto claro.

## Email

Avaliar:

- SMTP simples;
- provedor transacional;
- templates HTML e texto;
- logs de entrega;
- retentativas;
- bounce/falha;
- protecao de secrets;
- remetente com dominio configurado.

## Rate limiting

Aplicar limites por:

- email normalizado;
- IP;
- usuario autenticado no caso administrativo;
- janela de tempo.

## Mensagens neutras

Usar resposta do tipo: "Se existir uma conta para este email, enviaremos instrucoes."

## Testes de seguranca

- token expira;
- token usado uma vez nao funciona de novo;
- token invalido nao revela conta;
- email inexistente responde igual;
- rate limit bloqueia abuso;
- senha fraca e rejeitada;
- Admin nao consegue ver senha;
- auditoria registra reset administrativo.
