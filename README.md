# Mesa Nitro 📈

Pipeline que assiste à live diária "Sala Nitro" (fechamento de mercado no YouTube),
extrai as recomendações de opções (entradas/saídas/ajustes de ~21 ativos) e entrega
um **cockpit** com a fila de ação do dia, carteira (analista × você), simulador e histórico.

## Arquitetura
- **Captura + IA (cron diário)** → GitHub Actions: legenda YT → `parser.py` (Anthropic) → `resolver.py` (ticker B3 real + strike).
- **Banco** → Supabase (Postgres).
- **Dashboard** → Vercel (lê do banco).
- **Execução** → VPS Windows (MT5/Rico, bridge Python). *Só execução.*

## Pipeline (manual)
```bash
python vtt_to_transcript.py subs/<id>.pt-orig.vtt transcript_<data>.txt
python parser.py transcript_<data>.txt --data <AAAA-MM-DD> --out signals_parsed_<data>.json
python resolver.py signals_parsed_<data>.json --out signals_resolved_<data>.json
python dashboard.py   # gera dashboard.html
```
`run_daily.sh` orquestra tudo (captura → parser → resolver → dashboard).

## Componentes
- `parser.py` — transcript → sinais estruturados (tool-use Anthropic).
- `resolver.py` — sinais → ticker real B3 + strike (grade opcoes.net.br).
- `dashboard.py` — gera o cockpit (`dashboard.html`), tema claro "Mesa Nitro".
- `tickers.yaml` — universo de 21 ativos + aliases da legenda.
- `gabarito_analista.yaml` — códigos reais da planilha do analista (validação).

## Setup local
- `python -m venv .venv && pip install yt-dlp bgutil-ytdlp-pot-provider anthropic openpyxl pyyaml`
- Provider PO token (clone bgutil) na porta 4416 — necessário p/ baixar legenda.
- `.env` com `ANTHROPIC_API_KEY=...` (não versionado).

> Identidade visual em `BRAND.md` (no workspace) · não commitar segredos.
