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
