#!/usr/bin/env bash
# scripts/deploy-production-remote.sh
#
# Script remoto de deploy controlado do SmartPayBot em producao.
# Executado NA VPS. O orquestrador local (scripts/deploy-production.ps1)
# NUNCA envia o conteudo deste arquivo lido do filesystem local -- ele
# obtem o conteudo via `git show TARGET_SHA:scripts/deploy-production-remote.sh`
# e envia ESSE conteudo via stdin:
#
#   git show $TargetSha:scripts/deploy-production-remote.sh | ssh $DeployHost "bash -s -- $TargetSha $AppDir"
#
# Isso amarra criptograficamente TARGET_SHA ao codigo de deploy que sera
# efetivamente executado -- nao e possivel declarar um TARGET_SHA e rodar
# a logica de outro commit.
#
# Pode tambem ser copiado e executado manualmente na VPS para depuracao,
# ou futuramente reutilizado por um workflow de GitHub Actions (ver
# docs/runbooks/deploy-producao.md, secao "Futura automacao CI/CD").
#
# Recebe exatamente:
#   $1 = TARGET_SHA   (obrigatorio -- SHA git completo de 40 caracteres hex,
#                       e deve ser exatamente igual a origin/main)
#   $2 = APP_DIR       (opcional -- se informado, deve ser exatamente
#                       /home/deploy/apps/www.smartpaybot.com.br; qualquer
#                       outro valor e recusado nesta versao)
#
# Contrato:
#   - fail-fast / fail-closed: qualquer gate ANTES do restart que falhar
#     aborta (ou recupera) SEM tocar no servico em execucao.
#   - somente fast-forward: nunca merge de verdade, nunca reset --hard
#     alem do reversao explicita para PRE_DEPLOY_HEAD -- que so anda para
#     TRAS, na mesma linha de historico local, e NUNCA altera origin/main.
#   - nunca imprime valor de secret nem valor de cookie.
#   - sudo sempre nao-interativo (`sudo -n`); se nao disponivel, aborta
#     antes de qualquer alteracao.
#   - emite, ao final, linhas maquina-legiveis fixas (ver emit_result()).
#
# Codigos de saida:
#   0 = DEPLOY_STATUS=SUCCESS
#   1 = DEPLOY_STATUS=FAILED           (abortado ANTES do restart; se algo
#                                        ja tinha mudado localmente, foi
#                                        revertido com sucesso -- servico
#                                        antigo nunca foi tocado)
#   2 = DEPLOY_STATUS=ROLLED_BACK      (falhou DEPOIS do restart; codigo
#                                        revertido, servico religado e
#                                        validado com sucesso)
#   4 = DEPLOY_STATUS=RECOVERY_FAILED  (falhou ANTES do restart E a
#                                        reversao do codigo local nao pode
#                                        ser confirmada -- estado do
#                                        filesystem da VPS requer inspecao
#                                        manual imediata; servico nao foi
#                                        reiniciado, mas o codigo em disco
#                                        pode nao corresponder a nenhuma
#                                        versao conhecida)
#   5 = DEPLOY_STATUS=ROLLBACK_FAILED  (falhou DEPOIS do restart E o
#                                        rollback nao pode ser totalmente
#                                        validado -- requer inspecao manual
#                                        imediata; producao pode estar
#                                        degradada)

set -uo pipefail

readonly EXPECTED_APP_DIR="/home/deploy/apps/www.smartpaybot.com.br"
readonly EXPECTED_HOME_URL="https://smartpaybot.com.br/"
readonly EXPECTED_LOGIN_URL="https://smartpaybot.com.br/auth/login"
readonly EXPECTED_REGISTER_URL="https://smartpaybot.com.br/auth/register"
readonly EXPECTED_ADMIN_URL="https://smartpaybot.com.br/admin/"
readonly EXPECTED_WEBHOOK_URL="https://smartpaybot.com.br/webhook/telegram"

