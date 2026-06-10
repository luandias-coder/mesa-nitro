# V2_PLAN.md — HANDOFF AUTOSSUFICIENTE (Mesa Nitro / Trading)

> **Propósito:** garantia "sem perder uma vírgula" para um eu-do-futuro acordar do ZERO e continuar.
> Criado em 2026-06-10 antes de um reset/compactação de sessão pedido pelo Luan.
> Tudo aqui é **VERBATIM** do MEMORY.md no momento do handoff + estado vivo de execução.
> Se algo neste arquivo conflitar com o MEMORY.md curado, **este arquivo é a fonte detalhada**;
> o MEMORY.md curado é só o índice/snapshot. Repo: `luandias-coder/mesa-nitro` (este diretório).

---

# PARTE 1 — A PROPOSTA DO REDESIGN v2 (VERBATIM, COMPLETA)

## 🔁 REDESIGN v2 (Luan frustrado 2026-06-10, "tá horrível, pensando em começar do zero")
**Dores reais:** (1) NÃO dá pra saber "quais ordens executar pra replicar 100% da Sala" — info fragmentada (Hoje/fila + Carteira analista/Entrar + badges). (2) Fluxo de aprovação SEMPRE bate no Telegram — Luan quer Telegram e dash como canais **PARALELOS e independentes** (Telegram = quando longe do PC), não dash→cria→aprova-no-Telegram. (3) Conceitos demais (Hoje vs Carteira analista vs Sua carteira vs Executei/Não entrei vs badges). (4) Sem placar de replicação. (5) Resultado: mais trabalhoso que assistir a live e anotar ticker manual = FALHOU.

**PROPOSTA "Mesa de Replicação" (1 tela, 1 job):** placar "Replicando 7/12 da Sala, faltam X,Y,Z" + **lista única de AÇÕES** (cada linha = O QUE comprar/vender CALL/PUT TICKER · QUANTO sizing · PREÇO limite+live+✅dá entrar · [Executar 1-tap = REAL direto, SEM 2 passos] [Pular]). Dois grupos: "Ações de hoje (da live)" + "Catch-up com a Sala (posições faltantes)". Dash [Executar] cria ordem JÁ aprovada→ponte executa (1 clique). Telegram = MESMA lista com botões, paralelo. Estado compartilhado (Supabase): fez num, aparece feito no outro.

**BUILD:** DUPLICAR — nova rota/arquivo (web/v2 ou similar), atual intacto. Backend (ordens/sinais/posicoes_analista + ponte) reaproveitado. Recomendado construir com CONTEXTO FRESCO (esta sessão gigante). Pausar real (AUTO_SEND=0) durante o redesign.

## 💡 IDEIA: REPLICAR A PLANILHA DA SALA NO SISTEMA (Luan 2026-06-10)
Os analistas preenchem uma planilha "SALA NITRO" ao vivo (colunas: estrutura/COMPRA CALL|PUT, ticker, strike, vencimento, preços, e **coluna F = preço ATUAL do ativo**, atualizada ao vivo). Luan quer **replicar isso visualmente no sistema**. Minha leitura: ÓTIMO e encaixa no v2 — uma tabela "Livro da Sala" espelhando a planilha (todas as ops/posições + preço live = nossa bomba de preço = coluna F), familiar pro Luan, fonte única clara. Vira a base do "Mesa de Replicação".

## IDEIA FUTURA (Luan, 2026-06-10) — TOGGLE DE ORDENS AUTOMÁTICAS
Luan quer, no dashboard, um **toggle "ordens automáticas"**: se ligado, a ordem é aprovada/executada SEM ele clicar "Executar" (tese dele = entrar em TODAS as operações da live). Implementação provável: toggle grava uma flag (config/Supabase) que a auto-criação lê → cria ordem já como `aprovada` em vez de `pendente` (ou a ponte auto-aprova). DEIXAR PRA DEPOIS de tudo validado (gate manual primeiro). Combina com o AUTO_SEND da ponte (os dois ligados = ponta a ponta automático).

