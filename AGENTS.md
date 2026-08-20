# SmartPayBot - Governanca de agentes

Este repositorio adota o Abilio Dev OS como referencia de governanca, de forma leve e local.

Referencia externa:

- Abilio Dev OS: `Abiliioo/Dev-OS`
- Versao adotada: `v0.1.1-dev`
- Pin de referencia: `31943dd76fe76cabc4a10de21e604b11f32c80c7`
- Issue de adocao: GitHub Issue `#1`

## Regra de precedencia

1. Segurança, integridade, requisitos legais/obrigatórios e proteção de dados/secrets.
2. Instruções explícitas do proprietário para a tarefa atual, desde que não contrariem o item 1.
3. Regras específicas e mais restritivas do SmartPayBot.
4. Abilio Dev OS `v0.1.1-dev` no pin adotado.
5. Padrões gerais do agente ou ferramenta em uso.

Quando houver conflito, a regra mais restritiva de segurança/operação do SmartPayBot vence.

## Idioma

Responda, relate progresso e produza documentacao em portugues do Brasil. Nomes tecnicos, comandos, caminhos, hashes, slugs, branches e mensagens de commit podem permanecer em ingles quando isso preservar clareza.

## Principios do SmartPayBot

- Prioridade absoluta: gerar receita ou manter o que ja vende.
- Manter o delta pequeno e proporcional ao risco.
- Nao alterar codigo funcional fora do escopo aprovado.
- Nao mover ou renomear arquivos sem necessidade tecnica clara.
- Nao introduzir dependencia, ferramenta, automacao ou sincronizacao nova sem aprovacao explicita.
- Preservar o pipeline critico: `scheduler -> crawl_once() -> match_recent_projects() -> notify_pending()`.

## Papel preferencial dos agentes

- ChatGPT: direcao de produto, decisao de escopo, review e aceite.
- Claude: auditoria, arquitetura, analise de risco e revisao.
- Codex: implementacao local, Git, testes e validacao tecnica.

Esses papeis sao preferenciais, nao exclusivos. A tarefa atual e as instruções explícitas do proprietário continuam sendo a fonte de verdade, desde que nao contrariem seguranca, integridade, requisitos legais/obrigatorios e protecao de dados/secrets.

## Fluxo de trabalho

1. Confirmar branch, baseline e escopo antes de editar.
2. Trabalhar em branch curta baseada em `main` atualizada.
3. Fazer alteracoes pequenas, diretamente ligadas a uma issue ou objetivo claro.
4. Executar quality gates proporcionais ao risco.
5. Registrar no resultado final: arquivos alterados, validacoes feitas, commit sugerido ou criado e proximos passos.

## Quality gates

Escolha os gates de acordo com o risco da mudanca:

- Documentacao/governanca: `git diff --check`, revisao de escopo e verificacao de arquivos esperados.
- Codigo de baixo risco: smoke test ou teste unitario diretamente relacionado.
- Mudanca em seguranca, autenticacao, pagamentos, deploy, banco ou pipeline: testes focados + suite relevante + plano de rollback.

Nao fazer deploy, SSH, escrita em Scheduled Task, push ou PR sem pedido explicito.

## Estado operacional atual

- Banco atual de desenvolvimento e producao: SQLite.
- PostgreSQL e uma evolucao futura/proposta, nao o estado operacional atual.
- Pagamentos automatizados ainda nao estao implementados.
- SPB-264 e SPB-270 permanecem congelados ate a conclusao desta adocao de governanca.

## Arquivos locais relacionados

- `CLAUDE.md`: contexto operacional e regras especificas para Claude.
- `rules/`: regras de desenvolvimento e seguranca.
- `prompts/`: templates curtos para iniciar implementacao, revisao e commits.
- `CHANGELOG.md`: registro de mudancas relevantes.
