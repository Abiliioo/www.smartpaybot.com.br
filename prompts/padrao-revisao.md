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
3. Limites de plano — os limites Free/Pro estão sendo enforçados corretamente?
4. Compatibilidade — SQLite em dev ainda funciona?
5. Pipeline — ingestor/matcher/notifier foram afetados acidentalmente?
6. Sessões de banco — todos os `SessionLocal()` usam context manager?
7. Logs — eventos importantes estão sendo logados?
8. Overengineering — há abstrações desnecessárias?

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

Verificar:
1. .env não está no git (`git status` mostra .env?)
2. SECRET_KEY está configurada (não é o valor default)
3. DATABASE_URL aponta para PostgreSQL (não SQLite)
4. SCHEDULER=0 ou confirmado que APScheduler funciona com 1 worker
5. Alembic migrations foram aplicadas (`alembic upgrade head`)
6. seed_plans.py foi rodado no banco de prod
7. TELEGRAM_TOKEN é o token de produção correto
8. Nenhum print() ou debug ativo no código

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
