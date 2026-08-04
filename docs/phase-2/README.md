# SmartPayBot Fase 2

Esta pasta documenta a fase "Evolucao de Produto, Experiencia e Confiabilidade".

## Indice

1. [Visao geral](00-visao-geral.md)
2. [Estado atual](01-estado-atual.md)
3. [Roadmap](02-roadmap.md)
4. [Matcher de palavras-chave](03-matcher-palavras-chave.md)
5. [Admin de usuarios](04-admin-usuarios.md)
6. [Recuperacao de senha](05-recuperacao-senha.md)
7. [Central interna de alertas](06-central-alertas.md)
8. [Canais de notificacao](07-canais-notificacao.md)
9. [Design system](08-design-system.md)
10. [Seguranca e observabilidade](09-seguranca-observabilidade.md)
11. [Dados e migracoes](10-dados-migracoes.md)
12. [Estrategia de testes](11-estrategia-testes.md)
13. [Rollout](12-rollout.md)
14. [Backlog](13-backlog.md)
15. [Definition of Done](14-definition-of-done.md)
16. [Sprint 0 kickoff](15-sprint-0-kickoff.md)

## ADRs propostos

- [ADR-001: Caixa interna como fonte primaria dos alertas](../adr/001-caixa-interna-fonte-primaria.md)
- [ADR-002: Separacao entre alerta e entrega por canal](../adr/002-alerta-e-entrega-por-canal.md)
- [ADR-003: Desativacao, anonimizacao e exclusao permanente](../adr/003-exclusao-desativacao-anonimizacao.md)
- [ADR-004: Correspondencia lexical de palavras-chave](../adr/004-correspondencia-lexical.md)
- [ADR-005: Criterios para evoluir de SQLite para PostgreSQL](../adr/005-sqlite-para-postgresql.md)

## Regra de leitura

Os documentos separam:

- **Estado atual:** confirmado no codigo.
- **Proposta:** direcao recomendada para implementacao futura.
- **Decisao pendente:** ponto que ainda exige validacao antes de codigo ou migracao.