## 📐 REGRA DE AJUSTE DE DELTA / ROLAGEM (Luan 2026-06-10 — guardar p/ automação futura)
**Regra da Sala Nitro:** quando o ativo/opção bate **95% ou mais** (delta ~95%, opção fica deep ITM e perde optionalidade/alavancagem), o analista **ENCERRA a posição e RENOVA**: compra a **MESMA tendência** (CALL→CALL, PUT→PUT) num **vencimento MAIS LONGO**, por um **preço parecido** ao da opção original (o que reseta o delta pra mais baixo e mantém a alavancagem). É a "rolagem de vencimento" (ex R→S) que já aparece nos sinais como `ajuste_delta` (MBRFS151, WEG vira-mão). **Futuro automático:** detectar quando a posição em carteira atinge delta≥95% e auto-rolar (fechar + abrir vencimento mais longo, prêmio similar). Precisa de fonte de delta/greeks (MT5 nem sempre dá p/ opção B3 — investigar) ou aproximar por moneyness (preço do ativo vs strike).

## SIZING / TESE DE RÉPLICA (base do placar de replicação do v2)
- **Tese do Luan:** replicar o acumulado da Sala Nitro (~3000%) → **entrar em TODAS as posições, sem cherry-pick, com PESO IGUAL** por posição (peso igual = cada trade contribui igual no %, que é como o acumulado é medido). NÃO filtrar por confiança.
- **Pool inicial:** **R$10.000** ("dinheiro de aprender, se perder não dói"). Carteira atual = 16 posições; 1 contrato de cada = R$1.883 (piso, mas distorce peso); peso-igual ~R$450/pos deploy ~R$7k + ~30% caixa. **R$12k = ideal folgado** (config.json hoje pool=R$12k).
- **Modelo de sizing:** peso-igual, **nunca pula**, `contratos = max(1, round(alvo/(prêmio×100)))`, `alvo = pool×(1−caixa%)/n_posições`, caixa ~30% pra rolagens/ajustes (o edge da metodologia é o ajuste de delta constante → precisa de pólvora). ⚠️ **MAS** ver bloqueio de sizing na Parte 2: pool R$12k vs saldo REAL R$292,95 (display) — reavaliar antes de ligar AUTO_SEND no real.

## DECISÕES DO FLUXO DE APROVAÇÃO (Luan, 2026-06-10) — design completo em `ops/DESIGN-aprovacao-ordens.md`
- **A) Auto-criar ordem `pendente` p/ TODA operação da live** (não só on-click). Luan dá "executar" no Telegram OU no dash → ponte executa.
- **B) Volume = sugestão do sizing** (padrão).
- **C) "Pular" também marca a op como "não entrei"** na carteira do dash.
- Arquitetura: tabela `ordens` = fonte única; a PRÓPRIA PONTE vira carteiro do Telegram (notificar_pendentes + processar_callbacks via getUpdates, offset persistido; SÓ aceita callback do chat_id 8784619222). Duplo gate: aprovação humana + AUTO_SEND. Schema `ordens`: id,op_id,conta,codigo,acao,volume,preco_limite,status,ticket,preco_exec,resultado,criado_em,atualizado_em.

> **NOTA DE LEITURA PRO v2:** o redesign reaproveita TODO o backend abaixo (Parte 2). A mudança é de UI/UX
> (1 tela, lista única de ações, placar de replicação, dash↔Telegram paralelos via mesmo estado Supabase,
> [Executar] = 1 clique que cria ordem JÁ `aprovada`). Construir em arquivo/rota NOVO (`web/v2`), deixar o
> `web/index.html` atual intacto. Pausar AUTO_SEND (=0) durante o redesign.

---

# PARTE 2 — ESTADO VIVO DE EXECUÇÃO (snapshot 2026-06-10, VERBATIM do MEMORY.md)

