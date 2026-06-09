# 📊 Resumo Estruturado — Sala Nitro (Fechamento de Mercado)

**Data:** 05/06 (sexta-feira) · 16:30
**Analista:** Caio
**Metodologia:** Indicador "Nitro" (tipo High-Low / média das máximas e mínimas). Verde = início de tendência de alta → comprar **CALLs**. Vermelho = início de tendência de baixa → comprar **PUTs**.
**Regras citadas:** gerenciamento de risco inegociável, máx. 1% do patrimônio por operação; sempre ordem limitada (nunca a mercado); entrar em TODAS as operações novas (viradas de tendência); ajustes de delta são obrigatórios só para quem já está na operação antiga; vencimento usado = mensal tradicional acima de 20 dias úteis (julho/17).

---

## 🟢🔴 Mapa de Tendências do Dia (ativos monitorados)

| Ativo | Tendência atual | Movimento no dia | Observação |
|---|---|---|---|
| **BBSE3** (Bif 3) | 🔴 Baixa | +3,63% | Sobe no dia mas segue em baixa |
| **BRAP4** (Bradespar) | 🔴 Baixa | — | Entrou em baixa na quarta (pré-feriado); puts já compradas |
| **PRIO3 / Brava?** ("Brave 3") | 🟢 Alta | +1,4% | Petroleira em alta |
| **BRKM5** (Braskem) | 🔴 Baixa | -6% | Puts provavelmente atingiram 100% de lucro → ajuste de delta |
| **CMIN3** (CSN Mineração / "Semin") | 🔴 **VIRANDO p/ baixa** | -2,89% | **Virada de tendência hoje** |
| **CGNA / Cogna** (COGN3) | 🔴 Baixa | — | Segue em baixa |
| **CSAN3** (Cosan) | 🔴 Baixa | — | Segue em baixa |
| **CSNA3** (CSN) | 🔴 **VIRANDO p/ baixa** | -10% | **Virada de tendência hoje**; ativo lateralizado |
| **CYRE3** (Cyrela / "Cirela") | 🔴 Baixa | — | — |
| **EMBR3 / "Braer"** (Embraer) | 🔴 Baixa | +5% | Quase reverteu p/ alta hoje, mas segue baixa |
| **LREN3** (Lojas Renner) | 🔴 **VIRANDO p/ baixa** | — | **Virou no leilão (terça/quarta)**; operação feita perto do fechamento |
| **MRFG3 / BRFS3** ("MBRF3") | 🔴 Baixa | — | — |
| **MGLU3** (Magalu) | 🔴 Baixa | +2% | — |
| **MRVE3** (MRV) | 🔴 Baixa | — | — |
| **PETR4** (Petrobras) | 🔴 Baixa | — | — |
| **PRIO3** (PetroRio) | 🔴 Baixa | — | Petroleira |
| **LWSA3 / "Localiza"** | 🔴 Baixa | — | (ambíguo na transcrição) |
| **USIM5** (Usiminas / "US Minas") | 🟢 Alta | -2,4% | Tendência de alta desde 24/03 (~3 meses) |
| **VEG / "Velga"** (Vega?) | 🔴 Baixa | +1,89% | Volatilidade caindo → opção não "ganhou corpo" |

> ⚠️ **Tickers entre aspas** = como a legenda automática transcreveu (ex: "Semin"=CMIN3, "Braer"=EMBR3, "Brasquen"=BRKM5). **Confirmar antes de operar.** A legenda erra nomes falados.

---

## 🎯 Operações NOVAS do dia (entrar — viradas de tendência)

Caio destacou: **"hoje tivemos 3 viradas de tendência + 1 ajuste"**.

### 1. CSNA3 → comprar PUT
- **Código:** CSN **S610** (delta ~0,46)
- **Preço:** R$ 0,46
- **Ação:** encerrar a call antiga **CSNF 682** (estava ~R$0,007) e montar a put. Vencimento julho (17/07).

### 2. CMIN3 ("Semin") → comprar PUT
- **Código:** **SEMIN S50** (digitar SIN S50 — código com 2 dígitos no fim, normal)
- **Preço:** R$ 0,20–0,21
- **Ação:** encerrar a call antiga **SEMIN G485** (~R$0,10) e virar a mão p/ put.

### 3. LREN3 (Lojas Renner) → comprar PUT
- **Código:** LREN **S151** ("Lin S151")
- **Preço:** R$ 0,76
- **Ação:** encerrar call antiga **LREN F148** (~R$0,54) e entrar na put. Feito perto do fechamento (virou no leilão).

---

## 🔧 Ajuste de Delta do dia (obrigatório só p/ quem já tinha)

### BRKM5 (Braskem) — put bateu +100% de lucro
- **Encerrar:** BRKM **S110** (estava R$ 2,29)
- **Entrar:** BRKM **S900** (delta ~0,45, R$ 0,94) — mesmo vencimento (sem rolagem)
- **Racional:** trocar opção muito valorizada por nova na linha do dinheiro, embolsando o lucro e mantendo exposição.

---

## 📋 Posições em aberto citadas (snapshot de preços na planilha)

| Opção | Ativo | Preço | Nota |
|---|---|---|---|
| COGN R3 | Cogna | R$ 0,20–0,21 | put, baixa |
| LWSA R433 ("localiza") | — | R$ 2,76 | baixa |
| BRAP F205 | Bradespar | R$ 0,90 | +38% lucro |
| MRFG R167 | — | R$ 1,20 | |
| PETR S437 | Petrobras | R$ 2,39 | |
| MRVE S580 | MRV | R$ 0,43 | |
| MGLU S593 | Magalu | R$ 0,68 | |
| BBSE S346 | — | R$ 0,11 | |
| VEG S44 | Vega | R$ 1,28 | |
| USIM G130 ("Zin") | Usiminas | R$ 0,28 | call (alta) |
| CYRE S204 ("Siri") | Cyrela | R$ 1,25 | put — código é CRE/SIRI |
| EMBR MJS693 | Embraer | R$ 1,58 | put |
| CSAN S360 | Cosan | R$ 0,22 | put |
| BRAP S224 | Bradespar | R$ 1,06 | |
| BOVA G52 | BOVA11 | R$ 5,01 | comprado a pedido do "Uli/Will" |

---

## 💬 Q&A relevante (regras operacionais reforçadas)

- **1% do capital** = por operação, frente ao patrimônio total (não por ação).
- **Nunca ficar vendido em calls** (quantidade negativa = recomprar urgente).
- **Ordem não executou / preço fugiu** → editar preço ou abrir grade e pegar nova opção na linha do dinheiro.
- **Preço médio:** nunca fazer.
- **Linha do dinheiro** = strikes mais próximos do preço atual do ativo.
- **PUT** se valoriza quando o ativo objeto **cai** (confusão recorrente esclarecida várias vezes).
- **Trocar de corretora:** pedir transferência de custódia (não vender posições). Profit funciona igual em qualquer corretora.
- **A partir da semana que vem:** todas as operações com vencimento junho serão **roladas**.
- **Quem perde a sala das 16:30** pode entrar na abertura do dia seguinte.
- Ordens de Renner não executadas no leilão → refazer na segunda.

---
*Fonte: transcrição automática do YouTube (live 05/06), 315 segmentos / 45min. Tickers entre aspas precisam de validação manual — legenda auto erra códigos falados.*
