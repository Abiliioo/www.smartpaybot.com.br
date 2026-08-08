# Changelog

Todas as mudancas relevantes do SmartPayBot serao registradas neste arquivo.

Formato inspirado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). O produto ainda esta em beta e nao possui versionamento semantico formal, entao as mudancas permanecem em `[Unreleased]` ate que uma politica de releases seja definida.

## [Unreleased]

### Added

- Listagem administrativa com busca por username/email, filtros combinaveis (plano, monitoramento, Telegram vinculado) e paginacao (SPB-210).
- Observabilidade agregada do matcher, com contadores de projetos analisados, casamentos e criacoes, sem expor titulos, keywords ou dados de usuario nos logs (SPB-203).

### Changed

- Runner local do coletor (`run_collector.bat`) passou a registrar inicio e fim de cada ciclo com timestamp e `EXIT_CODE`, com saida do Python forcada em UTF-8.

### Fixed

- Correspondencia lexical do matcher deixou de casar termos curtos dentro de palavras maiores (ex.: `excel` casando indevidamente com `excelente`), com cobertura de testes automatizados dedicada (SPB-201, SPB-202).
- Listagem administrativa deixou de expor `password_hash`, telefone, `chat_id` e codigos de vinculacao Telegram na projecao retornada ao template (hardening de privacidade do SPB-210).
- Filtros administrativos de plano (Free, Pro, Admin) passaram a ser mutuamente exclusivos: administradores deixaram de aparecer no filtro Free (e no Pro, quando aplicavel), independentemente de possuirem assinatura ativa (SPB-210).

### Security

- Introduzida a variavel `APP_ENV` (`development`/`homologation`/`production`), com resolucao fail-closed: valor invalido ou `FLASK_ENV=production` sem `APP_ENV` explicito recusam o boot da aplicacao (SPB-263).
- `infrastructure/db.py` passou a validar `DATABASE_URL` antes de criar a conexao (`create_engine`): em `APP_ENV=homologation`, exige URL SQLite explicita apontando para um arquivo `homolog.db`, rejeitando o fallback padrao, `:memory:` e qualquer banco fora dessa convencao (SPB-263).
- O guardrail de `SECRET_KEY` (antes restrito a `FLASK_ENV=production`) passou a cobrir tambem `APP_ENV=homologation` (SPB-263).
- `workers/scheduler.py` passou a recusar iniciar o scheduler de scraping real (`start()`, e por extensao `start_scheduler()` e o toggle de monitoramento do dashboard) quando `APP_ENV=homologation`, e a pular a etapa de crawling dentro do ciclo do pipeline nesse ambiente, sem bloquear matcher/notifier (SPB-263).
