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

### Matcher - SPB-203

O matcher registra um resumo agregado por ciclo para diagnostico operacional, sem persistir novas metricas e sem expor PII.

Campos registrados:

- `rule`;
- `lookback_min`;
- `users_with_keywords`;
- `keywords_total`;
- `projects_scanned`;
- `projects_with_matches`;
- `match_pairs_total`;
- `projections_created`;
- `blocked_by_daily_limit`;
- `duplicates_or_existing`;
- `duration_ms`.

Semantica dos principais contadores:

- `projects_with_matches` conta projetos com ao menos um par lexical;
- `match_pairs_total` conta pares usuario/keyword encontrados;
- `projections_created` conta registros efetivamente criados;
- `blocked_by_daily_limit` conta pares bloqueados pelo limite diario;
- `duplicates_or_existing` conta pares que nao criaram nova projecao por ja existir ou por concorrencia.

O resumo nao deve incluir titulo, link, keyword, texto de projeto, email, username, token ou identificador de usuario.

Validacao de producao em 05/08/2026:

- commit `5925c54` implantado;
- servico permaneceu ativo e respondeu HTTP 200;
- testes especificos de observabilidade passaram (`9 OK`);
- testes lexicais passaram (`6 OK`);
- suite completa passou (`33 OK`);
- primeiro ciclo real recebeu 100 projetos, inseriu 2, atualizou 17 e ignorou 81;
- o resumo agregado do primeiro ciclo registrou 3 usuarios com keywords, 13 keywords, 18 projetos avaliados, 1 projeto com match, 2 pares encontrados, 2 projecoes criadas, 0 bloqueios por limite, 0 duplicados/existentes e duracao de 22 ms;
- notifier enviou 2 alertas e registrou 0 falhas;
- segundo ciclo real recebeu 100 projetos, inseriu 0, atualizou 7 e ignorou 93;
- o resumo agregado do segundo ciclo registrou 17 projetos avaliados, 1 projeto com match, 2 pares encontrados, 0 projecoes criadas, 2 duplicados/existentes e duracao de 9 ms;
- o segundo ciclo confirmou idempotencia e deduplicacao;
- nenhum dado sensivel apareceu no resumo agregado observado.

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