# ── argumentos ──────────────────────────────────────────────────────────
TARGET_SHA="${1:-}"
APP_DIR="${2:-$EXPECTED_APP_DIR}"

PRE_DEPLOY_HEAD=""
PRODUCTION_HEAD=""
DATABASE_INTEGRITY="NOT_OK"
SESSION_COOKIE_NAME="unknown"
HOMOLOGATION_BANNER_PRESENT="YES"
JOURNAL_ERROR_HITS="0"

emit_result() {
    local status="$1"
    echo "DEPLOY_STATUS=${status}"
    echo "PRE_DEPLOY_HEAD=${PRE_DEPLOY_HEAD}"
    echo "PRODUCTION_HEAD=${PRODUCTION_HEAD}"
    echo "TARGET_SHA=${TARGET_SHA}"
    echo "DATABASE_INTEGRITY=${DATABASE_INTEGRITY}"
    echo "SESSION_COOKIE_NAME=${SESSION_COOKIE_NAME}"
    echo "HOMOLOGATION_BANNER_PRESENT=${HOMOLOGATION_BANNER_PRESENT}"
    echo "JOURNAL_ERROR_HITS=${JOURNAL_ERROR_HITS}"
}

abort() {
    # Usado ANTES do restart, quando NENHUMA reversao de codigo era
    # necessaria (nada mudou ainda, ou a reversao ja foi confirmada por
    # recover_or_die()). Servico antigo nunca foi tocado.
    echo "ABORT: $1" >&2
    if [ -z "$PRODUCTION_HEAD" ]; then
        PRODUCTION_HEAD="${PRE_DEPLOY_HEAD}"
    fi
    emit_result "FAILED"
    exit 1
}

recover_or_die() {
    # Usado ANTES do restart, quando o codigo local JA foi adiantado
    # (fast-forward feito) e precisa voltar para PRE_DEPLOY_HEAD. Nunca
    # assume que `git reset --hard` funcionou -- verifica explicitamente.
    local reason="$1"
    echo "RECOVERY: $reason" >&2

    if [ -z "$PRE_DEPLOY_HEAD" ]; then
        # Nada foi adiantado ainda -- equivalente a abort simples.
        abort "$reason"
    fi

    git reset --hard "$PRE_DEPLOY_HEAD" >&2
    local reset_rc=$?
    local head_now
    head_now="$(git rev-parse HEAD 2>/dev/null || echo "")"
    PRODUCTION_HEAD="$head_now"

    if [ "$reset_rc" -eq 0 ] && [ "$head_now" = "$PRE_DEPLOY_HEAD" ]; then
        abort "$reason (codigo revertido com sucesso para PRE_DEPLOY_HEAD; servico antigo nunca foi reiniciado)"
    else
        echo "RECOVERY FALHOU: reset_rc=$reset_rc head_now='$head_now' esperado='$PRE_DEPLOY_HEAD'" >&2
        emit_result "RECOVERY_FAILED"
        exit 4
    fi
}

