#!/bin/bash
# ============================================================================
# Fallback residencial da captura diária da Sala Nitro.
# Roda ~18h10 BRT (launchd com.nitro.fallback) NESTE Mac (IP residencial).
#
# Lógica (pedido do Luan 2026-06-10): o cloud (GitHub Actions) tenta às 18h;
# se falhar (bot-block de datacenter) ou nem disparar, este script — que roda
# pouco depois — detecta que a live de hoje NÃO está no Supabase e captura aqui,
# onde o YouTube não bloqueia. Idempotente: se o cloud já carregou, não faz nada.
#
# Requisitos: venv persistente + .env (SUPABASE_*, ANTHROPIC_API_KEY, TG, PLAYLIST)
#             + provider de PO TOKEN (bgutil) no ar (porta 4416) -> captura SEM cookie,
#               imune à rotação diária do YouTube e funciona em background (sem Keychain).
#               Cookie do Chrome fica só como último recurso.
# ============================================================================
set -uo pipefail
ROOT="/Users/luandias/.openclaw/workspace-trading/projetos/live-mercado"
cd "$ROOT" || exit 1

VENV="/Users/luandias/.openclaw/mesa-nitro-venv"
PY="$VENV/bin/python"
YTDLP="$VENV/bin/yt-dlp"
COOKIE_FILE="/Users/luandias/.openclaw/secrets/youtube-cookies-fresh.txt"
POT_GEN="$ROOT/provider/server/build/generate_once.js"   # modo script (sem daemon)
POT_MAIN="$ROOT/provider/server/build/main.js"           # server :4416
LOG="ops/fallback.log"
mkdir -p ops subs

# Garante o provider de PO token no ar (HTTP :4416). Sem ele o YouTube não entrega
# a legenda automática (exige PO token desde 2025). Boot idempotente.
ensure_pot(){
  if curl -sf -m3 http://127.0.0.1:4416/ping >/dev/null 2>&1; then return 0; fi
  echo "[pot] server caído — subindo $POT_MAIN"
  ( cd "$ROOT/provider/server" && nohup node build/main.js >/tmp/pot_provider.log 2>&1 & )
  for i in 1 2 3 4 5 6; do sleep 2; curl -sf -m3 http://127.0.0.1:4416/ping >/dev/null 2>&1 && { echo "[pot] UP"; return 0; }; done
  echo "[pot] FALHOU boot — yt-dlp vai tentar modo script como fallback"
}
# Baixa legenda automática SEM cookie via PO token. $1=VID $2=saida.vtt
# 1ª tentativa: HTTP server (já no ar). 2ª: modo script (node on-demand). 3ª: cookie.
fetch_subs(){
  local vid="$1" out="$2"
  rm -f "$out"
  "$YTDLP" --skip-download --write-auto-subs --sub-langs pt-orig --sub-format vtt \
    -o "subs/%(id)s.%(ext)s" "https://www.youtube.com/watch?v=$vid" 2>&1 | tail -2
  [ -s "$out" ] && return 0
  echo "[subs] HTTP-POT vazio — tentando modo script"
  "$YTDLP" --extractor-args "youtubepot-bgutilscript:script_path=$POT_GEN" \
    --skip-download --write-auto-subs --sub-langs pt-orig --sub-format vtt \
    -o "subs/%(id)s.%(ext)s" "https://www.youtube.com/watch?v=$vid" 2>&1 | tail -2
  [ -s "$out" ] && return 0
  echo "[subs] POT falhou — último recurso: cookie do Chrome"
  "$YTDLP" --cookies-from-browser chrome --skip-download --write-auto-subs --sub-langs pt-orig --sub-format vtt \
    -o "subs/%(id)s.%(ext)s" "https://www.youtube.com/watch?v=$vid" 2>&1 | tail -2
  [ -s "$out" ] && return 0
  [ -s "$COOKIE_FILE" ] && "$YTDLP" --cookies "$COOKIE_FILE" --skip-download --write-auto-subs --sub-langs pt-orig --sub-format vtt \
    -o "subs/%(id)s.%(ext)s" "https://www.youtube.com/watch?v=$vid" 2>&1 | tail -2
  [ -s "$out" ]
}
exec >> "$LOG" 2>&1

