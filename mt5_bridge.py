#!/usr/bin/env python3
"""Bridge MT5 <-> Supabase (roda no VPS Windows).

Fluxo (com GATE HUMANO):
  dashboard cria ordem status='pendente' -> humano APROVA (status='aprovada')
  -> este bridge pega as 'aprovada', valida com order_check, e SÓ ENVIA se AUTO_SEND=1
  -> grava ticket/preço/resultado de volta no Supabase e marca 'executada'/'erro'.

Segurança:
  - NUNCA envia ordem a mercado: usa ordem LIMITADA (preco_limite obrigatório p/ enviar).
  - AUTO_SEND default '0' => roda em modo DRY-RUN (só order_check, não envia nada).
  - MT5_CONTA ('demo'|'real') casa com o campo `conta` da ordem; ordens de conta != da sessão são puladas.
  - Conexão preferida: ATTACH a um terminal já logado (mt5.initialize() sem credenciais).
    Fallback: initialize com credenciais (login/server) — menos estável headless.

Env: MT5_PATH, MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_CONTA, AUTO_SEND,
     SUPABASE_URL, SUPABASE_SECRET.
"""
import os, time, json, urllib.request

SB = os.environ["SUPABASE_URL"].rstrip("/")
SEC = os.environ["SUPABASE_SECRET"]
CONTA = os.environ.get("MT5_CONTA", "demo")
AUTO_SEND = os.environ.get("AUTO_SEND", "0") == "1"
PATH = os.environ.get("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
H = {"apikey": SEC, "Authorization": f"Bearer {SEC}", "Content-Type": "application/json"}


def sb(method, path, body=None, prefer=None):
    h = dict(H)
    if prefer:
        h["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(SB + path, data=data, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=30) as resp:
        t = resp.read().decode()
        return json.loads(t) if t else []


def connect():
    import MetaTrader5 as mt5
    # 1) tenta anexar a um terminal JÁ logado (mais estável)
    if mt5.initialize(path=PATH, timeout=60000):
        ai = mt5.account_info()
        if ai and (not os.environ.get("MT5_LOGIN") or str(ai.login) == os.environ.get("MT5_LOGIN")):
            return mt5
        mt5.shutdown()
    # 2) fallback: login explícito
    login = int(os.environ["MT5_LOGIN"]); pw = os.environ["MT5_PASSWORD"]; srv = os.environ["MT5_SERVER"]
    if not mt5.initialize(path=PATH, login=login, password=pw, server=srv, timeout=60000):
        raise SystemExit(f"MT5 initialize falhou: {mt5.last_error()}")
    return mt5


def executar(mt5, o):
    """Valida (order_check) e, se AUTO_SEND, envia ordem LIMITADA. Retorna (status, ticket, preco, msg)."""
    sym = o["codigo"]
    if not mt5.symbol_select(sym, True):
        return "erro", None, None, f"símbolo {sym} indisponível"
    if o.get("preco_limite") in (None, ""):
        return "erro", None, None, "sem preço limite (não enviamos a mercado)"
    tipo = mt5.ORDER_TYPE_BUY_LIMIT if o["acao"] == "comprar" else mt5.ORDER_TYPE_SELL_LIMIT
    req = {
        "action": mt5.TRADE_ACTION_PENDING, "symbol": sym, "volume": float(o["volume"]),
        "type": tipo, "price": float(o["preco_limite"]), "type_time": mt5.ORDER_TIME_DAY,
        "type_filling": mt5.ORDER_FILLING_RETURN, "comment": "mesa-nitro",
    }
    chk = mt5.order_check(req)
    if chk is None or chk.retcode != 0:
        return "erro", None, None, f"order_check reprovou: {getattr(chk,'comment','?')} ({getattr(chk,'retcode','?')})"
    if not AUTO_SEND:
        return "validada_dry_run", None, None, f"order_check OK (margem ok) — AUTO_SEND desligado, nada enviado"
    res = mt5.order_send(req)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        return "erro", None, None, f"order_send retcode={getattr(res,'retcode','?')} {getattr(res,'comment','')}"
    return "executada", res.order, res.price, "ok"


def loop_once(mt5):
    ordens = sb("GET", f"/rest/v1/ordens?status=eq.aprovada&conta=eq.{CONTA}&select=*")
    for o in ordens:
        status, ticket, preco, msg = executar(mt5, o)
        sb("PATCH", f"/rest/v1/ordens?id=eq.{o['id']}", {
            "status": status, "ticket": ticket, "preco_exec": preco,
            "resultado": msg, "atualizado_em": "now()"})
        print(f"ordem {o['id']} {o['codigo']} -> {status}: {msg}")
    return len(ordens)


def main():
    mt5 = connect()
    ai = mt5.account_info()
    print(f"CONECTADO conta={ai.login} server={ai.server} saldo={ai.balance:.2f} {ai.currency} "
          f"| MT5_CONTA={CONTA} AUTO_SEND={AUTO_SEND}")
    try:
        while True:
            loop_once(mt5)
            time.sleep(int(os.environ.get("POLL_SEG", "15")))
    except KeyboardInterrupt:
        pass
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
