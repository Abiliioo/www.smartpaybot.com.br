# Roadmap

## SPRINT 0 - Fundacao e baseline

Objetivo: preparar a base para evolucao com inventario tecnico, mapa de dados e criterio de seguranca.

Escopo:

- inventario tecnico;
- mapa de dados;
- baseline de testes;
- baseline de seguranca;
- inventario visual;
- criterios de migracao;
- definicao de feature flags;
- plano de rollback;
- preparacao de ambiente;
- definicao de contratos.

Fora de escopo: implementar matcher, Admin, senha, inbox ou redesign.

Dependencias: estado atual documentado e branch de trabalho isolada.

Tarefas:

- confirmar modelos, rotas e workers;
- mapear tabelas atuais e lacunas;
- definir matriz minima de testes;
- revisar `.env.example` sem valores reais;
- preparar plano de migracao incremental.

Criterios de aceite:

- backlog priorizado aprovado;
- primeiro item tecnico pronto para implementacao;
- riscos de schema e rollback registrados.

Testes obrigatorios: suite atual de unidade e `git diff --check`.

Riscos: documentacao ficar generica demais ou divergente do codigo.

Artefatos: docs da Fase 2, ADRs e checklist da Sprint 0.

Definicao de concluido: Sprint 1 pode iniciar por `SPB-201`.

## SPRINT 1 - Matcher e qualidade de alertas

Objetivo: corrigir correspondencia parcial e reduzir falsos positivos.

Escopo: limites lexicais, frases, pontuacao, termos curtos, testes e logs de match.

Fora de escopo: redesign, canais e schema de inbox.

Dependencias: testes de matcher antes da alteracao.

Criterios de aceite: `excel` nao casa com `excelente`; frases e separadores aceitos conforme matriz.

## SPRINT 2 - Admin e gestao de usuarios

Objetivo: tornar o Admin uma ferramenta operacional segura.

Escopo: listagem aprimorada, busca, filtros, detalhe, ativacao/desativacao, monitoramento, plano, exclusao segura, anonimizacao e auditoria.

Dependencias: modelo de auditoria e decisoes sobre exclusao.

Criterios de aceite: acoes sensiveis exigem confirmacao, sao auditadas e protegem o proprio admin.

## SPRINT 3 - Recuperacao de senha e seguranca

Objetivo: permitir recuperacao segura de conta.

Escopo: tokens de uso unico, expiracao, rate limit, email, mensagens neutras, invalidacao e testes de abuso.

Dependencias: provedor de email e tabela de tokens.

Criterios de aceite: fluxo nao revela se email existe e nao grava senha em claro.

## SPRINT 4 - Central interna de alertas

Objetivo: fazer do painel interno a fonte confiavel dos alertas.

Escopo: inbox, nao lidos, leitura, arquivamento, filtros, paginacao, pesquisa, estados e transicao de dados.

Dependencias: decisao entre estender `projects_per_user` ou separar entregas por canal.

Criterios de aceite: usuario consulta alertas mesmo sem Telegram.

## SPRINT 5 - Canais de notificacao

Objetivo: separar alerta interno de entrega externa.

Escopo: painel, Telegram, email, entregas por canal, retentativas, status, idempotencia, preferencias e resumo diario.

Dependencias: inbox interna e preferencias por usuario.

Criterios de aceite: falha em um canal nao bloqueia os outros.

## SPRINT 6 - Design system e redesign

Objetivo: elevar a experiencia visual para SaaS dark premium.

Escopo: tokens, sidebar, header, cards, dashboard, alertas, Admin, formularios, modais, responsividade, acessibilidade e microinteracoes.

Dependencias: mapa de telas e contratos de dados.

Criterios de aceite: telas principais responsivas, legiveis e consistentes.

## SPRINT 7 - Robustez operacional

Objetivo: fortalecer confiabilidade antes de escala.

Escopo: concorrencia, claim de fila, logs estruturados, painel de saude, backups, metricas, alertas operacionais, E2E, rollout e rollback.

Dependencias: estrategia de dados e fila definida.

Criterios de aceite: falhas sao rastreaveis, recuperaveis e nao geram duplicidade.
