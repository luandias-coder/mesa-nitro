#!/usr/bin/env python3
"""Converte VTT de auto-legenda do YouTube (janela rolante) p/ transcript M:SS<tab>texto."""
import re, sys

def parse(vtt_path):
    txt = open(vtt_path, encoding="utf-8").read()
    blocks = re.split(r"\n\n+", txt)
    cues = []
    for b in blocks:
        m = re.search(r"(\d+):(\d+):(\d+)\.\d+\s*-->", b)
        if not m: continue
        h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
        secs = h*3600 + mi*60 + s
        # linhas de texto (apos a linha de tempo); remove tags inline e align
        lines = []
        for ln in b.splitlines():
            if "-->" in ln or ln.strip()=="" or ln.strip()=="WEBVTT": continue
            ln = re.sub(r"<[^>]+>", "", ln)          # tira <00:..><c> tags
            ln = ln.strip()
            if ln: lines.append(ln)
        if lines:
            cues.append((secs, lines))
    return cues

def build(cues):
    out = []          # (secs, line)
    seen_last = None
    for secs, lines in cues:
        # a ultima linha do cue costuma ser o texto "novo" revelado
        for ln in lines:
            if ln == seen_last:    # dedup consecutivo
                continue
            # evita reanexar linha ja emitida recentemente
            if out and ln == out[-1][1]:
                continue
            out.append((secs, ln))
            seen_last = ln
    # segunda passada: remove linhas que sao prefixo da seguinte (rolagem parcial)
    cleaned = []
    for i,(secs,ln) in enumerate(out):
        if i+1 < len(out) and out[i+1][1].startswith(ln) and out[i+1][1]!=ln:
            continue
        if cleaned and cleaned[-1][1]==ln:
            continue
        cleaned.append((secs,ln))
    return cleaned

def fmt(secs):
    return f"{secs//60}:{secs%60:02d}"

if __name__=="__main__":
    vtt, out = sys.argv[1], sys.argv[2]
    cues = parse(vtt)
    rows = build(cues)
    with open(out,"w",encoding="utf-8") as f:
        for secs,ln in rows:
            f.write(f"{fmt(secs)}\t{ln}\n")
    print(f"OK {out} | cues={len(cues)} linhas={len(rows)}")
