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

- `scripts/deploy-production.ps1` (automacao local de deploy, SPB-263): o primeiro deploy real de producao terminou com `DEPLOY_STATUS=SUCCESS` remoto (banco integro, servico active, HTTP 200, Collector com `LastTaskResult=0` apos retomar o ciclo normal), mas o script local reportou falsamente "Deploy foi REVERTIDO automaticamente" (`exit 2`), sem rollback real ter ocorrido. Causa raiz reproduzida isoladamente (sem SSH/VPS): o Windows PowerShell 5.1 injeta um BOM UTF-8 no inicio e um `\r\n` extra no fim de qualquer string enviada via pipeline (`$texto | & processo`) a um processo nativo com stdin redirecionado, fazendo a ultima linha do script remoto (`exit 0`) chegar ao bash como `exit 0\r` -- rejeitado com `numeric argument required` e `exit 2`. Corrigido convertendo o script para Base64 antes do envio e decodificando no lado remoto com `base64 --decode --ignore-garbage` (que descarta os bytes espurios do transporte), preservando os bytes originais byte-a-byte (validado por comparacao de SHA-256 do script original contra o reconstruido, sem executa-lo).
- `scripts/deploy-production.ps1` (automacao local de deploy, SPB-263) passou a exigir PowerShell elevado ("Executar como Administrador") antes de pausar o Scheduled Task `SmartPayBot Collector`, e a rastrear explicitamente se a task foi de fato desabilitada pelo proprio deploy: `Disable-ScheduledTask` sem sucesso (ex.: "Acesso negado" por falta de elevacao) agora aborta com `exit 1` antes de qualquer conexao SSH, sem tentar `Enable-ScheduledTask` sobre uma task que nunca foi confirmadamente pausada. Corrige um incidente real em que a falta de elevacao causava "Acesso negado" tanto ao pausar quanto ao tentar religar o Collector no `finally`, sem impedir a tentativa de deploy remoto.
- Correspondencia lexical do matcher deixou de casar termos curtos dentro de palavras maiores (ex.: `excel` casando indevidamente com `excelente`), com cobertura de testes automatizados dedicada (SPB-201, SPB-202).
- Listagem administrativa deixou de expor `password_hash`, telefone, `chat_id` e codigos de vinculacao Telegram na projecao retornada ao template (hardening de privacidade do SPB-210).
- Filtros administrativos de plano (Free, Pro, Admin) passaram a ser mutuamente exclusivos: administradores deixaram de aparecer no filtro Free (e no Pro, quando aplicavel), independentemente de possuirem assinatura ativa (SPB-210).

### Security

- Introduzida a variavel `APP_ENV` (`development`/`homologation`/`production`), com resolucao fail-closed: valor invalido ou `FLASK_ENV=production` sem `APP_ENV` explicito recusam o boot da aplicacao (SPB-263).
- `infrastructure/db.py` passou a validar `DATABASE_URL` antes de criar a conexao (`create_engine`): em `APP_ENV=homologation`, exige URL SQLite explicita apontando para um arquivo `homolog.db`, rejeitando o fallback padrao, `:memory:` e qualquer banco fora dessa convencao (SPB-263).
- O guardrail de `SECRET_KEY` (antes restrito a `FLASK_ENV=production`) passou a cobrir tambem `APP_ENV=homologation` (SPB-263).
- `workers/scheduler.py` passou a recusar iniciar o scheduler de scraping real (`start()`, e por extensao `start_scheduler()` e o toggle de monitoramento do dashboard) quando `APP_ENV=homologation`, e a pular a etapa de crawling dentro do ciclo do pipeline nesse ambiente, sem bloquear matcher/notifier (SPB-263).
- Introduzida a variavel `TELEGRAM_MODE` (`disabled`/`homologation`/`production`), com resolucao fail-closed: `development` aceita `disabled`/`homologation` (ausente vira `disabled`) e rejeita `production`; `homologation` e `production` exigem o proprio valor explicito, sem fallback entre si (SPB-263).
- Introduzida a variavel `TELEGRAM_EXPECTED_BOT_ID` (nao e secret). `infrastructure/telegram.py` passou a centralizar toda chamada de rede Telegram (`send_message`, `get_webhook_info`, `set_webhook`, `delete_webhook`, `get_updates`) atras de um identity guard: antes da primeira operacao real, valida via `getMe` que o bot corresponde ao ID esperado, de forma lazy e cacheada por processo (sucesso e cacheado; falha nunca e). Bloqueio de identidade impede a operacao real sem derrubar a aplicacao (SPB-263).
- `app/routes/webhook_telegram.py` passou a usar `APP_ENV`/`TELEGRAM_MODE` (em vez de `FLASK_ENV`) como fonte de verdade: `TELEGRAM_MODE=disabled` recusa o webhook (503) antes de processar qualquer payload; quando ativo, `TELEGRAM_WEBHOOK_SECRET` e sempre obrigatorio (nunca mais aceita requisicao sem autenticacao); o identity guard roda apos o secret e antes de qualquer gravacao no banco (SPB-263).
- `workers/notifier.py` passou a verificar a prontidao do Telegram (`TELEGRAM_MODE` + identity guard) antes do loop de envio: se bloqueado, nenhuma mensagem e enviada e nenhuma tentativa/limite diario e consumido nesta rodada — distinto de uma falha real de entrega, que continua incrementando tentativas normalmente (SPB-263).
- `scripts/telegram_poll.py` (uso local/dev) deixou de exibir qualquer fragmento do token e passou a respeitar `TELEGRAM_MODE`/identity guard antes de iniciar o polling (SPB-263).
- Isolamento de Telegram (`TELEGRAM_MODE` + identity guard, itens acima) implantado e validado em producao em 09/08/2026, commits `0c41b25` (guardrails), `18ac2b1` (hardening de `set_webhook`, sempre envia `TELEGRAM_WEBHOOK_SECRET` configurado e bloqueia registro sem secret) e `fc3b91c` (isolamento dos testes do proprio helper de ambiente controlado em relacao ao `.env` real do processo) (SPB-263).
- SPB-263 B4 (isolamento visual e de sessao entre `development`/`homologation`/`production`) implementado e testado localmente, **ainda nao implantado em producao**: `SESSION_COOKIE_NAME` passou a ser derivado deterministicamente de `APP_ENV` (`infrastructure/config.py`, funcao `session_cookie_name_for_app_env`) — nunca configuravel via variavel de ambiente, produzindo `"session"` em `production`/`development` (cookie legado preservado) e `"smartpaybot_homolog_session"` em `homologation`; `SESSION_COOKIE_SECURE` passou a depender de `APP_ENV` (antes dependia de `FLASK_ENV`); `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_DOMAIN` e `SESSION_COOKIE_PATH` passaram a ser configurados explicitamente em todos os ambientes. Quando `APP_ENV=homologation`, a interface exibe um banner global "HOMOLOGACAO — AMBIENTE DE TESTES" no header, uma classe `env-homologation` no `<body>` e um prefixo `[HOMOLOGACAO]` no `<title>` — todos condicionados exclusivamente a `APP_ENV`, nunca a hostname/porta (SPB-263).
