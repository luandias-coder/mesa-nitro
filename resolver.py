#!/usr/bin/env python3
"""
Resolver da Sala Nitro: sinais parseados (código falado) -> TICKER REAL da opção B3.

Fonte da grade: opcoes.net.br (endpoint JSON público, sem auth).
Estratégia:
  1) Normaliza a raiz da opção pelo tickers.yaml (option_root) -> "Semin" vira CMIN, "Lin" vira LREN.
  2) Extrai a LETRA da série (A-X) e o número do código falado.
  3) Descobre o vencimento mensal correto (letra -> mês) na lista real de vencimentos do ativo.
  4) Baixa a grade daquele vencimento e CONFIRMA o ticker exato -> pega strike real, último e delta.
  5) Fallback: se não bater exato, casa pelo prêmio (último ~ preço cantado) dentro do tipo+vencimento.

Saída: signals_resolved_<data>.json (sinais enriquecidos com codigo_resolvido/strike_real)
       + tabela no terminal com a coluna TICKER REAL pra copiar e colar no home broker.

Uso:
    .venv/bin/python resolver.py signals_parsed_05-06.json
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

# letra da série -> (tipo, mês)
_CALL = "ABCDEFGHIJKL"   # jan..dez
_PUT = "MNOPQRSTUVWX"    # jan..dez
SERIE = {}
for i, ch in enumerate(_CALL):
    SERIE[ch] = ("CALL", i + 1)
for i, ch in enumerate(_PUT):
    SERIE[ch] = ("PUT", i + 1)


def load_roots():
    data = yaml.safe_load((HERE / "tickers.yaml").read_text())
    roots = {}
    for bloco in ("ativos", "grupo_csn", "auxiliares"):
        for a in data.get(bloco, []) or []:
            roots[a["underlying"]] = a.get("option_root", a["underlying"][:4])
    return roots


_chain_cache = {}
_venc_cache = {}


def get_vencimentos(acao):
    if acao in _venc_cache:
        return _venc_cache[acao]
    url = f"https://opcoes.net.br/listaopcoes/completa?idLista=ML&idAcao={acao}&listarVencimentos=true&cotacoes=true"
    d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25))
    vs = d["data"]["vencimentos"]
    _venc_cache[acao] = vs
    return vs


def get_chain(acao, venc):
    key = (acao, venc)
    if key in _chain_cache:
        return _chain_cache[key]
    url = f"https://opcoes.net.br/listaopcoes/completa?idLista=ML&idAcao={acao}&cotacoes=true&vencimentos={venc}"
    d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25))
    rows = d["data"]["cotacoesOpcoes"]
    # normaliza p/ dicts úteis
    out = []
    for r in rows:
        out.append({
            "ticker": r[0].split("_")[0],
            "tipo": r[2],
            "strike": r[5],
            "ultimo": r[8],
            "delta": r[13] if isinstance(r[13], (int, float)) else None,
        })
    _chain_cache[key] = out
    return out


def parse_codigo(codigo):
    """Extrai (letra, numero) do código falado. Ex 'CSNA S610'->('S','610'); 'Lin F148'->('F','148')."""
    s = re.sub(r"\s+", "", (codigo or "").upper())
    m = re.search(r"([A-X])(\d+[A-Z]?)$", s)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def monthly_venc(acao, mes, ano):
    """Acha o vencimento MENSAL (m=1) do ativo p/ mês/ano alvo."""
    for v in get_vencimentos(acao):
        val = v["value"]  # YYYY-MM-DD
        y, mth, _ = val.split("-")
        if int(y) == ano and int(mth) == mes and v.get("dataAttributes", {}).get("m") == "1":
            return val
    return None


def resolve_one(acao, codigo_falado, tipo_hint, preco, ano_base, roots, strike_hint=None):
    root = roots.get(acao, acao[:4])
    letra, num = parse_codigo(codigo_falado)
    if not letra:
        return {"codigo_resolvido": None, "metodo": "sem_codigo", "confianca": "baixa"}
    tipo, mes = SERIE[letra]
    venc = monthly_venc(acao, mes, ano_base)
    if not venc:
        return {"codigo_resolvido": None, "metodo": "venc_nao_encontrado", "confianca": "baixa",
                "tipo": tipo, "mes": mes}
    chain = get_chain(acao, venc)
    cand = f"{root}{letra}{num}"
    # 1) match exato (código falado == ticker real)
    for o in chain:
        if o["ticker"] == cand:
            return {"codigo_resolvido": o["ticker"], "strike_real": o["strike"],
                    "ultimo_hoje": o["ultimo"], "delta_hoje": o["delta"], "vencimento": venc,
                    "metodo": "exato", "confianca": "alta"}
    cands = [o for o in chain if o["tipo"] == tipo and isinstance(o["strike"], (int, float))]
    # 2) vira-mão: mesma linha de strike da perna fechada (mais confiável que prêmio)
    if strike_hint and cands:
        best = min(cands, key=lambda o: abs(o["strike"] - strike_hint))
        if abs(best["strike"] - strike_hint) <= 0.5:
            return {"codigo_resolvido": best["ticker"], "strike_real": best["strike"],
                    "ultimo_hoje": best["ultimo"], "delta_hoje": best["delta"], "vencimento": venc,
                    "metodo": "mesmo_strike", "confianca": "media",
                    "nota": f"sem match exato p/ {cand}; casado no strike ~{strike_hint} da perna fechada"}
    # 3) fallback por prêmio dentro do tipo
    cands_p = [o for o in cands if isinstance(o["ultimo"], (int, float))]
    if preco and cands_p:
        best = min(cands_p, key=lambda o: abs(o["ultimo"] - preco))
        return {"codigo_resolvido": best["ticker"], "strike_real": best["strike"],
                "ultimo_hoje": best["ultimo"], "delta_hoje": best["delta"], "vencimento": venc,
                "metodo": "aprox_premio", "confianca": "media",
                "nota": f"sem match exato p/ {cand}; casado pelo prêmio ~R${preco} (CONFIRMAR)"}
    return {"codigo_resolvido": None, "candidato": cand, "vencimento": venc,
            "metodo": "nao_encontrado", "confianca": "baixa"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("signals", help="arquivo signals_parsed_*.json")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    spath = Path(args.signals)
    if not spath.is_absolute():
        spath = HERE / spath
    data = json.loads(spath.read_text())
    roots = load_roots()
    ano_base = int((data.get("data") or "2026-01-01")[:4])

    def enrich(item, codigo_key, tipo_key, preco_key, strike_hint=None):
        acao = item.get("underlying")
        if not acao or acao.startswith("?"):
            item["resolucao"] = {"codigo_resolvido": None, "metodo": "underlying_incerto", "confianca": "baixa"}
            return
        try:
            r = resolve_one(acao, item.get(codigo_key), item.get(tipo_key), item.get(preco_key),
                            ano_base, roots, strike_hint=strike_hint)
        except Exception as e:
            r = {"codigo_resolvido": None, "metodo": "erro_grade", "confianca": "baixa", "erro": str(e)[:120]}
        item["resolucao"] = r
        if r.get("codigo_resolvido"):
            item["codigo_resolvido"] = r["codigo_resolvido"]

    for s in data.get("sinais", []):
        # vira-mão: resolve a perna fechada antes p/ usar o strike dela como pista
        hint = None
        rel = s.get("relacionada") or {}
        if rel.get("codigo_falado") and not str(s.get("underlying", "")).startswith("?"):
            try:
                rr = resolve_one(s["underlying"], rel["codigo_falado"], None, rel.get("preco"),
                                 ano_base, roots)
                rel["resolucao"] = rr
                hint = rr.get("strike_real")
            except Exception:
                pass
        enrich(s, "codigo_falado", "tipo_opcao", "preco_sugerido", strike_hint=hint)
    for p in data.get("posicoes_em_aberto", []):
        enrich(p, "codigo_falado", "tipo", "preco")

    outpath = Path(args.out) if args.out else (HERE / f"signals_resolved_{data.get('data','x')}.json")
    outpath.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    # tabela
    print(f"\n=== {data.get('data')} | {data.get('analista','')} ===")
    print(f"{'TS':>6}  {'AÇÃO':<12} {'ATIVO':<7} {'FALADO':<13} -> {'TICKER REAL':<12} {'STRIKE':>8}  CONF")
    print("-" * 78)
    for s in data.get("sinais", []):
        r = s.get("resolucao", {})
        print(f"{s.get('timestamp',''):>6}  {s.get('acao',''):<12} {s.get('underlying',''):<7} "
              f"{s.get('codigo_falado',''):<13} -> {str(r.get('codigo_resolvido') or '??'):<12} "
              f"{str(r.get('strike_real','')):>8}  {r.get('confianca','')}")
    print(f"\n-> {outpath.name}")


if __name__ == "__main__":
    main()
