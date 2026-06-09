#!/usr/bin/env python3
"""
Parser da Sala Nitro: transcript bruto (legenda YT) -> sinais estruturados (JSON).

Usa a API da Anthropic com tool-use forçado (structured output) e o registro
canônico de tickers (tickers.yaml) para fazer match no universo FECHADO de ativos.

Uso:
    .venv/bin/python parser.py transcript_05-06.txt
    .venv/bin/python parser.py transcript_05-06.txt --data 2026-06-05 --out signals_05-06.json
    .venv/bin/python parser.py transcript_05-06.txt --model claude-opus-4-8

API key: lê de ANTHROPIC_API_KEY (env) ou de um arquivo .env ao lado do script.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import yaml
from anthropic import Anthropic

HERE = Path(__file__).resolve().parent
DEFAULT_MODEL = "claude-sonnet-4-6"


def load_env():
    """Carrega .env (KEY=VALUE) se a env var não estiver setada."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    envf = HERE / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_registry():
    """Lê tickers.yaml e monta o texto do universo (underlying + aliases) p/ o prompt."""
    data = yaml.safe_load((HERE / "tickers.yaml").read_text())
    linhas = []
    universo = []
    for bloco in ("ativos", "grupo_csn", "auxiliares"):
        for a in data.get(bloco, []) or []:
            u = a["underlying"]
            universo.append(u)
            aliases = ", ".join(a.get("aliases", []))
            root = a.get("option_root", "")
            linhas.append(f"  {u} ({a['nome']}) | opção:{root} | legenda canta: {aliases}")
    return "\n".join(linhas), universo


SCHEMA = {
    "type": "object",
    "properties": {
        "data": {"type": "string", "description": "Data da live YYYY-MM-DD"},
        "analista": {"type": "string"},
        "resumo_analista": {"type": "string", "description": "Frase-resumo dita pelo analista, ex: '3 viradas + 1 ajuste'"},
        "vencimento_padrao": {"type": "string", "description": "Vencimento mensal usado no dia, YYYY-MM-DD se citado"},
        "sinais": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "timestamp": {"type": "string", "description": "Marca de tempo (mm:ss ou h:mm:ss) da linha do transcript onde o analista CRAVA esta operação. Copie verbatim do início da linha."},
                    "underlying": {"type": "string", "description": "Ticker DOS 21 do registro. Use '???' se não casar com confiança e registre em avisos."},
                    "acao": {"type": "string", "enum": ["entrada", "saida", "ajuste_delta", "manter"]},
                    "tipo_opcao": {"type": "string", "enum": ["CALL", "PUT"]},
                    "vencimento": {"type": "string"},
                    "strike": {"type": ["number", "null"]},
                    "codigo_falado": {"type": "string", "description": "Código da opção como cantado na live, ex 'CSN S610'"},
                    "preco_sugerido": {"type": ["number", "null"]},
                    "delta": {"type": ["number", "null"]},
                    "relacionada": {
                        "type": ["object", "null"],
                        "description": "Posição antiga a encerrar no mesmo movimento (vira-mão).",
                        "properties": {
                            "acao": {"type": "string"},
                            "codigo_falado": {"type": "string"},
                            "preco": {"type": ["number", "null"]},
                        },
                    },
                    "motivo": {"type": "string"},
                    "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
                    "trecho": {"type": "string", "description": "Trecho curto do transcript que embasa o sinal"},
                },
                "required": ["underlying", "acao", "tipo_opcao", "codigo_falado", "confianca"],
            },
        },
        "posicoes_em_aberto": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "timestamp": {"type": "string", "description": "Marca de tempo (mm:ss) da linha onde o preço/posição é citado, verbatim."},
                    "codigo_falado": {"type": "string"},
                    "underlying": {"type": "string"},
                    "preco": {"type": ["number", "null"]},
                    "tipo": {"type": "string", "enum": ["CALL", "PUT"]},
                    "nota": {"type": "string"},
                },
                "required": ["codigo_falado", "underlying"],
            },
        },
        "avisos": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ambiguidades, tickers incertos, confusões cantadas ao vivo (ex: 'BOVA S52 corrigido p/ G52')",
        },
    },
    "required": ["data", "sinais"],
}

