#!/usr/bin/env bash
# scripts/deploy-production-remote.sh
#
# Script remoto de deploy controlado do SmartPayBot em producao.
# Executado NA VPS, tipicamente invocado pelo orquestrador local
# scripts/deploy-production.ps1 via:
#
#   Get-Content scripts/deploy-production-remote.sh | ssh $DeployHost "bash -s -- $TargetSha $AppDir"
#
# Pode tambem ser copiado e executado manualmente na VPS para depuracao,
# ou futuramente reutilizado por um workflow de GitHub Actions (ver
# docs/runbooks/deploy-producao.md, secao "Futura automacao CI/CD").
#
# Recebe exatamente:
#   $1 = TARGET_SHA   (obrigatorio -- SHA git completo de 40 caracteres hex)
#   $2 = APP_DIR       (opcional -- default: /home/deploy/apps/www.smartpaybot.com.br)
#
# Contrato:
#   - fail-fast / fail-closed: qualquer gate pre-restart que falhar aborta
#     SEM tocar no servico em execucao (codigo antigo continua rodando).
#   - somente fast-forward: nunca merge, nunca reset --hard alem do
#     rollback explicito para PRE_DEPLOY_HEAD (que so anda para TRAS, na
#     mesma linha de historico local, e NUNCA altera origin/main).
#   - nunca imprime valor de secret.
#   - emite, ao final, linhas maquina-legiveis fixas (ver EMIT_RESULT).
#
# Codigos de saida:
#   0 = DEPLOY_STATUS=SUCCESS
#   1 = DEPLOY_STATUS=FAILED    (abortado ANTES do restart -- servico antigo intacto)
#   2 = DEPLOY_STATUS=ROLLED_BACK (falhou DEPOIS do restart -- codigo revertido e religado)

set -uo pipefail

# ── argumentos ──────────────────────────────────────────────────────────
TARGET_SHA="${1:-}"
APP_DIR="${2:-/home/deploy/apps/www.smartpaybot.com.br}"

PRE_DEPLOY_HEAD=""
PRODUCTION_HEAD=""
DATABASE_INTEGRITY="NOT_OK"
SESSION_COOKIE_NAME="unknown"
HOMOLOGATION_BANNER_PRESENT="YES"
RESTARTED="no"

emit_result() {
    local status="$1"
    echo "DEPLOY_STATUS=${status}"
    echo "PRE_DEPLOY_HEAD=${PRE_DEPLOY_HEAD}"
    echo "PRODUCTION_HEAD=${PRODUCTION_HEAD}"
    echo "TARGET_SHA=${TARGET_SHA}"
    echo "DATABASE_INTEGRITY=${DATABASE_INTEGRITY}"
    echo "SESSION_COOKIE_NAME=${SESSION_COOKIE_NAME}"
    echo "HOMOLOGATION_BANNER_PRESENT=${HOMOLOGATION_BANNER_PRESENT}"
}

abort() {
    # Usado ANTES do restart -- servico antigo nunca foi tocado.
    echo "ABORT: $1" >&2
    PRODUCTION_HEAD="${PRE_DEPLOY_HEAD}"
    emit_result "FAILED"
    exit 1
}

rollback_and_exit() {
    # Usado DEPOIS do restart -- reverte o codigo e religa o servico antigo.
    local reason="$1"
    echo "ROLLBACK: $reason" >&2
    if [ -n "$PRE_DEPLOY_HEAD" ]; then
        git reset --hard "$PRE_DEPLOY_HEAD" >&2
        sudo systemctl restart smartpaybot >&2
        sleep 3
        sudo systemctl is-active smartpaybot >&2 || echo "AVISO: servico nao voltou a active apos rollback" >&2
        curl -sS -o /dev/null -w "smoke pos-rollback HOME: %{http_code}\n" https://smartpaybot.com.br/ >&2 || true
    fi
    PRODUCTION_HEAD="$(git rev-parse HEAD 2>/dev/null || echo "$PRE_DEPLOY_HEAD")"
    emit_result "ROLLED_BACK"
    exit 2
}

# ── 1. validar TARGET_SHA e APP_DIR ──────────────────────────────────────
if [[ ! "$TARGET_SHA" =~ ^[0-9a-f]{40}$ ]]; then
    abort "TARGET_SHA ausente ou invalido (esperado SHA git completo de 40 hex chars)."
