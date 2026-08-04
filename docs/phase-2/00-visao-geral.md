# Fase 2 - Evolucao de Produto, Experiencia e Confiabilidade

## Contexto

O SmartPayBot esta operacional em producao como um SaaS beta. O fluxo atual usa um coletor local, executado pelo Agendador do Windows, que envia projetos para `/internal/ingest/projects` na VPS. A aplicacao Flask persiste os projetos, executa matcher, prepara notificacoes e envia alertas via Telegram.

## Motivacao

O produto ja prova valor operacional, mas ainda depende demais do Telegram, tem matching por substring, possui Admin limitado e nao oferece mecanismos completos de recuperacao de conta, caixa interna de alertas, canais alternativos ou observabilidade de produto.

## Problemas atuais

- O matcher considera `excel` dentro de `excelente`.
- Telegram funciona como canal principal de entrega e tambem como experiencia central percebida.
- O Admin lista usuarios e altera planos, mas nao tem busca, filtros, detalhes, bloqueios, exclusao segura nem trilha de auditoria estruturada.
- Nao ha fluxo de recuperacao ou redefinicao segura de senha.
- Alertas nao tem estado interno rico de leitura, arquivamento, descarte e entrega por canal.
- O schema ainda evolui sem migracoes versionadas.
- Observabilidade operacional existe principalmente via logs.

## Objetivos

- Melhorar a precisao do matcher.
- Transformar alertas em itens persistidos do produto, independentes de Telegram.
- Expandir o Admin para gestao operacional segura.
- Criar base para recuperacao de senha e email transacional.
- Preparar multiplos canais de notificacao.
- Atualizar a experiencia visual para um dashboard SaaS dark premium.
- Fortalecer seguranca, auditoria, dados, testes e rollout.

## Principios

- Painel interno como fonte confiavel.
- Telegram como canal, nao como banco.
- Seguranca por padrao.
- Acoes destrutivas explicitas.
- Observabilidade antes de automacao.
- Migracoes reversiveis.
- Testes antes de deploy.
- Evolucao incremental.
- Mobile-first.
- Acessibilidade.
- Sem dependencias complexas sem necessidade.

## Escopo

- Documentar arquitetura atual e proposta.
- Organizar roadmap, backlog e Sprint 0.
- Definir direcoes iniciais para matcher, Admin, senha, alertas, canais, design, seguranca, dados e testes.
- Registrar ADRs propostos.

## Fora de escopo

- Implementar funcionalidades.
- Alterar banco.
- Criar migracoes.
- Alterar coletor, scheduler, notifier, templates, CSS ou JavaScript.
- Acessar VPS, SSH, Agendador do Windows ou Telegram.
- Enviar projetos ou mensagens reais.

## Riscos

- Mudanca de schema sem migracao pode quebrar producao.
- Central de alertas mal modelada pode duplicar responsabilidades de `projects_per_user`.
- Canais externos sem idempotencia podem duplicar envios.
- Admin com acoes destrutivas sem auditoria aumenta risco operacional.
- Redesign grande demais pode atrasar melhorias de produto mais urgentes.

## Criterios de sucesso

- O matcher reduz falsos positivos sem perder matches relevantes.
- O usuario consegue consultar alertas no painel mesmo sem Telegram.
- Admins conseguem diagnosticar usuarios e planos sem acesso direto ao banco.
- Recuperacao de senha nao revela existencia de email e usa token de uso unico.
- Entregas por canal sao rastreaveis e reprocessaveis.
- Deploys passam por testes, backup, preflight e rollback definido.

## Indicadores de produto

- Taxa de alertas abertos no painel.
- Taxa de alertas enviados por canal.
- Alertas lidos por usuario ativo.
- Conversao de alerta em projeto ganho.
- Usuarios com Telegram vinculado.
- Usuarios com monitoramento ativo.
- Retencao semanal de usuarios ativos.

## Indicadores tecnicos

- Projetos recebidos, inseridos, atualizados e ignorados.
- Matches criados.
- Alertas elegiveis, enviados, falhos e pendentes.
- Falhas por canal.
- Latencia do ciclo coletor -> alerta.
- Ultimo ciclo do coletor.
- Backlog da fila.
- Erros de ingestao e autenticacao.
- Tempo de resposta das rotas principais.
