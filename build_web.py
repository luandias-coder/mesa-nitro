#!/usr/bin/env python3
"""Gera web/index.html — cockpit que lê do Supabase ao vivo (deploy Vercel).
Reusa o TEMPLATE do dashboard.py, trocando: dados embutidos -> fetch Supabase;
localStorage -> tabela execucoes_usuario. A publishable key é segura no frontend.
"""
import os, re
from dashboard import TEMPLATE

SB_URL = os.environ.get("SUPABASE_URL", "https://mqcryomwdwnosoqfmyak.supabase.co")
SB_PUB = os.environ.get("SUPABASE_PUBLISHABLE", "sb_publishable_GozaOIA6rPwYFpgiOh60lg_OAmWvMCP")

# 1) bootstrap: troca "const DATA = ...; ... const save=...;" por loader Supabase
boot_old_start = "const DATA = /*__DATA__*/;"
boot_new = f"""const SB_URL="{SB_URL}", SB_KEY="{SB_PUB}";
const sbh={{apikey:SB_KEY,Authorization:"Bearer "+SB_KEY,"Content-Type":"application/json"}};
let DATA={{meta:{{}},today:[],portfolio:[],history:[]}};
let store={{}};
async function sbGet(p){{try{{const r=await fetch(SB_URL+"/rest/v1/"+p,{{headers:sbh}});return r.ok?await r.json():[];}}catch(e){{return [];}}}}
async function loadAll(){{
  const [lives,sin,pos,exe]=await Promise.all([
    sbGet("lives?select=*&order=data.asc"),
    sbGet("sinais?select=*&order=data.asc,ts.asc"),
    sbGet("posicoes_analista?select=*"),
    sbGet("execucoes_usuario?select=*")]);
  const latest=lives.length?lives[lives.length-1]:{{}};
  const datasComOps=[...new Set(sin.map(s=>s.data))].sort();
  const filaData=datasComOps.length?datasComOps[datasComOps.length-1]:latest.data;
  DATA.meta={{data_latest:latest.data,fila_data:filaData,hoje_manutencao:(filaData!==latest.data),analista:latest.analista,lives:lives.length,n_pos:pos.length}};
  DATA.portfolio=pos.map(p=>({{underlying:p.underlying,tipo:p.tipo,codigo:p.codigo,strike:p.strike,venc:p.vencimento,entry:p.entry,atual:p.atual,conf:p.conf,metodo:p.metodo,pnl_real:p.pnl_real}}));
  DATA.history=sin.map(s=>({{data:s.data,ts:s.ts,acao:s.acao,underlying:s.underlying,tipo:s.tipo,codigo:s.codigo,strike:s.strike,venc:s.vencimento,preco:s.preco_limite,conf:s.conf,link:s.link}}));
  DATA.today=sin.filter(s=>s.data===filaData).map(s=>({{id:s.data+"__"+s.codigo+"__"+s.acao+"__"+s.ts,data:s.data,ts:s.ts,acao:s.acao,underlying:s.underlying,tipo:s.tipo,codigo:s.codigo,strike:s.strike,venc:s.vencimento,limite:s.preco_limite,atual:s.preco_atual,delta:s.delta,conf:s.conf,metodo:s.metodo,motivo:s.motivo,link:s.link,rel:s.rel_codigo?{{codigo:s.rel_codigo,preco:s.rel_preco}}:null}}));
  store={{}}; exe.forEach(e=>{{store[e.op_id]={{status:e.status,preco:e.preco_pago,qtd:e.qtd}};}});
}}
async function save(){{
  const find=id=>DATA.today.find(o=>o.id===id)||{{}};
  const rows=Object.entries(store).map(([op_id,v])=>{{const o=find(op_id);return {{op_id,status:v.status,preco_pago:(v.preco??null),qtd:(v.qtd??null),data:o.data,underlying:o.underlying,tipo:o.tipo,acao:o.acao,codigo:o.codigo}};}});
  try{{
    if(rows.length) await fetch(SB_URL+"/rest/v1/execucoes_usuario",{{method:"POST",headers:{{...sbh,Prefer:"resolution=merge-duplicates"}},body:JSON.stringify(rows)}});
    const keep=Object.keys(store); const all=await sbGet("execucoes_usuario?select=op_id");
    for(const r of all){{if(!keep.includes(r.op_id)) await fetch(SB_URL+"/rest/v1/execucoes_usuario?op_id=eq."+encodeURIComponent(r.op_id),{{method:"DELETE",headers:sbh}});}}
  }}catch(e){{console.warn("save falhou",e);}}
}}"""

t = TEMPLATE
# remove as 3 linhas antigas de bootstrap (DATA/LS/store/save)
t = t.replace(boot_old_start, boot_new)
t = t.replace("const LOTE=100, LS='mesa_nitro_exec_v1';\n", "const LOTE=100;\n")
t = t.replace("const store=JSON.parse(localStorage.getItem(LS)||'{}');\n", "")
t = t.replace("const save=()=>localStorage.setItem(LS,JSON.stringify(store));\n", "")
# init tail: carregar do Supabase antes de renderizar
old_init = "marketStatus();setInterval(marketStatus,60000);simOptions();setTipo('CALL');rerender();renderHist();"
new_init = "marketStatus();setInterval(marketStatus,60000);loadAll().then(()=>{document.getElementById('dlatest').textContent=brdate(DATA.meta.data_latest);simOptions();setTipo('CALL');rerender();renderHist();});"
t = t.replace(old_init, new_init)

t = t.replace("sua carteira salva neste navegador (localStorage)", "sua carteira no Supabase (nuvem)")
import json as _json
_cfg = _json.load(open("config.json")) if os.path.exists("config.json") else {"pool":12000,"caixa_pct":0.25,"peso_pct":0.05,"lote":100}
t = t.replace("/*__CFG__*/", _json.dumps(_cfg))
os.makedirs("web", exist_ok=True)
open("web/index.html", "w").write(t)
print("OK -> web/index.html", len(t), "bytes")
