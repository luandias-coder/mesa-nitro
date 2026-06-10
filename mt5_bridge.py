#!/usr/bin/env python3
"""Bridge MT5 <-> Supabase (roda no VPS Windows) com GATE HUMANO via Telegram + dashboard.

Fluxo:
  pipeline/dashboard cria ordem status='pendente'
  -> bridge notifica no Telegram com botoes [Executar][Pular] e marca 'notificada'
  -> humano toca (TG) ou clica (dash) -> status='aprovada' (ou 'cancelada')
  -> bridge pega 'aprovada', valida com order_check, e SO ENVIA se AUTO_SEND=1
  -> grava ticket/preco/resultado e marca 'executada'/'erro'/'validada_dry_run' + avisa no Telegram.

Seguranca:
  - NUNCA ordem a mercado: usa LIMITADA (preco_limite obrigatorio).
  - AUTO_SEND default '0' => DRY-RUN (so order_check).
  - Callback do Telegram SO aceito do chat_id do dono (TELEGRAM_CHAT_ID).
  - MT5_CONTA casa com o campo `conta`.

Env: MT5_PATH, MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_CONTA, AUTO_SEND,
     SUPABASE_URL, SUPABASE_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, POLL_SEG.
"""
import os, time, json, urllib.request, urllib.parse, ssl, certifi
_CTX = ssl.create_default_context(cafile=certifi.where())

SB = os.environ["SUPABASE_URL"].rstrip("/")
SEC = os.environ["SUPABASE_SECRET"]
CONTA = os.environ.get("MT5_CONTA", "demo")
AUTO_SEND = os.environ.get("AUTO_SEND", "0") == "1"
PATH = os.environ.get("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")
H = {"apikey": SEC, "Authorization": f"Bearer {SEC}", "Content-Type": "application/json"}

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
OFFSET_FILE = r"C:\tg_offset.txt"


def sb(method, path, body=None, prefer=None):
    h = dict(H)
    if prefer:
        h["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(SB + path, data=data, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=30, context=_CTX) as resp:
        t = resp.read().decode()
        return json.loads(t) if t else []


# ---------------- Telegram ----------------
def tg(method, payload):
    if not TG_TOKEN:
        return None
    data = json.dumps(payload).encode()
    r = urllib.request.Request(f"https://api.telegram.org/bot{TG_TOKEN}/{method}",
                               data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=20, context=_CTX) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"TG err {method}: {e}")
        return None


def _fmt_ordem(o):
    acao = "COMPRAR" if o.get("acao") == "comprar" else "VENDER"
    return (f"📈 <b>Aprovar ordem?</b>\n"
            f"<b>{o.get('codigo')}</b> · {acao}\n"
            f"Volume: <b>{o.get('volume')}</b> contrato(s)\n"
            f"Preço limite: <b>{o.get('preco_limite')}</b>\n"
            f"Conta: {o.get('conta')}")


def notificar_pendentes(mt5):
    """Valida o ticker no broker e, se existir, manda no Telegram com botoes ('notificada').
    Ticker que NAO existe no MT5 -> 'ticker_invalido' (nao aprovavel, flag p/ validacao manual)."""
    if not TG_TOKEN:
        return
    ords = sb("GET", f"/rest/v1/ordens?status=eq.pendente&conta=eq.{CONTA}&select=*")
    for o in ords:
        cod = o.get("codigo")
        # VALIDACAO: o ticker (legenda automatica erra) tem que existir de verdade no broker
        if not cod or not mt5.symbol_select(cod, True) or mt5.symbol_info(cod) is None:
            sb("PATCH", f"/rest/v1/ordens?id=eq.{o['id']}",
               {"status": "ticker_invalido", "resultado": f"ticker {cod} nao existe no broker - validar manualmente",
                "atualizado_em": "now()"})
            tg("sendMessage", {"chat_id": TG_CHAT, "parse_mode": "HTML",
                               "text": f"⚠️ Ordem <b>{cod}</b>: ticker NÃO existe no broker — pulada p/ validação manual (não aprovável)."})
            print(f"ticker_invalido ordem {o['id']} {cod}")
            continue
        kb = {"inline_keyboard": [[
            {"text": "✅ Executar", "callback_data": f"ap:{o['id']}"},
            {"text": "⏭️ Pular", "callback_data": f"pl:{o['id']}"},
        ]]}
        tg("sendMessage", {"chat_id": TG_CHAT, "text": _fmt_ordem(o),
                           "parse_mode": "HTML", "reply_markup": kb})
        sb("PATCH", f"/rest/v1/ordens?id=eq.{o['id']}",
           {"status": "notificada", "atualizado_em": "now()"})
        print(f"notificada ordem {o['id']} {o.get('codigo')}")


