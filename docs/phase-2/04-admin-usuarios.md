# Admin de usuarios

## Estado atual

O Admin atual fica em `/admin/`, protegido por `login_required` e `admin_required`.

Capacidades atuais confirmadas:

- listar usuarios;
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

## Lacunas

- busca por nome, username e email;
- filtros por plano, status e Telegram;
- pagina de detalhes;
- ultimo acesso;
- status de monitoramento;
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
