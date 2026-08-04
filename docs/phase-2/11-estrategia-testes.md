# Estrategia de testes

## Estado atual

O maior conjunto observado cobre `workers.notifier` com banco SQLite em memoria, mocks de Telegram e cenarios de elegibilidade. Existem probes de scraping e um arquivo de servicos vazio.

## Matriz

| funcionalidade | tipo de teste | cenarios | criterio de aprovacao |
|---|---|---|---|
| matcher | unitario | palavras completas, frases, acentos, hifen, barra, termos curtos | sem falsos positivos conhecidos |
| ingestao | integracao | payload valido, invalido, token ausente, token invalido | status e contadores corretos |
| notifier | unitario/integracao | elegiveis, inelegiveis, falha Telegram, limites | sem starvation e sem duplicidade |
| Telegram | mockado | webhook secret, start code, chat ja vinculado | sem chamada real em teste |
| Admin | funcional | permissao, filtros, plano, detalhe | usuario comum nao acessa |
| reset de senha | seguranca | token expira, uso unico, resposta neutra | nao enumera email |
| central de alertas | integracao | listar, ler, arquivar, filtrar | usuario ve apenas seus alertas |
| canais | unitario | entrega por canal, retentativa, idempotencia | falha isolada por canal |
| banco | migracao | upgrade, downgrade, contagens | rollback documentado |
| frontend | smoke/responsivo | dashboard, Admin, inbox, modais | sem quebra visual critica |
| acessibilidade | manual/automatizado | foco, contraste, teclado | fluxo essencial navegavel |
| rollout | smoke | healthz, login, ingest GET/POST autorizado controlado | deploy validado |

## Regras

- Nao enviar Telegram real em testes automatizados.
- Nao postar projetos falsos em producao.
- Usar banco isolado.
- Testes de migracao devem rodar em copia.
- Bugs confirmados devem ganhar teste antes ou junto da correcao.

## Baseline recomendado para Sprint 0

- Rodar `python -m unittest discover -v`.
- Manter `python -m unittest tests.test_notifier_queue -v`.
- Criar testes do matcher antes de alterar algoritmo.
- Adicionar fixtures minimas para usuarios, keywords e projetos.