rollback_and_exit() {
    # Usado DEPOIS do restart -- reverte o codigo, religa o servico
    # antigo, e VALIDA cada etapa explicitamente antes de declarar sucesso
    # do rollback. Nunca assume; sempre confere.
    local reason="$1"
    echo "ROLLBACK: $reason" >&2
    local ok="true"

    git reset --hard "$PRE_DEPLOY_HEAD" >&2
    local reset_rc=$?
    [ "$reset_rc" -eq 0 ] || ok="false"

    local head_now
    head_now="$(git rev-parse HEAD 2>/dev/null || echo "")"
    PRODUCTION_HEAD="$head_now"
    [ "$head_now" = "$PRE_DEPLOY_HEAD" ] || ok="false"

    sudo -n systemctl restart smartpaybot >&2
    local restart_rc=$?
    [ "$restart_rc" -eq 0 ] || ok="false"
    sleep 3

    sudo -n systemctl is-active --quiet smartpaybot
    local active_rc=$?
    [ "$active_rc" -eq 0 ] || ok="false"

    local has_loopback="no"
    local has_public="no"
    if ss -ltnp | grep -q '127\.0\.0\.1:8000'; then has_loopback="yes"; fi
    if ss -ltnp | grep -q '0\.0\.0\.0:8000'; then has_public="yes"; fi
    [ "$has_loopback" = "yes" ] || ok="false"
    [ "$has_public" = "no" ] || ok="false"

    local home_code
    home_code="$(curl -sS -o /dev/null -w '%{http_code}' "$EXPECTED_HOME_URL" 2>/dev/null || echo "000")"
    [ "$home_code" = "200" ] || ok="false"

    echo "rollback checks: reset_rc=$reset_rc head_match=$([ "$head_now" = "$PRE_DEPLOY_HEAD" ] && echo yes || echo no) restart_rc=$restart_rc active_rc=$active_rc loopback=$has_loopback public_exposed=$has_public home_code=$home_code" >&2

    if [ "$ok" = "true" ]; then
        emit_result "ROLLED_BACK"
        exit 2
    else
        echo "ROLLBACK NAO PODE SER TOTALMENTE VALIDADO -- inspecao manual imediata necessaria." >&2
        emit_result "ROLLBACK_FAILED"
        exit 5
    fi
}

# ── 1. validar TARGET_SHA e APP_DIR (antes de qualquer efeito colateral) ──
if [[ ! "$TARGET_SHA" =~ ^[0-9a-f]{40}$ ]]; then
    abort "TARGET_SHA ausente ou invalido (esperado SHA git completo de 40 hex chars minusculos)."
fi
if [ "$APP_DIR" != "$EXPECTED_APP_DIR" ]; then
    abort "APP_DIR ('$APP_DIR') diferente do unico diretorio de producao suportado nesta versao ('$EXPECTED_APP_DIR')."
fi
if [ ! -d "$APP_DIR" ]; then
    abort "APP_DIR nao encontrado: $APP_DIR"
fi
cd "$APP_DIR" || abort "nao foi possivel entrar em $APP_DIR"

echo "=== 1. PREFLIGHT REMOTO ==="
echo "APP_DIR=$(pwd)"
echo "TARGET_SHA=$TARGET_SHA"

# sudo nao-interativo obrigatorio -- falhar rapido, nunca pedir senha
# com o Collector ja pausado no lado local.
if ! sudo -n true 2>/dev/null; then
    abort "sudo nao-interativo indisponivel ('sudo -n true' falhou). Configure sudoers antes de tentar o deploy; nenhuma alteracao foi feita."
fi

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
    abort "TARGET_SHA ($TARGET_SHA) difere de origin/main ($ORIGIN_MAIN) -- esta versao do deploy exige TARGET_SHA == origin/main exatamente."
fi

if ! git cat-file -e "${TARGET_SHA}^{commit}" 2>/dev/null; then
    abort "TARGET_SHA nao existe como commit no repositorio local apos fetch."
fi

if ! git merge-base --is-ancestor "$PRE_DEPLOY_HEAD" "$TARGET_SHA"; then
    abort "PRE_DEPLOY_HEAD nao e ancestral de TARGET_SHA -- fast-forward nao e seguro (historico divergente)."
fi

# ── worktree tracked limpo ────────────────────────────────────────────
TRACKED_DIRTY="$(git status --short | grep -vE '^\?\? backups/' || true)"
if [ -n "$TRACKED_DIRTY" ]; then
    echo "$TRACKED_DIRTY" >&2
    abort "ha modificacao tracked inesperada no worktree de producao."
fi

echo
echo "=== 2. SAUDE PRE-DEPLOY (hard gate -- nao tentar consertar via deploy) ==="
if ! sudo -n systemctl is-active --quiet smartpaybot; then
    abort "servico smartpaybot nao esta active antes do deploy -- producao ja unhealthy."
