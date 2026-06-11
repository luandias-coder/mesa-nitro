#!/bin/bash
# Feed de preço das opções (opcoes.net.br -> Supabase). Roda a cada 10min via launchd;
# precos.py se auto-limita ao pregão (10:00-17:20 BRT, dias úteis).
cd /Users/luandias/.openclaw/workspace-trading/projetos/live-mercado || exit 1
set -a; . ./.env; set +a
echo "=== $(date '+%F %T') ===" >> ops/precos.log
/Users/luandias/.openclaw/mesa-nitro-venv/bin/python precos.py >> ops/precos.log 2>&1