# carrega .env (exporta tudo)
set -a; . ./.env; set +a

ISO=$(TZ=America/Sao_Paulo date +%F)
DDMM=$(TZ=America/Sao_Paulo date +%d/%m)
DOW=$(TZ=America/Sao_Paulo date +%u)   # 1-7 (6=sáb,7=dom)
echo "===================================================================="
echo "$(date '+%F %T') — fallback start (ISO=$ISO, DDMM=$DDMM, dow=$DOW)"

tg(){ [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="${TELEGRAM_CHAT_ID}" --data-urlencode "text=$1" -d parse_mode=HTML >/dev/null 2>&1 || true; }

# fim de semana: sem live
if [ "$DOW" = "6" ] || [ "$DOW" = "7" ]; then echo "fim de semana - sem live, saindo"; exit 0; fi

# 1) cloud já carregou? (live de hoje no Supabase)
N=$(curl -s "$SUPABASE_URL/rest/v1/sinais?select=codigo&data=eq.$ISO" \
      -H "apikey: $SUPABASE_SECRET" -H "Authorization: Bearer $SUPABASE_SECRET" --max-time 20 \
      | $PY -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
if [ "$N" != "0" ] && [ "$N" != "" ]; then
  echo "cloud OK ($N sinais p/ $ISO) - nada a fazer"
  exit 0
fi
echo "cloud NÃO carregou ($ISO) - acionando fallback local"
tg "🖥️ <b>Mesa Nitro</b> — cloud não carregou $ISO. Rodando captura de <b>fallback</b> neste Mac…"

# garante o provider de PO token antes de falar com o YouTube
ensure_pot

# 2) achar o vídeo do dia na playlist (cookieless via POT)
VID=$("$YTDLP" --flat-playlist --print '%(id)s|%(title)s' "$PLAYLIST" 2>/dev/null | grep -F "$DDMM" | head -1 | cut -d'|' -f1)
if [ -z "$VID" ]; then
  echo "sem vídeo p/ $DDMM na playlist"
  tg "🔕 <b>Mesa Nitro</b> — fallback local: nenhuma live encontrada na playlist p/ $ISO (feriado/sem live?)."
  exit 0
fi
echo "vídeo do dia: $VID"

# 3) capturar legenda — PO token (cookieless) primário; cookie só como último recurso
VTT="subs/$VID.pt-orig.vtt"
if ! fetch_subs "$VID" "$VTT"; then
  echo "captura FALHOU (sem .vtt)"
  tg "⚠️ <b>Mesa Nitro</b> — fallback local $ISO FALHOU na captura (sem legenda). Provider de PO token caiu E cookie expirou — checar /tmp/pot_provider.log e relogar o Chrome."
  exit 1
fi
echo "legenda capturada: $(wc -l < "$VTT") linhas"

# 4) pipeline: transcript -> parser -> resolver -> load (conta=real)
"$PY" vtt_to_transcript.py "$VTT" "transcript_$ISO.txt" || { tg "⚠️ fallback $ISO: vtt_to_transcript falhou"; exit 1; }
"$PY" parser.py "transcript_$ISO.txt" --data "$ISO" --out "signals_parsed_$ISO.json" || { tg "⚠️ fallback $ISO: parser falhou"; exit 1; }
"$PY" resolver.py "signals_parsed_$ISO.json" --out "signals_resolved_$ISO.json" || { tg "⚠️ fallback $ISO: resolver falhou"; exit 1; }
ORDENS_CONTA=real "$PY" load_supabase.py || { tg "⚠️ fallback $ISO: load_supabase falhou"; exit 1; }

NSIG=$(curl -s "$SUPABASE_URL/rest/v1/sinais?select=codigo&data=eq.$ISO" -H "apikey: $SUPABASE_SECRET" -H "Authorization: Bearer $SUPABASE_SECRET" --max-time 20 | $PY -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?")
echo "$(date '+%F %T') — fallback OK ($NSIG sinais carregados)"
tg "✅ <b>Mesa Nitro</b> — fallback local processou a live de <b>$ISO</b> ($NSIG sinais). Confira a fila no /v2."
exit 0