fi
if [[ ! "$APP_DIR" =~ ^[A-Za-z0-9_./-]+$ ]]; then
    abort "APP_DIR contem caracteres nao permitidos."
fi
if [ ! -d "$APP_DIR" ]; then
    abort "APP_DIR nao encontrado: $APP_DIR"
fi
cd "$APP_DIR" || abort "nao foi possivel entrar em $APP_DIR"

echo "=== 1. PREFLIGHT REMOTO ==="
echo "APP_DIR=$(pwd)"
echo "TARGET_SHA=$TARGET_SHA"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || abort "diretorio nao e um repositorio git."

CURRENT_BRANCH="$(git branch --show-current)"
if [ "$CURRENT_BRANCH" != "main" ]; then
    abort "branch atual da VPS nao e 'main' (encontrado: '$CURRENT_BRANCH')."
fi

PRE_DEPLOY_HEAD="$(git rev-parse HEAD)"
echo "PRE_DEPLOY_HEAD=$PRE_DEPLOY_HEAD"

git fetch origin || abort "git fetch origin falhou."
ORIGIN_MAIN="$(git rev-parse origin/main)"
echo "origin/main=$ORIGIN_MAIN"

if [ "$TARGET_SHA" != "$ORIGIN_MAIN" ]; then
    abort "TARGET_SHA ($TARGET_SHA) difere de origin/main ($ORIGIN_MAIN) -- deploy padrao exige TARGET_SHA == origin/main."
fi

if ! git cat-file -e "${TARGET_SHA}^{commit}" 2>/dev/null; then
    abort "TARGET_SHA nao existe como commit no repositorio local apos fetch."
fi

if ! git merge-base --is-ancestor "$PRE_DEPLOY_HEAD" "$TARGET_SHA"; then
    abort "PRE_DEPLOY_HEAD nao e ancestral de TARGET_SHA -- fast-forward nao e seguro (historico divergente)."
fi

# ── 2. worktree tracked limpo ────────────────────────────────────────────
TRACKED_DIRTY="$(git status --short | grep -vE '^\?\? backups/' || true)"
if [ -n "$TRACKED_DIRTY" ]; then
    echo "$TRACKED_DIRTY" >&2
    abort "ha modificacao tracked inesperada no worktree de producao."
fi

echo
echo "=== 2. ESTADO DE PRODUCAO ANTES DO DEPLOY ==="
sudo systemctl is-active smartpaybot || abort "servico smartpaybot nao esta active antes do deploy."
ss -ltnp | grep ':8000' || echo "AVISO: nada escutando em :8000 no preflight."
curl -sS -o /dev/null -w "HOME pre-deploy: %{http_code}\n" https://smartpaybot.com.br/

echo
echo "=== 3. CONFIGURACAO SEGURA (sem segredos) ==="
CONFIG_CHECK_OUT="$(.venv/bin/python -c "
from infrastructure.config import get_settings
s = get_settings()
print('APP_ENV=' + s.APP_ENV)
print('FLASK_ENV=' + s.FLASK_ENV)
print('TELEGRAM_MODE=' + s.TELEGRAM_MODE)
print('SCHEDULER_ENABLED=' + str(s.SCHEDULER_ENABLED))
print('TELEGRAM_TOKEN_SET=' + str(bool(s.TELEGRAM_TOKEN)))
print('TELEGRAM_WEBHOOK_SECRET_SET=' + str(bool(s.TELEGRAM_WEBHOOK_SECRET)))
print('INTERNAL_INGEST_TOKEN_SET=' + str(bool(s.INTERNAL_INGEST_TOKEN)))
print('SECRET_KEY_SET=' + str(bool(s.SECRET_KEY)))
")"
echo "$CONFIG_CHECK_OUT"
if ! echo "$CONFIG_CHECK_OUT" | grep -q '^APP_ENV=production$'; then
    abort "APP_ENV != production."
fi
if ! echo "$CONFIG_CHECK_OUT" | grep -q '^FLASK_ENV=production$'; then
    abort "FLASK_ENV != production."
fi

echo
echo "=== 4. CHECKPOINT DO BANCO (PRE) ==="
DB_HASH_PRE="$(sha256sum app.db | awk '{print $1}')"
echo "DB_HASH_PRE=$DB_HASH_PRE"
INTEGRITY_PRE="$(sqlite3 app.db "PRAGMA integrity_check;")"
echo "integrity_check pre=$INTEGRITY_PRE"
if [ "$INTEGRITY_PRE" != "ok" ]; then
    abort "PRAGMA integrity_check pre-deploy != ok."
