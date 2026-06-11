#!/usr/bin/env python3
"""Módulo Hi-Lo (à parte): calcula o Hi-Lo Activator dos ativos do universo a partir
do OHLC diário (Yahoo Finance) e compara com a direção do analista (CALL=alta, PUT=baixa).
Escreve web/v2/hilo.json (o dashboard lê e mostra). NÃO depende do MT5 nem de tabela nova.

Hi-Lo Activator (period n, default 3): verde/ALTA quando o close cruza ACIMA da SMA(High,n);
vermelho/BAIXA quando cruza ABAIXO da SMA(Low,n); mantém a tendência entre cruzamentos.

Uso: python hilo.py [--period 3]
"""
import json, os, sys, warnings, datetime
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("SUPABASE_URL", "https://mqcryomwdwnosoqfmyak.supabase.co").rstrip("/")
SBK = os.environ.get("SUPABASE_PUBLISHABLE", "sb_publishable_GozaOIA6rPwYFpgiOh60lg_OAmWvMCP")
PERIOD = 3
for i, a in enumerate(sys.argv):
    if a == "--period" and i + 1 < len(sys.argv):
        PERIOD = int(sys.argv[i + 1])


def universo_e_direcao():
    """ativo -> tipo do analista (CALL/PUT) a partir de posicoes_analista."""
    import urllib.request
    req = urllib.request.Request(
        f"{SB}/rest/v1/posicoes_analista?select=underlying,tipo",
        headers={"apikey": SBK, "Authorization": f"Bearer {SBK}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        pos = json.load(r)
    out = {}
    for p in pos:
        u, t = p.get("underlying"), (p.get("tipo") or "").upper()
        if u and t in ("CALL", "PUT"):
            out[u] = t
    return out


def hilo_trend(df, n=3):
    if len(df) < n + 2:
        return None, None
    highs = df["High"].rolling(n).mean()
    lows = df["Low"].rolling(n).mean()
    trend = None
    flip_date = None
    for i in range(n, len(df)):
        c = float(df["Close"].iloc[i])
        prev = trend
        if c > float(highs.iloc[i - 1]):
            trend = "alta"
        elif c < float(lows.iloc[i - 1]):
            trend = "baixa"
        if trend != prev and trend is not None:
            flip_date = str(df.index[i].date())
    return trend, flip_date


def main():
    import yfinance as yf
    want = universo_e_direcao()
    items = []
    ok = tot = 0
    for u, t in sorted(want.items()):
        analista = "baixa" if t == "PUT" else "alta"
        try:
            df = yf.download(u + ".SA", period="3mo", interval="1d",
                             progress=False, auto_adjust=True)
            tr, flip = hilo_trend(df, PERIOD)
        except Exception:
            tr, flip = None, None
        agree = None
        if tr is not None:
            tot += 1
            agree = (tr == analista)
            ok += 1 if agree else 0
        items.append({"ativo": u, "tipo": t, "analista": analista,
                      "hilo": tr, "flip": flip, "agree": agree})
    out = {
        "gerado_em": datetime.datetime.now().astimezone().isoformat(timespec="minutes"),
        "period": PERIOD,
        "resumo": {"concordam": ok, "total": tot,
                   "pct": round(ok / tot * 100) if tot else None},
        "itens": items,
    }
    dest = os.path.join(HERE, "web", "v2", "hilo.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    json.dump(out, open(dest, "w"), ensure_ascii=False, indent=2)
    print(f"hilo.json -> {dest} | concordância {ok}/{tot} "
          f"({out['resumo']['pct']}%) period={PERIOD}")


if __name__ == "__main__":
    main()
