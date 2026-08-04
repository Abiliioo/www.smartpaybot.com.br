# Seguranca e observabilidade

## Threat model resumido

| area | risco | mitigacao proposta |
|---|---|---|
| login | forca bruta | rate limit persistente, logs e alertas |
| reset de senha | enumeracao de email | resposta neutra e token de uso unico |
| Admin | abuso de privilegio | auditoria, confirmacao e menor privilegio |
| exclusao | perda acidental de dados | backup, transacao e resumo de impacto |
| Telegram | webhook falso | secret obrigatorio em producao |
| ingestao | envio nao autorizado | token interno obrigatorio em producao |
| caixa de alertas | acesso cruzado | filtro por usuario e testes de autorizacao |
| email | vazamento de dados | templates minimizados e logs sem PII sensivel |
| uploads futuros | malware/abuso | fora de escopo ate haver necessidade real |
| sessoes | sequestro | cookies seguros e invalidacao futura |
| logs | segredo em log | mascaramento e politica de retencao |

## Controles atuais confirmados

- CSRF ativo no Flask-WTF.
- Webhook e ingest isentos de CSRF por necessidade, com secrets/tokens.
- Em producao, `SECRET_KEY` padrao e recusada.
- Login tem rate limit em memoria.
- Cookies de sessao usam `HTTPONLY`, `SAMESITE=Lax` e `SECURE` em producao.

## Controles propostos

- Rate limit persistente para login, reset e ingest.
- Auditoria administrativa estruturada.
- Mascaramento de segredos em logs.
- Politica de retencao de logs e PII.
- Backup automatizado com teste de restauracao.
- Invalidacao de sessoes apos troca de senha.
- Protecao contra acoes destrutivas por acidente.

## Observabilidade atual

O sistema registra eventos via logging em rotas, workers, Telegram, ingestao, matcher e notifier.

## Observabilidade proposta

Metricas:

- ciclos do coletor;
- projetos recebidos;
- projetos inseridos;
- projetos atualizados;
- projetos ignorados;
- matches criados;
- alertas criados;
- entregas por canal;
- falhas por canal;
- latencia ponta a ponta;
- backlog pendente;
- ultimo ciclo;
- saude da VPS;
- status do coletor local.

## Painel operacional futuro

Exibir:

- ultimo POST de ingestao;
- ultimos resultados do coletor;
- fila elegivel;
- fila inelegivel;
- falhas recentes;
- status Telegram;
- status email;
- status banco;
- tempo desde ultima execucao.