## 🟢 SNAPSHOT — ONDE TUDO ESTÁ
**Repo:** `luandias-coder/mesa-nitro` (push via `git push https://x-access-token:$(cat /Users/luandias/.openclaw/secrets/github-mesa-nitro.token)@github.com/luandias-coder/mesa-nitro.git HEAD:main`). Dash live = `web/index.html` → Vercel (`vercel --prod` do PAI com `web/.vercel` copiado p/ raiz; Root Dir do projeto = "web"). Pipeline cloud = `.github/workflows/daily.yml` (cron 18:40 BRT). Ponte = `mt5_bridge.py` (deployada em `C:\mt5_bridge.py` no VPS Windows 216.238.118.28).

**VPS (SSH via expect, sem sshpass):** creds em `ops/vps.env` (gitignored). Shell=PowerShell. Ler arquivo travado: .NET FileShare ReadWrite. Escrever .ps1: base64+`[IO.File]::WriteAllBytes` (BOM UTF-8 só p/ PS, NÃO p/ .py). Tasks: `NitroBridge` (/IT, lança `C:\nitro_bridge.bat`), `NitroWatchdog` (SYSTEM, 12:00-02:00 UTC=09-23 BRT a cada 5min, self-heal+alerta Telegram), `NitroPreOpen` (SYSTEM, 12:00 UTC=09h BRT dias úteis, confirma no Telegram "pronta pra abertura" ou alerta se ponte caída; script `C:\nitro_preopen.ps1`, fonte `ops/nitro_preopen.ps1`).

**FLUXO DE APROVAÇÃO = FUNCIONANDO. AUTO_SEND=1 LIGADO (2026-06-10, demo Rico):** Luan autorizou execução real. Bats (nitro_bridge.bat + Startup) com `AUTO_SEND=1` + `PRICE_SEG=60`. Ponte rodando AUTO_SEND=True. Aprovar (TG/dash) → order_check → **order_send REAL** (limitada) na conta demo. Fluxo: pipeline cria `pendente` → ponte notifica Telegram c/ botões + dash mostra → Luan aprova → executa. Tabela `ordens` = fonte única. Volume = contratos×100 (normalizado). Telegram @MesaNitroBot.

**FILA DE ABERTURA (feito, commit fde8a1d):** aprovar ordem com mercado FECHADO não dá mais "erro" — vira status `fila_abertura` (detecta retcode 10018 MARKET_CLOSED no order_check/order_send), a ponte re-tenta a cada ciclo SEM spam e EXECUTA no 1º momento de abertura → `executada`. loop lê `status=in.(aprovada,fila_abertura)`, só PATCHa/notifica quando muda. Dash: ORDST + effStatus tratam `fila_abertura` (badge "📅 na fila → executa na abertura", conta como done/popula carteira). Resolve: parsing é pós-pregão, então aprovação quase sempre é com mercado fechado → execução real é na abertura seguinte (às vezes outro dia). Luan PODE aprovar as 9 ordens AGORA — vão enfileirar e disparar às 10h.

**AUTO-CRIAÇÃO CIENTE DE POSIÇÃO (feito, commit dab7b72):** insight do Luan — entramos numa Sala com histórico; saída/ajuste de posição que NUNCA tivemos não se aplica (executar saída sem ter = vender opção a descoberto = short, RISCO). `criar_ordens_pendentes` agora: entrada→sempre cria; saída/ajuste→só cria se `op.codigo` ∈ posições abertas (compras executada/aprovada/fila menos vendidas). Carteira limpa = só entradas. Cancelei as 5 saídas (vender) da fila 08/06; sobraram 4 entradas (WEGEG447, COGNS273, RENTS403, BRAVG215). Resposta ao Luan: numa vira-mão (fecha PUT + abre CALL), quem começa limpo PULA a saída do PUT e faz só a entrada da CALL.