SYSTEM = """Você é um parser especialista da "Sala Nitro", live diária de análise de mercado da B3.
Sua tarefa: ler a TRANSCRIÇÃO AUTOMÁTICA (legenda do YouTube, que ERRA nomes falados) e extrair os
sinais operacionais em estrutura rígida via a ferramenta emitir_sinais.

METODOLOGIA NITRO (contexto):
- Indicador tipo High-Low. Verde = início de tendência de ALTA -> comprar CALL. Vermelho = baixa -> comprar PUT.
- "Virada de tendência" = nova operação (acao=entrada). "Ajuste de delta" = trocar opção valorizada por
  outra na linha do dinheiro, mesmo vencimento (acao=ajuste_delta), só p/ quem já tinha a posição.
- PUT valoriza quando o ativo CAI. Regras: máx 1% por op, sempre ordem limitada, nunca preço médio.

UNIVERSO FECHADO — só existem estes ativos. Faça match do nome falado (mesmo mal transcrito) contra esta lista
usando os aliases. Se não casar com confiança, use underlying="???" e registre em avisos.
{registro}

CÓDIGO DE OPÇÃO B3 = <raiz_opcao><LETRA><strike>. A LETRA codifica mês + tipo:
  CALL: A=jan B=fev C=mar D=abr E=mai F=jun G=jul H=ago I=set J=out K=nov L=dez
  PUT : M=jan N=fev O=mar P=abr Q=mai R=jun S=jul T=ago U=set V=out W=nov X=dez
Use a letra do codigo_falado p/ inferir tipo_opcao e o mês de vencimento quando possível.
O strike exato NEM SEMPRE é decodificável do código — preencha strike só se tiver confiança; senão null.

TIMESTAMP: cada linha do transcript começa com a marca de tempo (mm:ss) do vídeo. Para CADA sinal e CADA
posição, preencha o campo timestamp com o tempo da linha onde aquilo é dito/cravado, copiado verbatim.
Isso permite ao usuário ir direto ao ponto do vídeo p/ validar ticker e preço.

REGRAS DE EXTRAÇÃO:
- Extraia operações NOVAS do dia (entrada), ajustes de delta, saídas e posições em aberto citadas.
- Para vira-mão (encerrar call e montar put), preencha o campo relacionada com a perna que sai.
- confianca: "alta" só quando ticker + tipo + código estão claros; "media"/"baixa" quando a legenda embolou.
- Registre em avisos toda confusão (códigos cantados errado e corrigidos, tickers ambíguos).
- NÃO invente. Se o analista não disse o preço/strike/delta, deixe null.
- Responda SOMENTE chamando a ferramenta emitir_sinais."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript", help="caminho do transcript .txt")
    ap.add_argument("--data", default="", help="data da live YYYY-MM-DD (ajuda o modelo)")
    ap.add_argument("--out", default="", help="arquivo de saída .json")
    ap.add_argument("--model", default=os.environ.get("PARSER_MODEL", DEFAULT_MODEL))
    args = ap.parse_args()

    load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ERRO: ANTHROPIC_API_KEY ausente. Defina a env var ou crie um arquivo .env com ANTHROPIC_API_KEY=...")

    tpath = Path(args.transcript)
    if not tpath.is_absolute():
        tpath = HERE / tpath
    transcript = tpath.read_text(errors="ignore")

    registro, _universo = load_registry()
    system = SYSTEM.format(registro=registro)

    user = f"Data da live: {args.data or 'inferir do conteúdo'}\n\nTRANSCRIÇÃO:\n{transcript}"

    client = Anthropic()
    print(f"[parser] modelo={args.model} transcript={tpath.name} ({len(transcript)} chars)", file=sys.stderr)

    resp = client.messages.create(
        model=args.model,
        max_tokens=8000,
        system=system,
        tools=[{
            "name": "emitir_sinais",
            "description": "Emite os sinais estruturados extraídos da live.",
            "input_schema": SCHEMA,
        }],
        tool_choice={"type": "tool", "name": "emitir_sinais"},
        messages=[{"role": "user", "content": user}],
    )

    out = None
    for block in resp.content:
        if block.type == "tool_use" and block.name == "emitir_sinais":
            out = block.input
            break
    if out is None:
        sys.exit("ERRO: modelo não retornou tool_use emitir_sinais.")

    # metadados + placeholder do resolver
    out.setdefault("fonte", "live_youtube")
    if args.data and not out.get("data"):
        out["data"] = args.data
    for s in out.get("sinais", []):
        s.setdefault("codigo_resolvido", None)  # preenchido depois pelo resolver (grade B3)

    outpath = Path(args.out) if args.out else (HERE / f"signals_parsed_{out.get('data','semdata')}.json")
    outpath.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    u = resp.usage
    print(f"[parser] OK -> {outpath.name} | {len(out.get('sinais',[]))} sinais | tokens in={u.input_tokens} out={u.output_tokens}", file=sys.stderr)
    print(outpath)


if __name__ == "__main__":
    main()