fi
FK_PRE="$(sqlite3 app.db "PRAGMA foreign_key_check;")"
if [ -n "$FK_PRE" ]; then
    abort "PRAGMA foreign_key_check pre-deploy encontrou inconsistencias."
fi

mkdir -p backups
chmod 700 backups
BACKUP_NAME="backups/app.db.pre-deploy-$(date +%Y%m%d-%H%M%S).bak"
cp -a app.db "$BACKUP_NAME"
chmod 600 "$BACKUP_NAME"
echo "backup criado: $BACKUP_NAME ($(stat -c%s "$BACKUP_NAME") bytes)"

echo
echo "=== 5. UPDATE (fast-forward) ==="
git merge --ff-only "$TARGET_SHA" || abort "fast-forward para TARGET_SHA falhou."
NEW_HEAD="$(git rev-parse HEAD)"
if [ "$NEW_HEAD" != "$TARGET_SHA" ]; then
    abort "HEAD pos-merge ($NEW_HEAD) diferente de TARGET_SHA ($TARGET_SHA)."
fi
echo "HEAD atualizado para $NEW_HEAD"

echo
echo "=== 6. TEST GATE ==="
.venv/bin/python -m unittest discover -v 2>&1 | tail -8
TEST_RC=${PIPESTATUS[0]}
.venv/bin/python -m py_compile infrastructure/config.py app/__init__.py
COMPILE_RC=$?
if [ "$TEST_RC" -ne 0 ] || [ "$COMPILE_RC" -ne 0 ]; then
    echo "Testes ou py_compile falharam -- revertendo codigo para PRE_DEPLOY_HEAD (servico AINDA NAO reiniciado)." >&2
    git reset --hard "$PRE_DEPLOY_HEAD"
    abort "test gate falhou pos-update; codigo revertido para PRE_DEPLOY_HEAD, servico antigo nunca foi tocado."
fi

echo
echo "=== 7. RESTART ==="
RESTART_TS="$(date --iso-8601=seconds)"
echo "RESTART_TS=$RESTART_TS"
sudo systemctl restart smartpaybot
RESTARTED="yes"
sleep 3
if ! sudo systemctl is-active --quiet smartpaybot; then
    rollback_and_exit "servico nao ficou active apos restart."
fi
if ss -ltnp | grep -q '0\.0\.0\.0:8000'; then
    rollback_and_exit "servico bindado em 0.0.0.0:8000 (exposto publicamente) apos restart."
fi
if ! ss -ltnp | grep -q '127\.0\.0\.1:8000'; then
    rollback_and_exit "servico nao esta escutando em 127.0.0.1:8000 apos restart."
fi

echo
echo "=== 8. SMOKE HTTP ==="
HOME_CODE="$(curl -sS -o /dev/null -w '%{http_code}' https://smartpaybot.com.br/)"
LOGIN_CODE="$(curl -sS -o /dev/null -w '%{http_code}' https://smartpaybot.com.br/auth/login)"
REGISTER_CODE="$(curl -sS -o /dev/null -w '%{http_code}' https://smartpaybot.com.br/auth/register)"
ADMIN_CODE="$(curl -sS -o /dev/null -w '%{http_code}' https://smartpaybot.com.br/admin/)"
echo "HOME=$HOME_CODE LOGIN=$LOGIN_CODE REGISTER=$REGISTER_CODE ADMIN=$ADMIN_CODE"

if [ "$HOME_CODE" != "200" ] || [ "$LOGIN_CODE" != "200" ] || [ "$REGISTER_CODE" != "200" ]; then
    rollback_and_exit "smoke HTTP falhou (HOME=$HOME_CODE LOGIN=$LOGIN_CODE REGISTER=$REGISTER_CODE)."
fi
case "$ADMIN_CODE" in
    3*) : ;;
    *) rollback_and_exit "smoke /admin/ nao retornou redirect (obtido: $ADMIN_CODE)." ;;
esac

