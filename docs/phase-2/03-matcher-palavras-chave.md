# Matcher de palavras-chave

## Estado atual

`domain/services/projects_service.py` implementa `match_users_for_title()`.

Algoritmo atual:

1. normaliza o titulo com `normalize_text()`;
2. normaliza a keyword com `clean_keyword()`;
3. considera match quando `nkw in nt`.

Isso preserva lowercase e remocao de acentos, mas gera falso positivo por substring.

## Bug confirmado

Keyword: `excel`

Resultado atual indevido:

- `excelente oportunidade` casa com `excel`.

Comportamento esperado:

- `Planilha em Excel`: match.
- `Excel/VBA`: match.
- `Curso de Excel avancado`: match.
- `Excelente profissional`: sem match.
- `Trabalho excelente`: sem match.
- `Excelencia no atendimento`: sem match.

## Comportamento desejado

- Matching case-insensitive.
- Equivalencia sem acentos.
- Palavra completa.
- Frase composta.
- Pontuacao como separador.
- Hifen e barra tratados conscientemente.
- Espacos multiplos normalizados.
- Termos curtos com regra explicita.

## Alternativas

### Alternativa A - Regex com limites lexicais

Gerar padrao por keyword normalizada, escapando caracteres especiais e usando limites que considerem letras e numeros como corpo de palavra.

Vantagens: simples, baixo impacto, facil de testar.

Riscos: regras de Unicode e separadores precisam ser bem definidas.

### Alternativa B - Tokenizacao

Tokenizar titulo e keyword em termos, comparar sequencias de tokens.

Vantagens: comportamento claro para frases e separadores.

Riscos: mais codigo e decisoes para hifen, barra e termos como `c#`.

### Alternativa C - Estrategia hibrida

Normalizar, tokenizar e usar regex apenas para casos especificos.

Vantagens: flexivel.

Riscos: pode ficar dificil de manter cedo demais.

## Recomendacao

Comecar com tokenizacao simples ou regex lexical bem testada, sem dependencia externa. A primeira entrega deve focar em corrigir falsos positivos conhecidos e proteger termos curtos.

## Implementacao local - SPB-201

Status: Implantado e validado em producao em 04/08/2026 (05/08/2026 UTC).

A implementacao adotada centraliza a regra em `domain/services/keywords_service.py::keyword_matches_text()`.

Estrategia efetiva:

1. normalizar keyword e texto com a mesma funcao existente;
2. dividir a keyword em tokens usando espaco, hifen e barra como separadores;
3. escapar cada token com `re.escape`;
4. aceitar espaco, hifen ou barra entre tokens;
5. exigir que nao haja caractere alfanumerico imediatamente antes ou depois da expressao.

Com isso, `excel` deixa de casar com `excelente`, enquanto `Excel/VBA`, `Excel-VBA`, `Mercado-Livre` e `mercado/livre` casam como separadores lexicais.

Testes adicionados em `tests/test_keyword_matching.py` cobrem palavras simples, termos curtos, frases, pontuacao, acentos, caixa e caracteres especiais tratados literalmente.

Validacao de producao:

- commit `b3fbbd8` implantado;
- testes especificos e suite completa passaram antes do deploy;
- ciclo automatico do coletor apos o deploy concluido com resultado `0`;
- validacao direta do matcher passou;
- nenhum falso positivo real de `excel` em `excelente` foi encontrado apos o deploy (`falsos_positivos_reais: 0`).

## Matriz de casos

| keyword | texto | esperado | justificativa |
|---|---|---|---|
| excel | Excel avancado | match | palavra completa |
| excel | excelente | sem match | substring dentro de palavra |
| excel | Excel-VBA | match | hifen como separador operacional |
| mercado livre | Mercado Livre | match | frase exata normalizada |
| mercado livre | Mercado-Livre | match | hifen foi adotado como separador lexical equivalente |
| mercado livre | mercado/livre | match | barra foi adotada como separador lexical equivalente |
| mercado livre | mercado livreiro | sem match | `livre` nao deve casar dentro de `livreiro` |
| python | Python/Django | match | barra como separador |
| python | pythonista | sem match | substring dentro de palavra |
| ia | inteligencia artificial | decisao pendente | sigla curta pode exigir termo isolado ou sinonimos |
| ia | secretaria | sem match | substring curta dentro de palavra |
| api | API REST | match | sigla isolada |
| api | capital | sem match | substring dentro de palavra |
| ads | Google Ads | match | sigla/palavra curta isolada |
| seo | SEO tecnico | match | sigla isolada |
| vba | Excel/VBA | match | sigla apos separador |

## Observabilidade local - SPB-203

Status: Implantado e validado em producao em 05/08/2026.

O matcher registra um resumo agregado por ciclo com a regra ativa (`lexical_boundaries_v1`), janela de lookback, usuarios com keywords, total de keywords, projetos analisados, projetos com match, pares encontrados, projecoes criadas, descartes por limite diario, duplicados/existentes e duracao em milissegundos.

O resumo nao inclui titulo de projeto, keyword, identificador de usuario, link, texto livre ou outro dado sensivel.

## Observabilidade futura

Registrar, sem dados sensiveis:

- distribuicao temporal dos ciclos;
- historico de contadores;
- alertas para quedas abruptas de volume;
- motivo agregado de descarte em casos ambiguos.

## Testes

Criar testes unitarios para:

- `normalize_text()`;
- `clean_keyword()`;
- `match_users_for_title()`;
- termos curtos;
- frases;
- pontuacao;
- hifen;
- barra;
- acentos;
- espacos multiplos;
- regressao `excel`/`excelente`.
