# Template de Prompt — Revisão de Código

Use este template para revisar código antes de fazer merge ou deploy, ou para avaliar uma sessão de implementação recente.

---

## Template de revisão geral

```
Faça uma revisão do código alterado nesta sessão do SmartPayBot.

Arquivos alterados:
- [listar arquivos]

Foco da revisão:
1. Corretude — o código faz o que deveria?
2. Segurança — há riscos de segurança introduzidos?
3. Governança — a mudança respeita AGENTS.md, regras locais e escopo aprovado?
4. Limites de plano — os limites Free/Pro estão sendo enforçados corretamente?
5. Compatibilidade — SQLite em dev ainda funciona?
6. Pipeline — ingestor/matcher/notifier foram afetados acidentalmente?
7. Sessões de banco — todos os `SessionLocal()` usam context manager?
8. Logs — eventos importantes estão sendo logados?
9. Overengineering — há abstrações desnecessárias?

Para cada problema encontrado:
- Indicar o arquivo e linha
- Descrever o problema
- Sugerir a correção
```

---

## Template de revisão de segurança

```
Revise os arquivos abaixo com foco exclusivo em segurança para o SmartPayBot:

Arquivos: [listar]

Checar obrigatoriamente:
1. Há segredos hardcoded (tokens, senhas, keys)?
2. Rotas novas têm @login_required e, se admin, @admin_required?
3. CSRF está ativado em formulários POST?
4. Há uso de | safe em templates com dados do usuário?
5. Parâmetros de URL são convertidos para tipo explícito?
6. Webhooks externos têm alguma validação (header, IP, assinatura)?
7. Queries SQL usam parâmetros (SQLAlchemy) — não string concatenation?
8. Logging não expõe dados sensíveis?

Retornar:
- Lista de problemas encontrados (crítico / alto / baixo)
- Sugestão de correção para cada um
```

---

## Template de revisão pré-deploy

```
Revisão pré-deploy do SmartPayBot.

Branch: [nome da branch]
Alterações desde o último deploy: [resumo ou `git log --oneline main..HEAD`]

Fonte canônica para deploy real:
docs/runbooks/deploy-producao.md

Verificar:
1. HEAD/base/target foram confirmados pelo orquestrador.
2. `.env` e outros segredos não aparecem no git, no diff ou nos logs.
3. Variáveis obrigatórias foram reportadas apenas como presentes/ausentes, sem valores.
4. Ambiente seguro foi reportado sem imprimir valores de secrets.
5. Testes/gates proporcionais ao risco foram executados.
6. Banco foi validado quando aplicável.
7. Migrações ou scripts de banco foram executados somente quando a mudança exigir, com evidência segura.
8. Smoke HTTP foi executado quando aplicável.
9. Webhook/Telegram foi validado por gate seguro quando aplicável.
10. Collector foi restaurado quando aplicável.
11. Nenhuma inspeção ou impressão de valores secretos foi solicitada.
12. Nenhum print() ou debug ativo foi introduzido no código.

Retornar:
- ✅ Pronto / ⚠ Atenção / ❌ Bloqueante para cada item
- Lista de ações necessárias antes do deploy
```

---

## Perguntas de revisão rápida

Para revisões informais durante o desenvolvimento, responder estas perguntas:

1. **O código está testável?** Consigo rodar um smoke test simples?
2. **Um novo dev entenderia em 2 minutos o que esse código faz?**
3. **Se esse código quebrar em produção, o pipeline de alertas para?**
4. **Algum usuário poderia acessar dados de outro usuário com esse código?**
5. **O que acontece se o banco estiver indisponível quando esse código rodar?**
