# Sprint 0 kickoff

## Objetivo

Preparar a base tecnica e documental para iniciar a Fase 2 com seguranca, sem alterar producao e sem implementar funcionalidades prematuramente.

## Duracao sugerida

3 a 5 dias de trabalho focado.

## Checklist

- [ ] Confirmar branch de trabalho.
- [ ] Rodar suite atual.
- [ ] Criar testes do matcher para bug `excel`/`excelente`.
- [ ] Mapear tabelas e lacunas de schema.
- [ ] Definir estrategia de migracoes.
- [ ] Definir regras de termos curtos.
- [ ] Definir modelo minimo de auditoria Admin.
- [ ] Escolher abordagem da central de alertas.
- [ ] Definir provedor de email ou manter pendente explicitamente.
- [ ] Criar inventario visual das telas atuais.
- [ ] Definir feature flags para entregas maiores.
- [ ] Validar plano de rollout e rollback.

## Arquivos a auditar

- `domain/services/projects_service.py`;
- `domain/services/keywords_service.py`;
- `domain/models.py`;
- `domain/repositories.py`;
- `workers/notifier.py`;
- `app/routes/admin.py`;
- `app/routes/auth.py`;
- `app/routes/dashboard.py`;
- `app/routes/ingest.py`;
- `app/templates/admin.html`;
- `app/templates/dashboard.html`;
- `app/static/css/style.css`;
- `app/static/js/script.js`;
- `tests/test_notifier_queue.py`;
- `.env.example`;
- `docs/decisoes-tecnicas.md`;
- `docs/regras-negocio.md`.

## Comandos

```powershell
git status --short --branch
git log -5 --oneline --decorate
python -m unittest discover -v
python -m unittest tests.test_notifier_queue -v
git diff --check
```

## Entregaveis

- matriz lexical aprovada;
- baseline de testes;
- proposta de schema para alertas e canais;
- proposta de auditoria Admin;
- decisao sobre migracoes;
- backlog Sprint 1 pronto.

## Criterios de saida

- `SPB-201` pronto para implementacao;
- testes de matcher especificados;
- riscos de dados conhecidos;
- rollback definido para primeira mudanca;
- nenhuma dependencia nova adicionada sem necessidade.

## Riscos

- tentar redesenhar UI antes de corrigir qualidade do alerta;
- adicionar canais antes de separar alerta de entrega;
- criar migracao sem rollback testado;
- acoplar Admin a regras ainda indefinidas.

## Primeiro item tecnico recomendado

`SPB-201 - Corrigir correspondencia parcial de palavras-chave`.

Motivo:

- bug confirmado;
- escopo pequeno;
- alto impacto;
- facil teste;
- baixa dependencia;
- reduz alertas incorretos antes de ampliar canais.