fi
if ! ss -ltnp | grep -q '127\.0\.0\.1:8000'; then
    abort "nenhum listener em 127.0.0.1:8000 antes do deploy."
fi
if ss -ltnp | grep -q '0\.0\.0\.0:8000'; then
    abort "listener publico 0.0.0.0:8000 detectado antes do deploy -- investigar manualmente antes de qualquer automacao."
fi
HOME_PRE="$(curl -sS -o /dev/null -w '%{http_code}' "$EXPECTED_HOME_URL" 2>/dev/null || echo "000")"
LOGIN_PRE="$(curl -sS -o /dev/null -w '%{http_code}' "$EXPECTED_LOGIN_URL" 2>/dev/null || echo "000")"
echo "HOME_PRE=$HOME_PRE LOGIN_PRE=$LOGIN_PRE"
if [ "$HOME_PRE" != "200" ] || [ "$LOGIN_PRE" != "200" ]; then
    abort "producao ja esta unhealthy antes do deploy (HOME=$HOME_PRE LOGIN=$LOGIN_PRE) -- nao tentar consertar via deploy."
fi

echo
echo "=== 3. CONFIGURACAO SEGURA (gate completo, sem imprimir segredos) ==="
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

CONFIG_FAIL=""
for expected_line in \
    "APP_ENV=production" \
    "FLASK_ENV=production" \
    "TELEGRAM_MODE=production" \
    "SCHEDULER_ENABLED=False" \
    "TELEGRAM_TOKEN_SET=True" \
    "TELEGRAM_WEBHOOK_SECRET_SET=True" \
    "INTERNAL_INGEST_TOKEN_SET=True" \
    "SECRET_KEY_SET=True"
do
    if ! printf '%s\n' "$CONFIG_CHECK_OUT" | grep -qx -- "$expected_line"; then
        CONFIG_FAIL="${CONFIG_FAIL:+$CONFIG_FAIL,}${expected_line%%=*}"
    fi
done
if [ -n "$CONFIG_FAIL" ]; then
    abort "config gate reprovou os seguintes campos: $CONFIG_FAIL"
fi

echo
echo "=== 4. BACKUP ONLINE DO BANCO (sqlite3 .backup) ==="
INTEGRITY_PRE="$(sqlite3 app.db "PRAGMA integrity_check;")"
echo "integrity_check pre (banco vivo)=$INTEGRITY_PRE"
if [ "$INTEGRITY_PRE" != "ok" ]; then
    abort "PRAGMA integrity_check do banco vivo != ok antes do deploy."
fi
FK_PRE="$(sqlite3 app.db "PRAGMA foreign_key_check;")"
if [ -n "$FK_PRE" ]; then
    abort "PRAGMA foreign_key_check do banco vivo encontrou inconsistencias antes do deploy."
fi

mkdir -p backups
chmod 700 backups
BACKUP_NAME="backups/app.db.pre-deploy-$(date +%Y%m%d-%H%M%S).bak"
sqlite3 app.db ".backup '$BACKUP_NAME'"
BACKUP_RC=$?
if [ "$BACKUP_RC" -ne 0 ] || [ ! -s "$BACKUP_NAME" ]; then
    abort "backup online do banco (sqlite3 .backup) falhou ou gerou arquivo vazio."
fi
chmod 600 "$BACKUP_NAME"

BACKUP_INTEGRITY="$(sqlite3 "$BACKUP_NAME" "PRAGMA integrity_check;")"
BACKUP_FK="$(sqlite3 "$BACKUP_NAME" "PRAGMA foreign_key_check;")"
if [ "$BACKUP_INTEGRITY" != "ok" ] || [ -n "$BACKUP_FK" ]; then
    abort "backup criado mas reprovou na validacao propria (integrity=$BACKUP_INTEGRITY, fk_check_presente=$([ -n "$BACKUP_FK" ] && echo yes || echo no))."
