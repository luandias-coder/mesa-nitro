#!/usr/bin/env bash
# Watchdog da ponte MT5 <-> Supabase no VPS Windows.
# Checa via SSH se o processo python da ponte está vivo.
# Alerta no Telegram (@MesaNitroBot) só em TRANSIÇÃO de status (anti-spam por arquivo de estado).
# OK (>=1 python) | DOWN (0 python) | UNREACHABLE (SSH sem resposta).
set -uo pipefail
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:$PATH"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
STATE="$HERE/.watchdog_state"
LOG="$HERE/watchdog.log"

set -a; source "$HERE/vps.env"; set +a       # exporta VPS_HOST/USER/PASS
TG_TOKEN="$(grep -E '^TELEGRAM_BOT_TOKEN=' "$ROOT/.env" | cut -d= -f2-)"
TG_CHAT="$(grep -E '^TELEGRAM_CHAT_ID=' "$ROOT/.env" | cut -d= -f2-)"

stamp(){ date '+%Y-%m-%d %H:%M:%S'; }
logline(){ echo "$(stamp) $*" >> "$LOG"; }
tg(){
  [ -n "${TG_TOKEN:-}" ] && [ -n "${TG_CHAT:-}" ] || { logline "SEM token/chat Telegram"; return; }
  curl -s "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
    -d chat_id="$TG_CHAT" --data-urlencode "text=$1" -d parse_mode=HTML >/dev/null
}

# comando remoto (PowerShell): conta processos python da ponte
export SSH_CMD='$c=(Get-Process python -ErrorAction SilentlyContinue | Measure-Object).Count; Write-Output "PYOK:$c"'

OUT="$(mktemp)"
expect -f "$HERE/_ssh_check.exp" > "$OUT" 2>&1
RESULT="$(tr -d '\r' < "$OUT")"; rm -f "$OUT"

NOW_STATUS="UNREACHABLE"; DETAIL=""
if echo "$RESULT" | grep -q "PYOK:"; then
  N="$(echo "$RESULT" | grep -oE 'PYOK:[0-9]+' | head -1 | cut -d: -f2)"
  DETAIL="python=$N"
  if [ "${N:-0}" -ge 1 ]; then NOW_STATUS="OK"; else NOW_STATUS="DOWN"; fi
fi

PREV_STATUS="$(cat "$STATE" 2>/dev/null || echo UNKNOWN)"
logline "status=$NOW_STATUS prev=$PREV_STATUS [$DETAIL]"

if [ "$NOW_STATUS" != "$PREV_STATUS" ]; then
  case "$NOW_STATUS" in
    OK)          [ "$PREV_STATUS" != "UNKNOWN" ] && tg "✅ <b>Ponte MT5 recuperada</b> — voltou a rodar ($DETAIL)." ;;
    DOWN)        tg "🔴 <b>Ponte MT5 caiu</b> no VPS (processo python morto). Loga no console e reabre o bridge.bat — ou me chama. [$DETAIL]" ;;
    UNREACHABLE) tg "⚠️ <b>VPS inacessível</b> (SSH sem resposta). Pode ter reiniciado/travado — sem o teu logon a ponte não sobe. Olha o console da Vultr." ;;
  esac
  echo "$NOW_STATUS" > "$STATE"
fi
echo "$NOW_STATUS $DETAIL"