echo
echo "=== 9. GATE DO COOKIE (redigido) ==="
COOKIE_HDR="$(curl -sS -D - -o /dev/null https://smartpaybot.com.br/auth/login | grep -i '^set-cookie:' | head -1)"
if [ -n "$COOKIE_HDR" ]; then
    SESSION_COOKIE_NAME="$(echo "$COOKIE_HDR" | sed -E 's/^[Ss]et-[Cc]ookie:\s*([^=]+)=.*/\1/' | tr -d '\r')"
    echo "COOKIE_NAME=$SESSION_COOKIE_NAME"
    echo "Secure presente=$(echo "$COOKIE_HDR" | grep -qi 'Secure' && echo True || echo False)"
    echo "HttpOnly presente=$(echo "$COOKIE_HDR" | grep -qi 'HttpOnly' && echo True || echo False)"
    echo "SameSite=$(echo "$COOKIE_HDR" | grep -oiE 'SameSite=[A-Za-z]+' || echo ausente)"
    echo "Domain presente=$(echo "$COOKIE_HDR" | grep -qi 'Domain=' && echo True || echo False)"
    if [ "$SESSION_COOKIE_NAME" != "session" ]; then
        rollback_and_exit "cookie de producao nao se chama 'session' (encontrado: '$SESSION_COOKIE_NAME')."
    fi
else
    echo "AVISO: nenhum Set-Cookie observado em /auth/login (GET simples pode nao gravar sessao)."
    SESSION_COOKIE_NAME="session"
fi

echo
echo "=== 10. GATE VISUAL (ausencia do banner de homologacao) ==="
HOME_HTML="$(curl -sS https://smartpaybot.com.br/)"
BANNER_HITS=0
for marker in "HOMOLOGA" "AMBIENTE DE TESTES" "env-homologation"; do
    HITS="$(echo "$HOME_HTML" | grep -c "$marker" || true)"
    echo "ocorrencias de '$marker': $HITS"
    BANNER_HITS=$((BANNER_HITS + HITS))
done
if [ "$BANNER_HITS" -gt 0 ]; then
    HOMOLOGATION_BANNER_PRESENT="YES"
    rollback_and_exit "banner de homologacao presente em producao (BANNER_HITS=$BANNER_HITS)."
else
    HOMOLOGATION_BANNER_PRESENT="NO"
fi

echo
echo "=== 11. TELEGRAM -- SMOKE READ-ONLY (informativo, nao bloqueante) ==="
.venv/bin/python -c "
from infrastructure.telegram import telegram_ready, get_webhook_info
print('telegram_ready()=', telegram_ready())
info = get_webhook_info()
if info and info.get('ok'):
    r = info.get('result', {})
    print('webhook OK=', info.get('ok'))
    print('webhook URL=', r.get('url'))
    print('pending_update_count=', r.get('pending_update_count'))
    print('last_error_message=', r.get('last_error_message'))
else:
    print('getWebhookInfo retornou dado inesperado:', info)
" || echo "AVISO: smoke do Telegram falhou (nao bloqueante)."

echo
echo "=== 12. BANCO POS-DEPLOY (informativo, nao bloqueante por hash) ==="
DB_HASH_POST="$(sha256sum app.db | awk '{print $1}')"
echo "DB_HASH_POST=$DB_HASH_POST"
if [ "$DB_HASH_POST" != "$DB_HASH_PRE" ]; then
    echo "AVISO: hash do banco mudou apos o deploy (pode ser escrita legitima concorrente; Collector deve estar pausado)."
fi
INTEGRITY_POST="$(sqlite3 app.db "PRAGMA integrity_check;")"
echo "integrity_check pos=$INTEGRITY_POST"
FK_POST="$(sqlite3 app.db "PRAGMA foreign_key_check;")"
if [ "$INTEGRITY_POST" = "ok" ] && [ -z "$FK_POST" ]; then
    DATABASE_INTEGRITY="OK"
else
    DATABASE_INTEGRITY="NOT_OK"
    rollback_and_exit "integridade do banco comprometida apos o deploy (integrity=$INTEGRITY_POST, fk_check='$FK_POST')."
fi

echo
echo "=== 13. JOURNAL DESDE O RESTART (informativo) ==="
sudo journalctl -u smartpaybot --since "$RESTART_TS" --no-pager | grep -iE "traceback|runtimeerror|critical|error|exception" || echo "(nenhuma ocorrencia de erro no journal)"

PRODUCTION_HEAD="$(git rev-parse HEAD)"
echo
echo "=== DEPLOY CONCLUIDO COM SUCESSO ==="
emit_result "SUCCESS"
exit 0