fi
echo "backup validado: $BACKUP_NAME ($(stat -c%s "$BACKUP_NAME") bytes)"

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
    recover_or_die "test gate falhou pos-update (TEST_RC=$TEST_RC COMPILE_RC=$COMPILE_RC)."
fi

echo
echo "=== 7. CONFIG DE SESSAO (B4) -- ANTES DO RESTART, SEM TOCAR TELEGRAM ==="
COOKIE_CFG_OUT="$(.venv/bin/python -c "
from app import create_app
app = create_app()
c = app.config
print('SESSION_COOKIE_NAME=' + str(c['SESSION_COOKIE_NAME']))
print('SESSION_COOKIE_SECURE=' + str(c['SESSION_COOKIE_SECURE']))
print('SESSION_COOKIE_HTTPONLY=' + str(c['SESSION_COOKIE_HTTPONLY']))
print('SESSION_COOKIE_SAMESITE=' + str(c['SESSION_COOKIE_SAMESITE']))
print('SESSION_COOKIE_DOMAIN=' + str(c['SESSION_COOKIE_DOMAIN']))
print('SESSION_COOKIE_PATH=' + str(c['SESSION_COOKIE_PATH']))
" 2>&1)"
echo "$COOKIE_CFG_OUT"

COOKIE_CFG_FAIL=""
for expected_line in \
    "SESSION_COOKIE_NAME=session" \
    "SESSION_COOKIE_SECURE=True" \
    "SESSION_COOKIE_HTTPONLY=True" \
    "SESSION_COOKIE_SAMESITE=Lax" \
    "SESSION_COOKIE_DOMAIN=None" \
    "SESSION_COOKIE_PATH=/"
do
    if ! printf '%s\n' "$COOKIE_CFG_OUT" | grep -qx -- "$expected_line"; then
        COOKIE_CFG_FAIL="${COOKIE_CFG_FAIL:+$COOKIE_CFG_FAIL,}${expected_line%%=*}"
    fi
done
if [ -n "$COOKIE_CFG_FAIL" ]; then
    recover_or_die "config de sessao (B4) reprovou antes do restart (campos: $COOKIE_CFG_FAIL)."
fi

echo
echo "=== 8. RESTART ==="
RESTART_TS="$(date --iso-8601=seconds)"
echo "RESTART_TS=$RESTART_TS"
sudo -n systemctl restart smartpaybot
RESTART_RC=$?
if [ "$RESTART_RC" -ne 0 ]; then
    rollback_and_exit "systemctl restart smartpaybot falhou (rc=$RESTART_RC)."
fi
sleep 3
if ! sudo -n systemctl is-active --quiet smartpaybot; then
    rollback_and_exit "servico nao ficou active apos restart."
fi
if ss -ltnp | grep -q '0\.0\.0\.0:8000'; then
    rollback_and_exit "servico bindado em 0.0.0.0:8000 (exposto publicamente) apos restart."
fi
if ! ss -ltnp | grep -q '127\.0\.0\.1:8000'; then
    rollback_and_exit "servico nao esta escutando em 127.0.0.1:8000 apos restart."
fi

echo
echo "=== 9. SMOKE HTTP ==="
HOME_CODE="$(curl -sS -o /dev/null -w '%{http_code}' "$EXPECTED_HOME_URL")"
LOGIN_CODE="$(curl -sS -o /dev/null -w '%{http_code}' "$EXPECTED_LOGIN_URL")"
REGISTER_CODE="$(curl -sS -o /dev/null -w '%{http_code}' "$EXPECTED_REGISTER_URL")"
ADMIN_CODE="$(curl -sS -o /dev/null -w '%{http_code}' "$EXPECTED_ADMIN_URL")"
echo "HOME=$HOME_CODE LOGIN=$LOGIN_CODE REGISTER=$REGISTER_CODE ADMIN=$ADMIN_CODE"

