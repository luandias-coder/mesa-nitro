#!/usr/bin/env python3
"""Carrega lives/sinais/posições no Supabase via PostgREST (secret key).
Env: SUPABASE_URL (https://<ref>.supabase.co) e SUPABASE_SECRET (sb_secret_...).
Idempotente: upsert em lives; replace (delete+insert) em sinais e posicoes_analista.
NÃO toca em execucoes_usuario (dados do usuário).
"""
import json, glob, os, urllib.request, urllib.parse
from dashboard import collect, load_gabarito  # reaproveita o mesmo pipeline de dados

URL = os.environ["SUPABASE_URL"].rstrip("/")
SEC = os.environ["SUPABASE_SECRET"]
H = {"apikey": SEC, "Authorization": f"Bearer {SEC}", "Content-Type": "application/json"}


def req(method, path, body=None, prefer=None):
    h = dict(H)
    if prefer:
        h["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(URL + path, data=data, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return resp.status, resp.read().decode()


def main():
    docs = [json.load(open(f)) for f in sorted(glob.glob("signals_resolved_*.json"))]
    videos = json.load(open("videos.json")) if os.path.exists("videos.json") else {}
    data = collect(docs, load_gabarito())

    # lives (a partir de cada doc)
    lives = [{"data": d.get("data"), "analista": d.get("analista"),
              "video_id": videos.get(d.get("data"))} for d in docs]
    req("POST", "/rest/v1/lives", lives, prefer="resolution=merge-duplicates")
    print("lives:", len(lives))

    # sinais — replace tudo (histórico completo)
    req("DELETE", "/rest/v1/sinais?id=gt.0")
    sinais = []
    for h in data["history"]:
        sinais.append({k: h.get(k) for k in ("data", "ts", "acao", "underlying", "tipo",
                       "codigo", "strike", "vencimento", "preco", "conf", "link")})
        sinais[-1]["preco_limite"] = sinais[-1].pop("preco")
        sinais[-1]["vencimento"] = (h.get("venc") or None)
    # chunked insert
    for i in range(0, len(sinais), 200):
        req("POST", "/rest/v1/sinais", sinais[i:i+200])
    print("sinais:", len(sinais))

    # posicoes_analista — replace
    req("DELETE", "/rest/v1/posicoes_analista?id=gt.0")
    pos = [{"underlying": p["underlying"], "tipo": p.get("tipo"), "codigo": p.get("codigo"),
            "strike": p.get("strike"), "vencimento": p.get("venc"), "entry": p.get("entry"),
            "atual": p.get("atual"), "conf": p.get("conf"), "metodo": p.get("metodo"),
            "pnl_real": p.get("pnl_real")} for p in data["portfolio"]]
    req("POST", "/rest/v1/posicoes_analista", pos)
    print("posicoes:", len(pos))
    print("OK -> Supabase carregado")


if __name__ == "__main__":
    main()
