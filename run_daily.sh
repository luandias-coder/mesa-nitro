#!/bin/bash
# run_daily.sh — orquestrador diário da Sala Nitro (pós-fechamento).
# Captura a live do dia -> transcript -> parser -> resolver -> dashboard.
# Roda via cron (dias úteis). Idempotente: se já processou o dia, reprocessa sem dano.
# INTERIM no Mac; quando o VPS entrar, isso migra pra lá (always-on).
set -uo pipefail

DIR="/Users/luandias/.openclaw/workspace-trading/projetos/live-mercado"
PLAYLIST="https://www.youtube.com/playlist?list=PLBXPCoq0WOd7zEXdiGj_I61SmJ-Ces94p"
cd "$DIR" || exit 1
mkdir -p logs subs
ISO="$(date +%F)"
LOG="logs/daily_${ISO}.log"
exec >>"$LOG" 2>&1
echo "================ RUN $(date) ================"

# venv
source .venv/bin/activate 2>/dev/null || { echo "ERRO: venv ausente"; exit 1; }

# 1) provider PO token up?
if ! curl -sf -m3 http://127.0.0.1:4416/ping >/dev/null 2>&1; then
  echo "[provider] subindo..."
  ( cd provider/server && nohup node build/main.js >/tmp/pot_provider.log 2>&1 & )
  sleep 5
  curl -sf -m3 http://127.0.0.1:4416/ping >/dev/null 2>&1 && echo "[provider] UP" || echo "[provider] FALHOU (segue mesmo assim)"
fi

# 2) achar o vídeo de hoje na playlist (título contém DD/MM)
DDMM="$(date +%d/%m)"
VID="$(yt-dlp --flat-playlist --print '%(id)s|%(title)s' "$PLAYLIST" 2>/dev/null | grep -F "$DDMM" | head -1 | cut -d'|' -f1)"
if [ -z "$VID" ]; then
  echo "[video] nenhum vídeo com '$DDMM' no título — talvez a live ainda não subiu. Abortando sem erro."
  exit 0
fi
echo "[video] $VID  (data $ISO)"

# 3) registrar no mapa videos.json (pro dashboard linkar)
python3 - "$ISO" "$VID" << 'PY'
import json,sys,os
iso,vid=sys.argv[1],sys.argv[2]
p="videos.json"; d=json.load(open(p)) if os.path.exists(p) else {}
d[iso]=vid; json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
print("[videos.json] +",iso,vid)
PY

# 4) legenda automática (precisa do provider p/ PO token)
yt-dlp --skip-download --write-auto-subs --sub-langs pt-orig --sub-format vtt \
  -o "subs/%(id)s.%(ext)s" "https://www.youtube.com/watch?v=${VID}" || { echo "[subs] falhou"; exit 1; }
VTT="subs/${VID}.pt-orig.vtt"
[ -f "$VTT" ] || { echo "[subs] vtt não encontrado: $VTT"; exit 1; }

# 5) pipeline
python3 vtt_to_transcript.py "$VTT" "transcript_${ISO}.txt" || exit 1
python3 parser.py "transcript_${ISO}.txt" --data "$ISO" --out "signals_parsed_${ISO}.json" || exit 1
python3 resolver.py "signals_parsed_${ISO}.json" --out "signals_resolved_${ISO}.json" || exit 1
python3 dashboard.py || exit 1
python3 build_xlsx.py 2>/dev/null || true

echo "================ OK $(date) — dia $ISO processado ================"