if [ "$HOME_CODE" != "200" ] || [ "$LOGIN_CODE" != "200" ] || [ "$REGISTER_CODE" != "200" ]; then
    rollback_and_exit "smoke HTTP falhou (HOME=$HOME_CODE LOGIN=$LOGIN_CODE REGISTER=$REGISTER_CODE)."
fi
case "$ADMIN_CODE" in
    3*) : ;;
    *) rollback_and_exit "smoke /admin/ nao retornou redirect (obtido: $ADMIN_CODE)." ;;
esac

echo
echo "=== 10. GATE DO COOKIE (fail-closed, redigido) ==="
COOKIE_HDR="$(curl -sS -D - -o /dev/null "$EXPECTED_LOGIN_URL" | grep -i '^set-cookie:' | head -1)"
if [ -z "$COOKIE_HDR" ]; then
    rollback_and_exit "nenhum Set-Cookie observado em /auth/login apos o deploy -- gate fail-closed (ausencia de cookie e tratada como falha, nunca como sucesso presumido)."
fi

SESSION_COOKIE_NAME="$(echo "$COOKIE_HDR" | sed -E 's/^[Ss]et-[Cc]ookie:\s*([^=]+)=.*/\1/' | tr -d '\r')"
SECURE_PRESENT="no"; HTTPONLY_PRESENT="no"; DOMAIN_PRESENT="no"
echo "$COOKIE_HDR" | grep -qi 'Secure' && SECURE_PRESENT="yes"
echo "$COOKIE_HDR" | grep -qi 'HttpOnly' && HTTPONLY_PRESENT="yes"
echo "$COOKIE_HDR" | grep -qi 'Domain=' && DOMAIN_PRESENT="yes"
SAMESITE_VAL="$(echo "$COOKIE_HDR" | grep -oiE 'SameSite=[A-Za-z]+' | cut -d= -f2 | tr -d '\r')"
PATH_VAL="$(echo "$COOKIE_HDR" | grep -oiE 'Path=[^;[:space:]]+' | cut -d= -f2 | tr -d '\r')"

echo "COOKIE_NAME=$SESSION_COOKIE_NAME"
echo "Secure presente=$SECURE_PRESENT"
echo "HttpOnly presente=$HTTPONLY_PRESENT"
echo "SameSite=$SAMESITE_VAL"
echo "Path=$PATH_VAL"
echo "Domain presente=$DOMAIN_PRESENT"

COOKIE_FAIL=""
[ "$SESSION_COOKIE_NAME" = "session" ] || COOKIE_FAIL="${COOKIE_FAIL:+$COOKIE_FAIL,}nome"
[ "$SECURE_PRESENT" = "yes" ] || COOKIE_FAIL="${COOKIE_FAIL:+$COOKIE_FAIL,}Secure"
[ "$HTTPONLY_PRESENT" = "yes" ] || COOKIE_FAIL="${COOKIE_FAIL:+$COOKIE_FAIL,}HttpOnly"
[ "$SAMESITE_VAL" = "Lax" ] || COOKIE_FAIL="${COOKIE_FAIL:+$COOKIE_FAIL,}SameSite"
[ "$PATH_VAL" = "/" ] || COOKIE_FAIL="${COOKIE_FAIL:+$COOKIE_FAIL,}Path"
[ "$DOMAIN_PRESENT" = "no" ] || COOKIE_FAIL="${COOKIE_FAIL:+$COOKIE_FAIL,}DomainPresente"

if [ -n "$COOKIE_FAIL" ]; then
    rollback_and_exit "cookie de producao divergente do contrato B4 (campos com problema: $COOKIE_FAIL)."
fi

