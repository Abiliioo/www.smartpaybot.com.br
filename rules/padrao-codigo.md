# SmartPayBot — Padrão de Código

## Princípios

1. **Mudanças pequenas e focadas.** Uma sessão de desenvolvimento = uma responsabilidade.
2. **Código claro sobre código inteligente.** Um nome bom vale mais que um comentário.
3. **Preservar SQLite em dev.** Não exigir infraestrutura adicional para rodar localmente.
4. **Sem comentários óbvios.** Comentar apenas o *por quê* não-óbvio, nunca o *o quê*.

---

## Estrutura de arquivos

### Novos modelos → `domain/models.py`
Sempre ao final do arquivo. Seguir o padrão SQLAlchemy 2.x com `Mapped[T]`:

```python
class NomeModelo(Base):
    __tablename__ = "nome_tabela"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campo: Mapped[str] = mapped_column(String(100), nullable=False)
    campo_opcional: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

### Novas queries → `domain/repositories.py`
Apenas SQL. Sem regras de negócio. Sem chamadas a serviços externos.

```python
def get_coisa_por_id(db: Session, coisa_id: int) -> Optional[Coisa]:
    return db.execute(select(Coisa).where(Coisa.id == coisa_id)).scalar_one_or_none()
```

### Nova lógica de negócio → `domain/services/`
Sem SQL direto. Usa repositórios. Sem referências a Flask/request.

```python
# domain/services/exemplo_service.py
from ..repositories import get_coisa_por_id

def pode_fazer_algo(db: Session, user_id: int) -> bool:
    ...
```

### Novas rotas → `app/routes/<contexto>.py`
Sem SQL direto. Usa serviços do domain. Sempre importar DB via `SessionLocal()`.

```python
@bp.get("/rota")
@login_required
def minha_rota():
    with SessionLocal() as db:
        resultado = algum_servico(db, int(current_user.id))
    return jsonify({"ok": True, "data": resultado})
```

---

## Sessões de banco

Sempre usar context manager:

```python
# ✅ Correto
with SessionLocal() as db:
    user = db.get(User, user_id)

# ❌ Evitar
db = SessionLocal()
user = db.get(User, user_id)
db.close()
```

---

## Tratamento de erros

- Rotas devem capturar exceções previsíveis e retornar resposta adequada.
- Não usar `except Exception` em rotas sem logar antes.
- Workers devem ser resilientes: um erro em um item não deve derrubar o ciclo inteiro.

```python
try:
    resultado = operacao_riscosa()
except ValueError as e:
    flash(str(e), "danger")
    return redirect(url_for("dashboard.home"))
except Exception as e:
    log.exception("[contexto] falha inesperada: %s", e)
    flash("Erro interno. Tente novamente.", "danger")
    return redirect(url_for("dashboard.home"))
```

---

## Logging

Sempre usar `get_logger(__name__)`, nunca `print()` em produção:

```python
from infrastructure.logging import get_logger
log = get_logger(__name__)

log.info("[contexto] mensagem descritiva: campo=%s", valor)
log.warning("[contexto] situação inesperada mas não crítica: %s", detalhe)
log.error("[contexto] falha tratável: %s", erro)
log.exception("[contexto] exceção não esperada: %s", erro)  # inclui traceback
```

---

## Configuração

Nunca ler variáveis de ambiente diretamente fora de `infrastructure/config.py`:

```python
# ✅ Correto
from infrastructure.config import get_settings
settings = get_settings()
valor = settings.MINHA_VAR

# ❌ Evitar
import os
valor = os.getenv("MINHA_VAR")
```

Novas configurações: adicionar ao `Settings` dataclass em `infrastructure/config.py`.

---

## Templates Jinja2

- Não colocar lógica complexa em templates. Pré-calcular no Python.
- Usar os CSS tokens existentes (`var(--brand)`, `var(--success)`, etc.) — não hardcodar cores.
- Botões de formulário sempre com `csrf_token()` no campo hidden ou via `form.hidden_tag()`.

---

## Compatibilidade local

Qualquer funcionalidade nova deve funcionar com:
```
DATABASE_URL=sqlite:///app.db
SCHEDULER=0
```
Não exigir Redis, PostgreSQL ou Celery para rodar localmente. Esses são opcionais em dev.

---

## Comandos de teste mínimos

Após qualquer mudança, verificar:

```powershell
# 1. App sobe sem erro
.venv\Scripts\python.exe -c "from app import create_app; create_app(); print('OK')"

# 2. Seed roda sem erro (se modelos novos)
.venv\Scripts\python.exe scripts/seed_plans.py

# 3. Importações do módulo alterado não quebram
.venv\Scripts\python.exe -c "from workers.notifier import notify_pending; print('OK')"
```

Para testes de rotas específicas, usar `app.test_client()`.

---

## Convenções de nome

| Tipo | Padrão | Exemplo |
|---|---|---|
| Função de repository | `get_X`, `list_X`, `create_X`, `delete_X` | `get_user_by_id` |
| Função de service | verbo + contexto | `can_add_keyword`, `set_user_plan` |
| Blueprint | `bp` | `bp = Blueprint(...)` |
| Rota GET simples | substantivo | `/dashboard/`, `/admin/` |
| Rota POST de ação | verbo no infinitivo | `/dashboard/keywords/delete` |
| Variável de ambiente | `UPPER_SNAKE_CASE` | `TELEGRAM_TOKEN` |
| Slugs de plano | `lower_snake_case` | `"free"`, `"pro"` |
