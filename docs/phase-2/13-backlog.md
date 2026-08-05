# Backlog priorizado

Estimativas: XS, S, M, L, XL. Prioridades: P0, P1, P2, P3.

| ID | titulo | prioridade | valor | descricao | dependencias | criterios de aceite | testes | riscos | estimativa | sprint |
|---|---|---|---|---|---|---|---|---|---|---|
| SPB-201 | Corrigir correspondencia parcial de palavras-chave | P0 | Reduz falsos positivos imediatamente | Implantado e validado em producao em 04/08/2026 (05/08/2026 UTC) | SPB-202 | `excel` nao casa com `excelente`; matriz lexical passa | `tests/test_keyword_matching.py` | monitorar novos falsos positivos com termos curtos | S | Sprint 1 |
| SPB-202 | Adicionar testes lexicais do matcher | P0 | Evita regressao | Implantado e validado em producao junto com o SPB-201 em 04/08/2026 (05/08/2026 UTC) | nenhuma | casos documentados automatizados | `tests/test_keyword_matching.py` | monitorar novas combinacoes lexicais ambiguas | S | Sprint 1 |
| SPB-203 | Registrar observabilidade minima de matches | P1 | Facilita diagnostico | Logar regra e contagem de matches sem PII sensivel | SPB-201 | logs sem segredos e com contadores | unitario/manual | excesso de log | M | Sprint 1 |
| SPB-210 | Criar listagem administrativa com busca e filtros | P1 | Melhora suporte | Buscar por username/email e filtrar por plano/status/Telegram | nenhuma | filtros combinaveis e paginacao definida | funcional Admin | expor PII demais | M | Sprint 2 |
| SPB-211 | Criar pagina de detalhes do usuario | P1 | Diagnostico operacional | Mostrar plano, Telegram, keywords, alertas e atividade | SPB-210 | detalhe protegido por admin | permissao e render | consulta pesada | M | Sprint 2 |
| SPB-212 | Implementar desativacao de conta | P1 | Controle operacional reversivel | Bloquear usuario sem apagar dados | SPB-215 recomendado | usuario desativado nao opera | auth/admin | bloquear admin por acidente | M | Sprint 2 |
| SPB-213 | Implementar exclusao segura | P1 | Reduz risco em operacoes destrutivas | Fluxo com resumo, backup, transacao e confirmacao forte | SPB-215 | autoexclusao bloqueada e auditoria criada | integracao/rollback | perda de dados | L | Sprint 2 |
| SPB-214 | Implementar anonimizacao de usuario | P2 | Privacidade e suporte futuro a retencao | Remover PII preservando agregados permitidos | SPB-215, politica de dados | PII removida sem quebrar metricas | integracao | anonimizar dados necessarios | L | Sprint 2 |
| SPB-215 | Criar auditoria administrativa | P1 | Rastreabilidade | Registrar ator, alvo, acao, data e metadados seguros | decisao de schema | acoes sensiveis auditadas | unitario/integracao | logar dado sensivel | M | Sprint 2 |
| SPB-220 | Implementar tokens de redefinicao | P1 | Recuperacao de conta | Token hash, uso unico e expiracao | migracao | token invalida apos uso/expiracao | seguranca | enumeracao de conta | M | Sprint 3 |
| SPB-221 | Implementar tela Esqueci minha senha | P1 | Autonomia do usuario | Formulario com resposta neutra | SPB-220, email | mensagem igual para email existente/inexistente | funcional | revelar existencia | M | Sprint 3 |
| SPB-222 | Configurar provedor de email transacional | P1 | Permite reset e canais | Definir SMTP/provedor, templates e logs | decisao de fornecedor | envio mockado em teste e real controlado | mock/integracao sandbox | secrets e entrega | M | Sprint 3 |
| SPB-223 | Invalidar sessoes apos troca de senha | P2 | Seguranca | Permitir encerrar sessoes existentes | SPB-220 | sessoes antigas invalidadas quando escolhido | auth | quebrar login atual | M | Sprint 3 |
| SPB-230 | Criar caixa interna de alertas | P1 | Produto menos dependente de Telegram | Inbox paginada por usuario | decisao ADR-001/002 | usuario ve seus alertas sem Telegram | integracao/autorizacao | backlog antigo confuso | L | Sprint 4 |
| SPB-231 | Implementar estado lido/nao lido | P1 | Melhora experiencia | Campos e acoes de leitura | SPB-230 | marcar um/todos como lido | integracao/UI | concorrencia simples | M | Sprint 4 |
| SPB-232 | Implementar arquivamento | P1 | Organizacao do usuario | Arquivar e filtrar arquivados | SPB-230 | alerta arquivado some do padrao | integracao/UI | ocultar alerta sem retorno | M | Sprint 4 |
| SPB-233 | Implementar filtros e pesquisa de alertas | P2 | Encontrabilidade | Filtrar por keyword, periodo e status | SPB-230 | filtros combinados funcionam | funcional | consultas lentas | M | Sprint 4 |
| SPB-240 | Criar entregas por canal | P1 | Base para multi-canal | Tabela/servico de status por canal | SPB-230 | Telegram registrado como entrega | unitario/integracao | duplicidade | L | Sprint 5 |
| SPB-241 | Adicionar preferencias de notificacao | P1 | Controle do usuario | Preferencias por canal e frequencia | SPB-240 | canal desativado nao envia | unitario/UI | confundir usuario | M | Sprint 5 |
| SPB-242 | Adicionar email imediato | P2 | Canal alternativo | Enviar alerta por email conforme preferencia | SPB-222, SPB-240 | email mockado e status registrado | mock/integracao | spam/entrega | M | Sprint 5 |
| SPB-243 | Adicionar resumo diario | P3 | Reduz ruido | Digest diario com alertas novos | SPB-240, SPB-241 | resumo idempotente por janela | unitario | duplicar resumo | L | Sprint 5 |
| SPB-250 | Criar design tokens | P2 | Consistencia visual | Tokens semanticos de cor, superficie e status | inventario visual | tokens documentados e aplicados incrementalmente | visual/manual | regressao visual | S | Sprint 6 |
| SPB-251 | Redesenhar dashboard | P2 | Experiencia SaaS premium | Nova hierarquia de metricas e alertas | SPB-250 | responsivo e acessivel | visual/responsivo | escopo crescer | L | Sprint 6 |
| SPB-252 | Redesenhar Admin | P2 | Operacao melhor | Tabela, filtros e detalhes alinhados ao design | SPB-210, SPB-250 | sem perda de acoes atuais | visual/funcional | quebrar admin | L | Sprint 6 |
| SPB-253 | Criar telas da central de alertas | P2 | Completa inbox | Feed/tabela, filtros, estados vazios e detalhes | SPB-230, SPB-250 | fluxo principal navegavel | visual/e2e | densidade ruim no mobile | L | Sprint 6 |
| SPB-260 | Implementar claim de fila | P1 | Evita duplicidade sob concorrencia | Reservar entregas antes de envio | SPB-240 | execucoes paralelas nao duplicam | concorrencia simulada | SQLite limitar solucao | L | Sprint 7 |
| SPB-261 | Adicionar painel de saude operacional | P2 | Suporte e observabilidade | Status coletor, ingest, notifier e canais | metricas basicas | painel mostra ultimo ciclo e falhas | funcional | metricas inconsistentes | M | Sprint 7 |
| SPB-262 | Estruturar backups e teste de restauracao | P1 | Recuperabilidade | Backup automatizado e teste de restore | decisao operacional | restore validado em copia | manual/documentado | backup invalido | M | Sprint 7 |