def _load_offset():
    try:
        return int(open(OFFSET_FILE).read().strip())
    except Exception:
        return None


def _save_offset(v):
    try:
        open(OFFSET_FILE, "w").write(str(v))
    except Exception as e:
        print(f"offset save err: {e}")


def processar_callbacks():
    """Le getUpdates e processa os toques nos botoes (Executar/Pular)."""
    if not TG_TOKEN:
        return
    payload = {"timeout": 0, "allowed_updates": ["callback_query"]}
    off = _load_offset()
    if off is not None:
        payload["offset"] = off
    res = tg("getUpdates", payload)
    if not res or not res.get("ok"):
        return
    last = off
    for upd in res["result"]:
        last = upd["update_id"] + 1
        cq = upd.get("callback_query")
        if not cq:
            continue
        frm = str(cq.get("from", {}).get("id"))
        data = cq.get("data", "")
        if frm != str(TG_CHAT):
            tg("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "não autorizado"})
            continue
        if ":" not in data:
            continue
        act, oid = data.split(":", 1)
        msg = cq.get("message", {})
        if act == "ap":
            sb("PATCH", f"/rest/v1/ordens?id=eq.{oid}&status=eq.notificada",
               {"status": "aprovada", "atualizado_em": "now()"})
            tg("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "✅ Aprovada — executando"})
            _edit(msg, "✅ <b>APROVADA</b> — enviando pra ponte")
        elif act == "pl":
            sb("PATCH", f"/rest/v1/ordens?id=eq.{oid}&status=eq.notificada",
               {"status": "cancelada", "atualizado_em": "now()"})
            tg("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "⏭️ Pulada"})
            _edit(msg, "⏭️ <b>PULADA</b>")
    if last is not None:
        _save_offset(last)


def _edit(msg, text):
    if not msg:
        return
    tg("editMessageText", {"chat_id": msg.get("chat", {}).get("id"),
                           "message_id": msg.get("message_id"), "text": text, "parse_mode": "HTML"})


# ---------------- MT5 ----------------
def connect():
    import MetaTrader5 as mt5
    if mt5.initialize(path=PATH, timeout=60000):
        ai = mt5.account_info()
        if ai and (not os.environ.get("MT5_LOGIN") or str(ai.login) == os.environ.get("MT5_LOGIN")):
            return mt5
        mt5.shutdown()
    login = int(os.environ["MT5_LOGIN"]); pw = os.environ["MT5_PASSWORD"]; srv = os.environ["MT5_SERVER"]
    if not mt5.initialize(path=PATH, login=login, password=pw, server=srv, timeout=60000):
        raise SystemExit(f"MT5 initialize falhou: {mt5.last_error()}")
    return mt5


def executar(mt5, o):
    sym = o["codigo"]
    if not mt5.symbol_select(sym, True):
        return "erro", None, None, f"simbolo {sym} indisponivel"
    if o.get("preco_limite") in (None, ""):
        return "erro", None, None, "sem preco limite (nao enviamos a mercado)"
    si = mt5.symbol_info(sym)
    if si is None:
        return "erro", None, None, f"sem symbol_info de {sym}"
    # 'volume' guardado = nº de CONTRATOS (lotes). MT5 quer em unidades do símbolo:
    # 1 lote = volume_min (100 p/ opções B3). Normaliza ao step e clampa a min/max.
    step = si.volume_step or 1.0
    lote = si.volume_min or step
    vol = round(float(o["volume"]) * lote / step) * step
    vol = max(si.volume_min, min(vol, si.volume_max))
    tipo = mt5.ORDER_TYPE_BUY_LIMIT if o["acao"] == "comprar" else mt5.ORDER_TYPE_SELL_LIMIT
    req = {
        "action": mt5.TRADE_ACTION_PENDING, "symbol": sym, "volume": float(vol),
        "type": tipo, "price": float(o["preco_limite"]), "type_time": mt5.ORDER_TIME_DAY,
        "type_filling": mt5.ORDER_FILLING_RETURN, "comment": "mesa-nitro",
    }
    MARKET_CLOSED = 10018  # TRADE_RETCODE_MARKET_CLOSED — mercado fechado, enfileira p/ abertura
    chk = mt5.order_check(req)
    if chk is not None and chk.retcode == MARKET_CLOSED:
        return "fila_abertura", None, None, "mercado fechado - na fila p/ executar na abertura"
    if chk is None or chk.retcode != 0:
        return "erro", None, None, f"order_check reprovou: {getattr(chk,'comment','?')} ({getattr(chk,'retcode','?')})"
    if not AUTO_SEND:
        return "validada_dry_run", None, None, "order_check OK (margem ok) - AUTO_SEND desligado, nada enviado"
    res = mt5.order_send(req)
    if res is not None and res.retcode == MARKET_CLOSED:
        return "fila_abertura", None, None, "mercado fechado - na fila p/ executar na abertura"
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        return "erro", None, None, f"order_send retcode={getattr(res,'retcode','?')} {getattr(res,'comment','')}"
    return "executada", res.order, res.price, "ok"


PRICE_SEG = int(os.environ.get("PRICE_SEG", "60"))
_next_price = [0.0]


def atualizar_precos(mt5):
    """Bomba de preço LIVE: pega tick da MT5 dos tickers da fila atual e escreve
    sinais.preco_atual no Supabase (dash faz poll e recalcula 'Ainda dá')."""
    sinais = sb("GET", "/rest/v1/sinais?select=data,codigo&order=data.desc&limit=300")
    if not sinais:
        return
    fila = sinais[0]["data"]
    cods = sorted({s["codigo"] for s in sinais if s.get("data") == fila and s.get("codigo")})
    n = 0
    for c in cods:
        if not mt5.symbol_select(c, True):
            continue
        t = mt5.symbol_info_tick(c)
        if not t:
            continue
        px = t.last if t.last else (round((t.bid + t.ask) / 2, 2) if (t.bid and t.ask) else None)
        if px:
            sb("PATCH", f"/rest/v1/sinais?data=eq.{fila}&codigo=eq.{c}",
               {"preco_atual": round(float(px), 2)})
            n += 1
    if n:
        print(f"precos live atualizados: {n}/{len(cods)} (fila {fila})")


def loop_once(mt5):
    processar_callbacks()          # 1) toques nos botoes (notificada -> aprovada/cancelada)
    notificar_pendentes(mt5)       # 2) valida ticker + avisa novas pendentes
    if time.time() >= _next_price[0]:   # 2.5) bomba de preço live (a cada PRICE_SEG)
        try:
            atualizar_precos(mt5)
        except Exception as e:
            print(f"preco err: {e}")
        _next_price[0] = time.time() + PRICE_SEG
    # 3) executa aprovadas E re-tenta as que estão na fila de abertura (mercado fechado)
    ordens = sb("GET", f"/rest/v1/ordens?status=in.(aprovada,fila_abertura)&conta=eq.{CONTA}&select=*")
    for o in ordens:
        status, ticket, preco, msg = executar(mt5, o)
        if status == o["status"]:
            continue               # ainda na fila (mercado fechado) — não re-notifica/spama
        sb("PATCH", f"/rest/v1/ordens?id=eq.{o['id']}", {
            "status": status, "ticket": ticket, "preco_exec": preco,
            "resultado": msg, "atualizado_em": "now()"})
        print(f"ordem {o['id']} {o['codigo']} -> {status}: {msg}")
        emoji = {"executada": "✅", "erro": "❌", "validada_dry_run": "🔎", "fila_abertura": "📅"}.get(status, "")
        extra = " — executa na abertura do pregão" if status == "fila_abertura" else ""
        tg("sendMessage", {"chat_id": TG_CHAT, "parse_mode": "HTML",
                           "text": f"{emoji} Ordem <b>{o['codigo']}</b>: <b>{status}</b>{extra}\n{msg}"})
    return len(ordens)


def main():
    mt5 = connect()
    ai = mt5.account_info()
    print(f"CONECTADO conta={ai.login} server={ai.server} saldo={ai.balance:.2f} {ai.currency} "
          f"| MT5_CONTA={CONTA} AUTO_SEND={AUTO_SEND} TG={'on' if TG_TOKEN else 'off'}")
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
