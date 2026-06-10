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
#             + Chrome logado no YouTube (conta premium) p/ --cookies-from-browser.
# ============================================================================
set -uo pipefail
ROOT="/Users/luandias/.openclaw/workspace-trading/projetos/live-mercado"
cd "$ROOT" || exit 1

VENV="/Users/luandias/.openclaw/mesa-nitro-venv"
PY="$VENV/bin/python"
YTDLP="$VENV/bin/yt-dlp"
COOKIE_FILE="/Users/luandias/.openclaw/secrets/youtube-cookies-fresh.txt"
LOG="ops/fallback.log"
mkdir -p ops subs
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

# 2) achar o vídeo do dia na playlist
VID=$("$YTDLP" --cookies-from-browser chrome --flat-playlist --print '%(id)s|%(title)s' "$PLAYLIST" 2>/dev/null | grep -F "$DDMM" | head -1 | cut -d'|' -f1)
if [ -z "$VID" ]; then
  echo "sem vídeo p/ $DDMM na playlist"
  tg "🔕 <b>Mesa Nitro</b> — fallback local: nenhuma live encontrada na playlist p/ $ISO (feriado/sem live?)."
  exit 0
fi
echo "vídeo do dia: $VID"

# 3) capturar legenda — tenta cookie do Chrome (sempre fresco), fallback p/ arquivo salvo
VTT="subs/$VID.pt-orig.vtt"
rm -f "$VTT"
"$YTDLP" --cookies-from-browser chrome --skip-download --write-auto-subs --sub-langs pt-orig --sub-format vtt -o "subs/%(id)s.%(ext)s" "https://www.youtube.com/watch?v=$VID" 2>&1 | tail -3
if [ ! -s "$VTT" ] && [ -s "$COOKIE_FILE" ]; then
  echo "cookies-from-browser falhou — tentando cookie salvo"
  "$YTDLP" --cookies "$COOKIE_FILE" --skip-download --write-auto-subs --sub-langs pt-orig --sub-format vtt -o "subs/%(id)s.%(ext)s" "https://www.youtube.com/watch?v=$VID" 2>&1 | tail -3
fi
if [ ! -s "$VTT" ]; then
  echo "captura FALHOU (sem .vtt)"
  tg "⚠️ <b>Mesa Nitro</b> — fallback local $ISO FALHOU na captura (sem legenda). Cookie do YouTube pode ter expirado — reexporta e me manda."
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