**PREÇO LIVE = MID BID/ASK (commit e42897b):** `atualizar_precos` agora prioriza `mid=(bid+ask)/2` ao vivo (cotação real do book), `last` só fallback (em opção ilíquida o last é negócio velho → preço irreal). Luan: "live real real real" — pq se o preço estiver fora, a limitada não executa ou paga caro.

**PENDÊNCIAS VALIDAÇÃO MANUAL (commit 7d570ba):** Luan quer replicar 100% das ops; o que o parsing não reconhece (sem codigo) ou sem preço (ex MBRFS151, preco_limite=null) NÃO some — card no dash ganha aviso "⚠️ Validação manual" (`.manualval`, condição `!op.codigo||op.limite==null`). MBRFS151 = ajuste/rolagem R→S "só p/ quem já estava posicionado" + sem preço → corretamente não vira ordem p/ carteira limpa, mas aparece flagado. Luan: NÃO precisa cache de símbolos do broker (BOVA-type real-mas-fora-do-demo é aceitável).

**DEMO ZERADA + DASHBOARD (2026-06-10):** fechei as 3 posições demo (retcode 10009) + zerei tabela `ordens`. Dashboard: botão **"▶ Entrar"** na carteira do analista (`entrarPosicao` cria ordem pendente conta=demo, codigo/comprar/sizing/preco_limite=entry; commit 35f354c) + selo "Dá entrar agora?" (entryBadge live vs entrada do analista) + REMOVIDA a barra "X/N resolvidas"+"limpar marcações" (confusa).

**🔴 MIGRADO PRA CONTA REAL (2026-06-10, AUTO_SEND=0 por segurança):** o email do Rico dizia "Ambiente Demonstrativo" mas testei o login e **TRADE_MODE=2 (REAL)** — é DINHEIRO REAL. Conta `6824926` / senha `97R6mBG@` / server **Rico-PRD** / saldo **R$292,95** / nome LUAN CESAR BALBINO DIAS. Bats (nitro_bridge.bat + Startup) atualizados: MT5_LOGIN=6824926, MT5_PASSWORD=97R6mBG@, MT5_SERVER=Rico-PRD, MT5_CONTA=real, **AUTO_SEND=0** (dry-run, trava de segurança). Ponte rodando CONECTADO real AUTO_SEND=False. Demo zerada antes.

**FUNDING NÃO É BLOQUEIO (2026-06-10):** Rico avisa "a plataforma MT5 não replica o saldo da conta; mesmo aparecendo saldo zero opera normalmente". Confirmado: `order_check` na conta real retcode=0 'Done' p/ ordens de R$13, R$468, R$420 mesmo com margin_free=292.95 (margin=0, leverage=1). O R$292,95 é só display; opera contra a conta Rico real (R$10k+). Falta só: validar order_send REAL com 1 ordem pequena (~R$13) antes de escalar.

**BLOQUEIOS ANTES DE LIGAR AUTO_SEND=1 (real):** (1) **SIZING:** config.json pool=R$12k (~R$474/pos) vs saldo REAL R$292,95 → ordens seriam rejeitadas por margem/super-alavancadas. AJUSTAR pool pro capital real (perguntar quanto Luan vai operar). (2) **Botão Entrar do dash cria conta="demo"** (hardcoded) — trocar p/ "real" senão a ponte (filtra conta=eq.real) ignora. (3) **ORDENS_CONTA=real** no workflow GitHub (cron diário). (4) GO explícito do Luan. Luan quer posicionar ANTES da live 16:30.

**FUTURO (Luan, 2026-06-10, NÃO agora):** (1) tentar parsear DURANTE a live das 16:30 (não só pós); (2) o robô saber analisar o GRÁFICO e definir tendência (hoje depende do analista Caio).

