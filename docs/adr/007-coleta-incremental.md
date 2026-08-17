# ADR-007 — Coleta incremental fail-open

## Status

Proposta.

Esta ADR permanece em Proposta ate que o algoritmo candidato seja validado empiricamente pelo shadow mode (SPB-266) em producao. Nenhuma parte desta decisao deve ser lida como implementada ou ativada.

## Contexto

O coletor local (`scripts/local_collector_push.py`) roda via Windows Scheduled Task, varrendo sempre as 10 primeiras paginas de `/projects` do 99Freelas a cada ciclo (~10 minutos), independentemente de quantos projetos ja sejam conhecidos.

Uma auditoria forense sobre 832 ciclos reais registrados em `logs/collector.log` (periodo de 10 dias) confirmou:

- 61 dos 832 ciclos (~7,3%) tiveram falha total de coleta (zero paginas coletadas com sucesso) e ainda assim terminaram com `EXIT_CODE=0` — falha silenciosa, invisivel para o operador e para a Task Scheduler;
- de 76.888 projetos enviados no total, apenas 1.316 (~1,71%) eram efetivamente novos (`inserted`); 15.698 (~20,42%) eram projetos ja conhecidos com metadata alterada (`updated`); 59.874 (~77,87%) estavam inalterados (`skipped`);
- a razao `updated`/`inserted` e de aproximadamente 11,9x — a maior parte do trabalho do coletor e refresh de metadata, nao descoberta;
- rastreamento do consumo dessa metadata (`proposals`, `interested`, `client_rating`, `client_reviews`) mostrou que o matcher usa apenas o `title` do projeto e o notifier refaz o proprio scraping no momento do envio (`enrich_from_list_pages`), descartando o valor persistido pelo coletor — ou seja, a maior parte da metadata atualizada nao tem consumidor real hoje;
- o estado de deduplicacao (`seen_ids`) existe apenas durante uma unica execucao do processo — nao ha persistencia entre ciclos;
- `infrastructure.scraping.HttpClient.get_text` retorna o corpo da resposta mesmo quando o status HTTP e diferente de 200, apenas registrando um aviso — um bloqueio (403/429) ou pagina de challenge chegaria ao parser como HTML normal, produzindo poucos ou nenhum item, indistinguivel de uma pagina legitimamente sem novidades.

## Decisao proposta

Adotar uma arquitetura de coleta incremental **adaptive fail-open**, sujeita a validacao pelo shadow mode antes de qualquer ativacao real.

### Principios

1. Qualquer incerteza sobre o estado, o parser ou a resposta HTTP deve resultar em coletar MAIS paginas, nunca em parar mais cedo.
2. Early-stop e estritamente uma otimizacao de custo/latencia — nunca um mecanismo de correcao.
3. O numero maximo de paginas (`max-pages`, hoje 10) permanece como fallback de seguranca, independente do algoritmo incremental.
4. O estado local do coletor nunca e fonte de verdade. Ele e descartavel: apagar o arquivo de estado deve, no pior caso, causar um full scan no ciclo seguinte, nunca perda de capacidade de coleta.
5. O banco de dados da VPS (`projects_global`, via `/internal/ingest/projects`) continua sendo a unica fonte de verdade dos projetos ja ingeridos.
6. O checkpoint local so pode avancar depois de uma resposta HTTP 2xx do endpoint de ingest com corpo JSON valido. Se o scrape encontrar projetos novos mas o POST falhar, o checkpoint permanece no estado anterior, garantindo reprocessamento no proximo ciclo (idempotente, pois o upsert deduplica por `project_id`).
7. Estado ausente, corrompido, com `schema_version` desconhecida, ou mais velho que um limiar de idade (ex.: 60 minutos, cobrindo o gap operacional diario observado de ~10h) deve resultar em full scan das `max-pages` paginas.
8. Nenhuma forma de early-stop real deve ser ativada em producao antes de um periodo de shadow mode, no qual o algoritmo calcula onde pararia mas o coletor continua lendo todas as paginas normalmente, permitindo medir o impacto sem risco.

### Estado local proposto (indicativo, sujeito a refinamento em SPB-265)

- `schema_version`;
- `last_success_at` (timestamp do ultimo ciclo que avancou o checkpoint com sucesso);
- `watermark_published_ms` (maior `published_ms` ja ingerido com sucesso);
- `anchors` (IDs da primeira pagina do ultimo ciclo bem-sucedido);
- `recent_ids` (janela deslizante de IDs recentes conhecidos).

