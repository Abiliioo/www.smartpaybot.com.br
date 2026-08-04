# Definition of Done

Uma entrega da Fase 2 so deve ser considerada concluida quando:

- escopo e fora de escopo estao documentados;
- testes novos cobrem o comportamento alterado;
- suite relevante passa localmente;
- `git diff --check` passa;
- nenhum segredo, token, senha ou chat ID foi adicionado;
- rotas protegidas foram testadas com usuario comum e admin quando aplicavel;
- mudancas de schema tem backup, migracao e rollback;
- a experiencia mobile foi verificada quando ha UI;
- logs nao expoem PII desnecessaria;
- criterios de aceite do backlog foram cumpridos;
- rollout e rollback estao claros;
- documentacao foi atualizada quando a decisao muda arquitetura.

## Gates por tipo

### Matcher

- matriz lexical passa;
- termos curtos documentados;
- sem chamada externa;
- sem alterar banco.

### Admin

- permissao testada;
- auditoria para acoes sensiveis;
- confirmacao para acoes destrutivas;
- protecao contra autoexclusao.

### Senha

- token de uso unico;
- expiracao;
- resposta neutra;
- senha sempre com hash;
- rate limit.

### Alertas e canais

- idempotencia;
- falha isolada por canal;
- sem duplicidade;
- estado visivel ao usuario;
- retentativas limitadas.

### Design

- responsivo;
- acessivel;
- sem texto sobreposto;
- estados vazios;
- foco visivel.