**TESTE 10h (2026-06-10) — gargalo ALGO TRADING + validação de ticker:** Luan aprovou as 4 entradas; todas deram erro. 3 (WEGEG447/COGNS273/RENTS403) = `retcode 10027 AutoTrading disabled by client` → o botão **"Algo Trading" do MT5 estava DESLIGADO** (`terminal.trade_allowed=False`; conta/expert OK; mercado aberto 10:07). FIX permanente: MT5 → Ferramentas → Opções → Expert Advisors → marcar "Permitir negociação algorítmica" (volta ligado a cada start, inclusive pós-reboot). Não dá p/ ligar remoto (trava de GUI). 1 (BRAVG215) = "símbolo indisponível" (não existe no demo Rico; BRAV3 existe) — erro da legenda. **VALIDAÇÃO DE TICKER CONSTRUÍDA (commit fbdc26b):** `notificar_pendentes(mt5)` agora valida `symbol_select`+`symbol_info` ANTES de oferecer; ticker inexistente → status `ticker_invalido` (não aprovável, avisa no TG) em vez de virar ordem. Dash: ORDST+effStatus tratam `ticker_invalido` (skip, badge aviso). **RESOLVIDO 10:xx — EXECUÇÃO REAL PROVADA:** Luan marcou "Permitir negociação algorítmica" (Opções→Expert Advisors), `trade_allowed=True`. Re-armei as 3 (erro→aprovada) → **TODAS executaram, ticket real no MT5 demo** (COGNS273 t=2453873510, RENTS403 t=2453873565, WEGEG447 t=2453873582; px=0 = limitada pendente esperando preço). CICLO COMPLETO PROVADO ponta-a-ponta com order_send real. Próximo passo do Luan: migrar pra conta REAL.

**PLANO 2026-06-10 10h (abertura):** Luan vai aprovar algumas ordens na DEMO com mercado aberto, ver order_send criar ordem limitada de verdade. Dando certo → MIGRAR PRA CONTA REAL (passo explícito dele: trocar MT5_LOGIN/PASSWORD/SERVER + MT5_CONTA=real nos bats + ORDENS_CONTA=real na auto-criação; precisa das creds reais do Rico + go dele). **9 ordens da fila 08/06 criadas (conta=demo, todas notificadas) pra ele testar.** NÃO aprovar antes das 10h (mercado fechado → order_send falha).

**ALERTA INFRA:** tarefa NitroBridge (self-heal do watchdog) deu erro transitório `-2147020576` (sessão interativa) durante minha rajada de restarts; subi a ponte via tarefa once /IT (método da 1ª vez, sempre funciona). Watchdog ainda usa NitroBridge — se falhar no self-heal, alerta dispara. Vigiar.

**FEEDBACK PENDENTE DO LUAN (2026-06-10):**
1. ✅ **UNIFICAR execução — FEITO (commit 9ae64ec):** dash tem `effStatus(op)` que DERIVA o status do usuário da ORDEM (aprovada/executada/validada_dry_run→done, usa preco_exec||preco_limite e volume; cancelada→skip; senão cai no store legado). userPortfolio/renderHoje/kpis usam effStatus → aprovar (TG ou dash) popula a carteira "você" SOZINHO; botões manuais Executei/Não entrei somem quando há ordem. Provado em node (test lógico).
2. ✅ **PREÇO LIVE — FEITO E VALIDADO (commit 1cd122b):** MT5 demo Rico TEM tick de opção (WEGES444 last=0.95). Ponte `atualizar_precos()` a cada `PRICE_SEG`=60s pega tick (`last`, senão mid bid/ask) dos tickers da fila e PATCHa `sinais.preco_atual` no Supabase (provado: 0.72→0.95; "precos live atualizados: 3/10", ilíquidas zeradas puladas). Dashboard faz poll `loadAll` a cada 45s (pula se modal aberto) e recalcula "Ainda dá". MT5 = a "API live" (sem commit/push/CORS/scraping).
3. ✅ **PWA bottom nav — FEITO (commit 4d3e046):** nav vira ícone+label; no mobile (≤720px) fixa no RODAPÉ (tab bar, safe-area iPhone, indicador da aba ativa); no desktop segue abas no topo. Ícones emoji (⚡📊🧮🕘📖). Handler de clique inalterado.
4. ✅ feitos: removido "copiar p/ home broker" (copy mantido); fix volume 10014.

