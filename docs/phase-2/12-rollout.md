# Rollout

## Processo padrao

1. Criar branch.
2. Rodar testes locais.
3. Commit.
4. Push.
5. Backup.
6. Preflight.
7. Pull fast-forward na VPS.
8. Compile.
9. Testes na VPS.
10. Migracao, se houver.
11. Restart.
12. Smoke test.
13. Observacao.
14. Rollback, se necessario.

## Mudanca sem schema

Exemplos: matcher, templates, CSS sem nova tabela.

Checklist:

- testes unitarios;
- `python -m compileall`;
- `git diff --check`;
- smoke local;
- deploy com backup por seguranca.

## Mudanca com schema

Checklist adicional:

- backup antes;
- migracao versionada;
- teste em copia;
- contagens antes/depois;
- plano de rollback;
- janela de baixa atividade.

## Mudanca visual

Checklist:

- screenshots desktop/mobile;
- contraste;
- foco;
- textos sem sobreposicao;
- estados vazios e loading.

## Mudanca de autenticacao

Checklist:

- login;
- logout;
- registro;
- CSRF;
- cookie seguro;
- reset se aplicavel;
- usuario comum vs admin.

## Mudanca de fila

Checklist:

- idempotencia;
- concorrencia;
- retentativas;
- falha por canal;
- sem duplicidade de Telegram;
- backlog observado.

## Mudanca destrutiva

Checklist:

- confirmacao explicita;
- backup validado;
- auditoria;
- transacao;
- bloqueio de autoexclusao;
- rollback testado.