### Algoritmo candidato (nao final)

- ler no minimo 2 paginas por ciclo, independentemente de sinais de boundary (justificado pelo fato observado de que cada pagina tem exatamente 10 itens e apenas ~0,26% dos ciclos historicos tiveram mais de 20 projetos novos);
- combinar deteccao por `recent_ids` (janela deslizante), `anchors` (IDs da pagina 1 do ciclo anterior) e watermark de `published_ms`, pois cada sinal isolado tem um modo de falha conhecido (ver alternativas rejeitadas abaixo) e a combinacao cobre as falhas mutuamente;
- se nenhum sinal de boundary for encontrado ate `max-pages`, emitir o sinal operacional `boundary_not_found_within_max_pages` — condicao que deve gerar alerta, nao passar despercebida.

**Nota explicita**: a hipotese de que uma media de ~2 paginas por ciclo e suficiente para cobrir a coleta incremental na pratica **nao esta provada**. E uma hipotese derivada da distribuicao historica de `inserted` por ciclo (mediana 1, media 1,71, maximo 55 em 769 ciclos observados), nao uma garantia. O algoritmo final e os parametros exatos (tamanho da janela de `recent_ids`, limiar de idade do estado, numero minimo de paginas) dependem do resultado do shadow mode (SPB-266) e podem divergir do descrito aqui.

### Gate de ativacao (shadow mode)

Condicao obrigatoria antes de qualquer ativacao real (SPB-267):

```
missed_new_if_active = 0
```

isto e: nenhum projeto novo pode ter sido encontrado, durante toda a janela de observacao, em uma pagina posterior ao ponto em que o algoritmo hipoteticamente teria parado.

**Janela de observacao**: minimo de 7 dias corridos (incluindo um fim de semana completo), idealmente 14 dias, e deve incluir pelo menos 3 ciclos com mais de 10 projetos novos (eventos de burst), que sao os casos que mais testam a seguranca do algoritmo.

## Alternativas rejeitadas

| Alternativa | Por que foi considerada insuficiente isoladamente |
|---|---|
| Parar no primeiro ID ja conhecido (first known ID) | Um unico projeto fixado, reordenado ou republicado no topo interromperia a coleta imediatamente, sem nenhuma seguranca. Inseguro por construcao. |
| Parar quando uma pagina inteira contiver apenas IDs conhecidos (known page) | Nao cobre o caso de um projeto novo aparecer isolado apos uma pagina inteiramente conhecida (reordenacao parcial). |
| Parar apos N IDs conhecidos consecutivos (known streak) | A escolha de N e arbitraria sem dados sobre o comportamento real de ordenacao/reordenacao do site — nao ha prova de que a listagem seja estritamente cronologica ou estavel. |
| Usar apenas um conjunto de anchors do ciclo anterior | Falha se os projetos-ancora forem removidos (projeto fechado ou expirado desaparece da listagem). |
| Usar apenas o watermark de `published_ms` | O campo pode vir ausente (`None`) — o parser ja admite esse caso — e nao ha garantia de que a publicacao seja estritamente monotonica. |

Nenhuma evidencia sobre o comportamento real de paginacao do 99Freelas (ordenacao estritamente cronologica, existencia de itens fixados, possibilidade de reordenacao) esta disponivel hoje. O desenho fail-open trata essa ausencia de prova como incerteza a ser coberta por redundancia de sinais e por degradacao para full scan, nunca como premissa assumida.

## Consequencias

- Reducao esperada (nao garantida) do volume de requisicoes HTTP ao 99Freelas por ciclo, condicionada aos resultados do shadow mode.
- Introduz um novo artefato de estado local persistente no ambiente do coletor, que precisa ser tratado como descartavel e nunca versionado nem tratado como fonte de verdade.
- Exige, como pre-requisito, corrigir o contrato HTTP atual (`HttpClient.get_text`) para nunca entregar corpo de resposta de erro ao parser como se fosse HTML valido — sem essa correcao, nenhuma forma de early-stop pode ser considerada segura.
- Nao resolve nem pretende resolver a atualizacao de metadata de projetos antigos (`proposals`, `interested`, etc.); como esses campos nao tem consumidor identificado hoje (nem no matcher, nem na UI, nem persistentemente no notifier), esta ADR nao propoe um mecanismo de "background refresh" dedicado.
