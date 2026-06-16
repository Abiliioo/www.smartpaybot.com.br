# SmartPayBot — Padrão de Mensagens de Commit

## Formato

```
<tipo>(<escopo>): <descrição curta em imperativo>

[corpo opcional — explica o POR QUÊ, não o O QUÊ]

[rodapé opcional — breaking changes, refs de issues]
```

---

## Tipos

| Tipo | Quando usar |
|---|---|
| `feat` | Nova funcionalidade para o usuário ou operador |
| `fix` | Correção de bug |
| `chore` | Manutenção sem impacto funcional (seed, scripts, dependências) |
| `docs` | Apenas documentação |
| `refactor` | Refatoração sem mudança de comportamento |
| `style` | CSS, templates, UI (sem lógica) |
| `test` | Adição ou correção de testes |
| `security` | Correção de vulnerabilidade ou hardening |

---

## Escopos comuns

| Escopo | Módulo/área |
|---|---|
| `plans` | Sistema de planos e subscriptions |
| `billing` | Pagamentos, Stripe |
| `admin` | Painel administrativo |
| `auth` | Login, registro, sessão |
| `dashboard` | Rotas e templates do dashboard |
| `notifier` | Worker de notificação |
| `matcher` | Worker de matching de keywords |
| `ingestor` | Worker de scraping |
| `scheduler` | Agendamento do pipeline |
| `models` | Schema do banco de dados |
| `telegram` | Integração com Telegram |
| `config` | Configurações e variáveis de ambiente |
| `deps` | Dependências (requirements.txt) |

---

## Exemplos

```
feat(plans): adicionar modelos Plan, Subscription e UserAlertDaily

Introduz infraestrutura de planos SaaS com dois planos iniciais:
Free (3 keywords, 10 alertas/dia) e Pro (ilimitado).
A verificação de limites é feita em plan_service.py de forma
centralizada para evitar duplicação.
```

```
feat(admin): implementar painel de gestão de planos em /admin/

Permite ao admin alterar o plano de qualquer usuário manualmente,
viabilizando o modelo de beta pago sem Stripe.
```

```
fix(notifier): respeitar limite diário de alertas do plano Free

Usuários Free com mais de 10 alertas no dia tinham notificações
enviadas além do limite. O check agora ocorre antes de cada envio
e notificações excedentes ficam pendentes para o dia seguinte.
```

```
docs: criar estrutura de documentação e regras do projeto

Adiciona CLAUDE.md, docs/, rules/ e prompts/ para padronizar
o desenvolvimento e o uso do Claude Code neste projeto.
```

```
chore(plans): seed inicial dos planos Free e Pro no banco
```

```
security: nunca logar conteúdo de TELEGRAM_TOKEN em config.py
```

---

## Regras

1. **Imperativo no presente:** "adicionar" não "adicionei" ou "adicionando".
2. **Linha de assunto ≤ 72 caracteres.**
3. **Corpo em PT-BR**, explica motivação e impacto — não o que o diff já mostra.
4. **Nunca incluir** senhas, tokens ou dados pessoais na mensagem.
5. **Um commit por responsabilidade** — não agrupar features não relacionadas.
6. **Breaking changes** no rodapé: `BREAKING CHANGE: descrição`.

---

## Commits típicos por fase de desenvolvimento

### Fase de features SaaS
```
feat(plans): <nova feature de plano>
feat(billing): <integração de pagamento>
feat(admin): <melhoria no painel admin>
```

### Fase de correção/hardening
```
fix(<escopo>): <descrição do bug corrigido>
security: <melhoria de segurança>
```

### Fase de documentação
```
docs: <o que foi documentado>
```

### Manutenção operacional
```
chore(deps): atualizar flask para 3.1.x
chore(db): seed de planos no ambiente de staging
```