**LIMPAR:** ordens de teste no Supabase (id=12 WEGES444 e quaisquer demo_test/TESTE/PUBTEST).

---

# PARTE 3 — THREADS EM ABERTO / PRÓXIMOS PASSOS

## 🔴 BLOQUEIOS PARA LIGAR AUTO_SEND=1 NO REAL (ordem de execução)
1. **SIZING vs capital real.** config.json pool=R$12k → ~R$474/pos. Saldo display R$292,95 (mas funding "não é bloqueio", opera contra conta Rico real R$10k+). **AÇÃO:** perguntar ao Luan quanto ele vai operar de fato no real e ajustar `pool` no config.json. Risco real = ordens super-alavancadas se o pool não bater com o capital.
2. **Botão "Entrar" do dash hardcoda conta="demo"** (`entrarPosicao`). Trocar p/ "real" — senão a ponte (filtra `conta=eq.real`) ignora a ordem criada pelo dash.
3. **ORDENS_CONTA=real** no workflow GitHub (`.github/workflows/daily.yml`) — a auto-criação diária precisa criar ordens com conta=real.
4. **GO explícito do Luan** + validar 1 order_send REAL pequeno (~R$13) antes de escalar.
5. Luan quer **posicionar ANTES da live das 16:30**.

## ✅ JÁ PROVADO (não refazer)
- Ciclo completo ponta-a-ponta com **order_send REAL na DEMO** (3 tickets reais no MT5: COGNS273, RENTS403, WEGEG447). Fluxo pipeline→pendente→Telegram/dash→aprovação→order_check→order_send funciona.
- Conexão MT5 REAL (6824926/Rico-PRD) lê conta e símbolos; `order_check` retcode=0 'Done' mesmo com saldo display baixo (funding não bloqueia).
- Fila de abertura (mercado fechado não dá erro, enfileira e dispara na abertura).
- Validação de ticker (símbolo inexistente → `ticker_invalido`, não vira ordem).
- Preço live via MT5 (mid bid/ask), poll do dash 45s.
- PWA bottom nav, unificação de execução via effStatus.

## ⚙️ GARGALO OPERACIONAL CONHECIDO
- **Algo Trading do MT5** volta DESLIGADO a cada start (inclusive pós-reboot). Não dá p/ ligar remoto (trava de GUI). FIX manual: MT5 → Ferramentas → Opções → Expert Advisors → "Permitir negociação algorítmica". Se as ordens derem `retcode 10027 AutoTrading disabled by client`, é isso. Luan precisa marcar na GUI pelo console noVNC.

## 🧹 LIMPEZA PENDENTE
- Apagar ordens de teste no Supabase: id=12 WEGES444 + quaisquer `demo_test`/`TESTE`/`PUBTEST`.

## 🔭 FUTURO (Luan, NÃO agora)
- Parsear DURANTE a live das 16:30 (não só pós-pregão).
- Robô analisar o GRÁFICO e definir tendência sozinho (hoje depende do analista da Sala) — objetivo de longo prazo: coordenação full do ciclo sem depender da live.
- Toggle "ordens automáticas" no dash (aprova sem clique) — só depois de tudo validado.
- Auto-rolagem por delta≥95% (precisa fonte de greeks ou aproximar por moneyness).

