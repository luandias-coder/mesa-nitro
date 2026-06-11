#!/usr/bin/env python3
"""Feed de preço das opções via opcoes.net.br (último negociado real do mercado).
Atualiza sinais.preco_atual e posicoes_analista.atual no Supabase para TODOS os
códigos com posição/sinal — não só a fila do dia. Substitui o pump do MT5, que
estoura em opção ilíquida (ex: WEG mostrava 0,90 vs 1,22 real).

Rodar durante o pregão (ex: a cada ~10min) + 1x no fechamento. Env: SUPABASE_URL, SUPABASE_SECRET.
"""
import os, json, urllib.request

SB = os.environ["SUPABASE_URL"].rstrip("/")
SEC = os.environ["SUPABASE_SECRET"]
H = {"apikey": SEC, "Authorization": f"Bearer {SEC}", "Content-Type": "application/json"}
UA = {"User-Agent": "Mozilla/5.0"}


def sb(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(SB + path, data=data, headers=H, method=method)
    with urllib.request.urlopen(r, timeout=30) as resp:
        t = resp.read().decode()
        return json.loads(t) if t else []


def opcoes_ultimos(acao):
    """codigo -> último negociado, varrendo todos os vencimentos do ativo."""
    base = f"https://opcoes.net.br/listaopcoes/completa?idLista=ML&idAcao={acao}"
    d = json.load(urllib.request.urlopen(
        urllib.request.Request(base + "&listarVencimentos=true&cotacoes=true", headers=UA), timeout=25))
    cols = [c["name"] for c in d["data"]["columns"]]
    iU = cols.index("ultimo")
    out = {}

    def collect(dd):
        for r in dd["data"]["cotacoesOpcoes"]:
            c = str(r[0]).split("_")[0].upper()
            u = r[iU]
            if u not in (None, ""):
                out[c] = u

    collect(d)
    for v in [x["value"] for x in d["data"]["vencimentos"]]:
        try:
            dd = json.load(urllib.request.urlopen(
                urllib.request.Request(base + f"&cotacoes=true&vencimentos={v}", headers=UA), timeout=25))
        except Exception:
            continue
        collect(dd)
    return out


def dentro_do_pregao():
    """True em dia útil entre ~10:00 e 17:20 BRT (cobre o fechamento). FORCE=1 ignora."""
    if os.environ.get("FORCE") == "1":
        return True
    import datetime, zoneinfo
    now = datetime.datetime.now(zoneinfo.ZoneInfo("America/Sao_Paulo"))
    if now.weekday() >= 5:
        return False
    h = now.hour + now.minute / 60
    return 10.0 <= h <= 17.34


def main():
    if not dentro_do_pregao():
        print("fora do pregão — pulando")
        return
    pos = sb("GET", "/rest/v1/posicoes_analista?select=codigo,underlying")
    sin = sb("GET", "/rest/v1/sinais?select=codigo,underlying,data&order=data.desc&limit=400")
    cu = {}
    for x in pos + sin:
        if x.get("codigo") and x.get("underlying"):
            cu.setdefault(x["codigo"], x["underlying"])
    under = {}
    for c, u in cu.items():
        under.setdefault(u, set()).add(c)

    n = 0
    for u, cods in under.items():
        try:
            ult = opcoes_ultimos(u)
        except Exception as e:
            print(f"  {u}: erro {e}")
            continue
        for c in cods:
            px = ult.get(c)
            if px is None:
                continue
            px = round(float(px), 2)
            sb("PATCH", f"/rest/v1/posicoes_analista?codigo=eq.{c}", {"atual": px})
            sb("PATCH", f"/rest/v1/sinais?codigo=eq.{c}", {"preco_atual": px})
            n += 1
            print(f"  {c} ({u}) -> {px}")
    print(f"OK {n} códigos atualizados via opcoes.net.br")


if __name__ == "__main__":
    main()