echo
echo "=== 11. GATE VISUAL (ausencia do banner de homologacao) ==="
HOME_HTML="$(curl -sS "$EXPECTED_HOME_URL")"
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
echo "=== 12. TELEGRAM (gate obrigatorio, read-only) ==="
TG_CHECK_OUT="$(.venv/bin/python -c "
from infrastructure.telegram import telegram_ready, get_webhook_info
ready = telegram_ready()
print('TELEGRAM_READY=' + str(ready))
info = get_webhook_info()
ok = bool(info and info.get('ok'))
print('WEBHOOK_OK=' + str(ok))
if ok:
    r = info.get('result', {}) or {}
    print('WEBHOOK_URL=' + str(r.get('url') or ''))
    print('PENDING_UPDATE_COUNT=' + str(r.get('pending_update_count')))
    print('LAST_ERROR_PRESENT=' + str(bool(r.get('last_error_message'))))
else:
    print('WEBHOOK_URL=')
    print('PENDING_UPDATE_COUNT=')
    print('LAST_ERROR_PRESENT=')
" 2>&1)"
echo "$TG_CHECK_OUT"

TG_READY_OK="no"
printf '%s\n' "$TG_CHECK_OUT" | grep -qx 'TELEGRAM_READY=True' && TG_READY_OK="yes"
WEBHOOK_OK="no"
printf '%s\n' "$TG_CHECK_OUT" | grep -qx 'WEBHOOK_OK=True' && WEBHOOK_OK="yes"
WEBHOOK_URL_SEEN="$(printf '%s\n' "$TG_CHECK_OUT" | sed -n 's/^WEBHOOK_URL=//p')"

if [ "$TG_READY_OK" != "yes" ]; then
    rollback_and_exit "telegram_ready() retornou False apos o deploy -- Telegram e core neste deploy de producao."
fi
if [ "$WEBHOOK_OK" != "yes" ]; then
    rollback_and_exit "getWebhookInfo() nao retornou ok=True apos o deploy."
fi
if [ "$WEBHOOK_URL_SEEN" != "$EXPECTED_WEBHOOK_URL" ]; then
    rollback_and_exit "webhook URL divergente do esperado apos o deploy (obtido: '$WEBHOOK_URL_SEEN', esperado: '$EXPECTED_WEBHOOK_URL')."
fi

echo
echo "=== 13. BANCO POS-DEPLOY ==="
INTEGRITY_POST="$(sqlite3 app.db "PRAGMA integrity_check;")"
echo "integrity_check pos=$INTEGRITY_POST"
FK_POST="$(sqlite3 app.db "PRAGMA foreign_key_check;")"
if [ "$INTEGRITY_POST" = "ok" ] && [ -z "$FK_POST" ]; then
    DATABASE_INTEGRITY="OK"
else
    DATABASE_INTEGRITY="NOT_OK"
    rollback_and_exit "integridade do banco comprometida apos o deploy (integrity=$INTEGRITY_POST, fk_check_presente=$([ -n "$FK_POST" ] && echo yes || echo no))."
fi

echo
echo "=== 14. JOURNAL DESDE O RESTART (somente contagem -- nunca linhas completas) ==="
JOURNAL_ERROR_HITS="$(sudo -n journalctl -u smartpaybot --since "$RESTART_TS" --no-pager 2>/dev/null | grep -ciE "traceback|runtimeerror|critical|error|exception" || true)"
echo "JOURNAL_ERROR_HITS=$JOURNAL_ERROR_HITS"
if [ "$JOURNAL_ERROR_HITS" -gt 0 ]; then
    echo "AVISO: journal registrou ${JOURNAL_ERROR_HITS} ocorrencia(s) de padroes de erro desde o restart -- inspecionar manualmente com 'journalctl -u smartpaybot --since \"$RESTART_TS\"' (linhas completas nao sao impressas automaticamente para evitar vazar PII/secret de codigo futuro)." >&2
fi

PRODUCTION_HEAD="$(git rev-parse HEAD)"
echo
echo "=== DEPLOY CONCLUIDO COM SUCESSO ==="
emit_result "SUCCESS"
exit 0