## 🧨 RISCOS DE INFRA A VIGIAR
- Tarefa `NitroBridge` deu erro transitório `-2147020576` (sessão interativa) durante rajada de restarts; watchdog usa essa tarefa no self-heal — se falhar, o alerta Telegram dispara. Método infalível p/ subir a ponte = tarefa once /IT.
- Auto-logon do Windows NÃO funciona nessa imagem Vultr (quirk). Persistência 24/7 = sessão logada (Luan no console) + watchdog. Cai só em reboot.
- Cookie do YouTube (captura cloud) expira em semanas → workflow avisa no Telegram. PAT mesa-nitro expira ~2026-09-07 (cron de lembrete já criado p/ 2026-09-02).
- Cron do Mac é frágil (Mac dorme) — captura cloud (GH Actions) já resolve, mas validar que roda sozinha num dia com live REAL.

## 📌 LEMBRETE-MOR
- **A LIVE DIÁRIA pós-16:30 é o coração do produto.** Todo dia útil tem live nova; processar SEMPRE (cron ou manual). Mesmo enterrado na frente MT5, a live vem primeiro.
- Tickers da legenda do YouTube erram — confiança ALTA (código exato) é confiável; MÉDIA (`aprox_premio`) precisa conferência.

---

# PARTE 4 — REFERÊNCIA RÁPIDA DE INFRA (para acordar do zero)

- **Repo / push:** `git push https://x-access-token:$(cat /Users/luandias/.openclaw/secrets/github-mesa-nitro.token)@github.com/luandias-coder/mesa-nitro.git HEAD:main`
- **Dash live:** `web/index.html` → Vercel (Root Dir do projeto = "web"; deploy `vercel --prod` do PAI com `web/.vercel` copiado p/ raiz). URL: mesa-nitro.vercel.app
- **Pipeline cloud:** `.github/workflows/daily.yml`, cron `40 21 * * 1-5` (18:40 BRT). Captura→parser→resolver→load_supabase→criar_ordens_pendentes.
- **Ponte MT5:** `mt5_bridge.py` (fonte no repo + `ops/mt5_bridge.py`) → deployada `C:\mt5_bridge.py` no VPS Windows **216.238.118.28**.
- **VPS:** SSH via expect (sem sshpass), creds `ops/vps.env` (gitignored). Shell PowerShell (`;` não `&&`). Chave `~/.ssh/mesa_nitro_vps`. Ler log travado: .NET FileStream FileShare ReadWrite. Escrever .ps1: base64+`[IO.File]::WriteAllBytes` com BOM UTF-8 (NÃO p/ .py).
- **Supabase:** project ref `mqcryomwdwnosoqfmyak`. Tabelas: lives, sinais, posicoes_analista, execucoes_usuario, **ordens** (fonte única). Schema em `schema.sql`. Chaves (publishable/secret) passadas em sessão, NÃO salvas.
- **Telegram:** bot @MesaNitroBot, chat_id Luan = 8784619222. Token/chat_id em `.env` (gitignored) + nos bats do VPS.
- **Tasks Windows:** `NitroBridge` (/IT, lança `C:\nitro_bridge.bat`), `NitroWatchdog` (SYSTEM, 09-23 BRT cada 5min, self-heal+alerta), `NitroPreOpen` (SYSTEM, 09h BRT dias úteis, confirma "pronta pra abertura").
- **MT5 conta ATUAL na ponte:** REAL 6824926 / Rico-PRD / **AUTO_SEND=0 (dry-run, trava)**. (Demo = 3006824926 / Rico-DEMO.)
- **B3:** pregão 10h–17h (after ~18h). NÃO 20h.
- **Config sizing:** `config.json` (pool 12k, caixa 25%, peso 5%, 19/21 ativos).
- **Arquivos-chave do pipeline:** parser.py, resolver.py, load_supabase.py (`criar_ordens_pendentes`), build_web.py, mt5_bridge.py, vtt_to_transcript.py, run_daily.sh. Universo em `tickers.yaml`. Gabarito em `gabarito_analista.yaml`.
- **Design do fluxo de aprovação:** `ops/DESIGN-aprovacao-ordens.md`.
