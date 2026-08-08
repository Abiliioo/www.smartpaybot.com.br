# Admin de usuarios

## Estado atual

O Admin atual fica em `/admin/`, protegido por `login_required` e `admin_required`.

Status SPB-210: Implementado localmente, aguardando revisao e deploy.

Capacidades atuais confirmadas:

- listar usuarios;
- buscar por username ou email;
- filtrar por plano efetivo;
- filtrar por monitoramento;
- filtrar por Telegram vinculado;
- combinar filtros por query string;
- paginar a listagem;
- exibir total filtrado;
- exibir email;
- exibir plano;
- exibir data de subscription;
- exibir quantidade de keywords;
- exibir alertas de hoje;
- exibir total de projetos;
- indicar Telegram vinculado;
- ativar Pro;
- voltar para Free;
- alterar plano por rota.

## Listagem SPB-210

`GET /admin/` aceita os parametros:

- `q`: busca opcional por username ou email, case-insensitive, limitada a 100 caracteres;
- `plan`: `all`, `free`, `pro` ou `admin`;
- `monitoring`: `all`, `active` ou `inactive`;
- `telegram`: `all`, `linked` ou `unlinked`;
- `page`: pagina atual, com fallback seguro para `1`.

`monitoring` representa somente o status do monitoramento (`users.bot_active`). Ele nao representa conta ativa/inativa.

`plan` representa categorias visuais mutuamente exclusivas, nao apenas a assinatura:

- `admin`: `User.is_admin` verdadeiro, independente de existir ou nao assinatura associada;
- `pro`: `User.is_admin` falso e assinatura Pro ativa;
- `free`: `User.is_admin` falso e sem assinatura Pro ativa (inclui ausencia de assinatura e assinatura cancelada/inativa);
- `all`: todos os usuarios, sem restricao de categoria.

Administrador tem precedencia sobre qualquer plano: um usuario com `is_admin=True` aparece somente em `admin`, mesmo que possua assinatura Pro ativa. Ele nunca aparece em `free` nem em `pro`.

A paginacao usa tamanho fixo de 20 usuarios por pagina e nao aceita `page_size` enviado pelo usuario.

## Protecao de PII

A listagem nao exibe telefone, `chat_id`, `password_hash`, tokens ou codigos de vinculacao. O filtro por Telegram mostra apenas o estado vinculado/nao vinculado.

A consulta retorna uma projecao explicita de campos para o template. Objetos `User`, `Subscription` e `Plan` completos nao integram o resultado da listagem.

`password_hash`, telefone, `chat_id` e codigos internos nao sao selecionados como colunas retornadas. O `chat_id` e usado apenas para calcular o estado vinculado/nao vinculado.

As buscas usam SQLAlchemy com parametros e nao registram termos pesquisados em logs.

Curingas de `LIKE`, como `%` e `_`, sao tratados literalmente na busca textual.

## Fora de escopo do SPB-210

Conta ativa/inativa ainda nao existe como campo separado. O SPB-212 continua responsavel por desativacao de conta.

## Lacunas

- pagina de detalhes;
- ultimo acesso;
- alertas pendentes e falhos;
- atividade recente;
- ativar/desativar conta;
- ativar/desativar monitoramento;
- reset administrativo de senha;
- remocao segura;
- anonimizacao;
- auditoria estruturada.

## Matriz de permissoes proposta

| acao | admin | usuario | efeito | auditoria | confirmacao |
|---|---:|---:|---|---|---|
| listar usuarios | sim | nao | leitura operacional | nao obrigatoria | nao |
| buscar usuarios | sim | nao | leitura operacional | nao obrigatoria | nao |
| ver detalhe | sim | proprio perfil futuro | leitura de dados | recomendado | nao |
| alterar plano | sim | nao | atualiza subscription | sim | sim |
| ativar/desativar monitoramento | sim | sim, para si | altera `bot_active` | sim | sim |
| desativar conta | sim | nao | bloqueia acesso/envios | sim | sim |
| iniciar reset de senha | sim | usuario para si | cria token/link | sim | sim |
| anonimizar usuario | sim | nao | remove PII e preserva metricas | sim | confirmacao forte |
| excluir permanentemente | sim | nao | remove dados dependentes | sim | confirmacao forte |
| excluir proprio admin | nao | nao | bloqueado | sim | nao aplicavel |

## Exclusao segura

Separar tres operacoes:

- **Desativacao:** usuario permanece no banco, login e monitoramento podem ser bloqueados.
- **Anonimizacao:** remove ou substitui PII, preservando dados agregados quando permitido.
- **Exclusao permanente:** remove dados dependentes com transacao, backup previo e resumo de impacto.

## Protecoes obrigatorias

- Confirmacao explicita com nome/ID do usuario.
- Resumo dos dados afetados.
- Verificacao de dependencias.
- Transacao.
- Backup antes de operacao destrutiva.
- Registro de auditoria.
- Bloqueio de autoexclusao do administrador.
- Mensagens claras de sucesso, falha e rollback.

## Dados necessarios

Proposta futura:

- `users.is_active`;
- `users.disabled_at`;
- `users.last_login_at`;
- tabela `admin_audit_events`;
- possivel campo `deleted_at` para soft delete.

## Testes

- permissao de acesso Admin;
- usuario comum recebe 403;
- alteracao de plano;
- bloqueio de autoexclusao;
- auditoria de acoes sensiveis;
- rollback em falha de exclusao;
- filtros e busca sem vazar PII desnecessaria.
