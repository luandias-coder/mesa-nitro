# Fluxo de Aprovação de Ordem — Design

> Objetivo: Luan aprova/pula cada ordem com **um toque**, no **Telegram** OU no **dashboard**,
> e a ponte MT5 executa (com travas). Tudo via a tabela `ordens` (Supabase) que JÁ existe.

## Princípio: a tabela `ordens` é a fonte única da verdade
Tanto o Telegram quanto o dashboard são só **duas janelas** pra mesma fila `ordens`.
Ninguém precisa de servidor novo: a **própria ponte** (que já roda 24/7 no VPS e já lê `ordens`)
vira também o "carteiro" do Telegram. Zero infra nova, sem webhook público.

## Máquina de estados (campo `status`)
```
            cria (dash)              aprova (TG ou dash)         AUTO_SEND=1
  [pendente] ───────► [notificada] ──────────────────► [aprovada] ─────► [executada]
       │                   │                                │     order_check     └─(erro)
       │                   │ pula (TG ou dash)              │
       └───────────────────┴──────────► [cancelada]        └─ AUTO_SEND=0 ► [validada_dry_run]
```
- `pendente` → ordem criada, ainda não avisada.
- `notificada` → ponte mandou a msg no Telegram com botões (não reenvia).
- `aprovada` → Luan tocou Aprovar (TG) ou clicou no dash → ponte pega e valida/executa.
- `executada` / `erro` / `validada_dry_run` → resultado da ponte.
- `cancelada` → Luan pulou.

## Quem faz o quê

### 1. Origem da ordem (2 portas, mesmo destino: cria linha `pendente`)
- **Dashboard (aba Hoje):** botão **"Enviar p/ aprovação"** em cada card → `INSERT ordens`
  (op_id, codigo, acao=comprar/vender, volume=sugestão do sizing, preco_limite, conta).
- (Futuro) geração automática a partir dos sinais resolvidos do dia.

### 2. Ponte (VPS) — 2 funções novas no loop de 15s
- **notificar_pendentes()**: pega `status=pendente` → manda no Telegram msg com botões
  `[✅ Aprovar] [⏭️ Pular]` (callback_data = `ap:<id>` / `pl:<id>`) → grava `tg_message_id`
  e marca `notificada`.
- **processar_callbacks()**: lê `getUpdates` (offset persistido em arquivo) → no toque:
  - `ap:<id>` → `status=aprovada`, edita a msg p/ "✅ Aprovada", responde o callback.
  - `pl:<id>` → `status=cancelada`, edita p/ "⏭️ Pulada".
  - **Só aceita callback do chat_id do Luan (8784619222).** Ignora qualquer outro (o bot é público).

### 3. Ponte — executor (JÁ EXISTE, sem mudança)
`status=aprovada` → `order_check` → se `AUTO_SEND=1`, `order_send` (limitada) → grava
`executada`/`erro` + ticket + preço. Opcional: manda no Telegram o resultado ("✅ Executada, ticket #123").

### 4. Dashboard — botão de executar (pedido do Luan: TG **e** dash)
- Em cada card de ordem: **"Aprovar"** (PATCH status→aprovada) e **"Pular"** (→cancelada),
  além do "Enviar p/ aprovação". Como o cockpit já lê/escreve Supabase, é só um PATCH.
- **Badge de status ao vivo** no card: pendente / notificada / aprovada / executada / erro.

## Travas (guardrails)
- **Duplo gate:** (a) aprovação humana + (b) `AUTO_SEND`. Mesmo aprovada, só ENVIA se AUTO_SEND=1;
  senão fica em dry-run (`validada_dry_run`). Rollout seguro: começa AUTO_SEND=0.
- **order_check** antes de enviar (margem/símbolo/preço). Só ordem **limitada**, nunca a mercado.
- **conta** casa (demo vs real) — ordem de conta != sessão é pulada.
- **Idempotência:** transições de status garantem 1 envio só.
- **Auth do Telegram:** callbacks só do chat_id do Luan.

## Mudanças de schema (mínimas)
```sql
alter table ordens add column if not exists tg_message_id bigint;  -- p/ editar a msg após o toque
-- 'notificada' é só um novo valor de status (campo é texto livre, sem migração).
```

## Passos de build
1. Schema: `alter table` acima (1 linha no Supabase).
2. Ponte: patch `mt5_bridge.py` (+ notificar_pendentes, processar_callbacks, offset getUpdates),
   redeploy via base64+SSH; watchdog garante que sobe.
3. Dashboard `web/index.html`: botões Enviar/Aprovar/Pular + badge de status (PATCH/INSERT Supabase).
4. Teste E2E na conta **DEMO**, **AUTO_SEND=0**: cria → msg no TG → toca Aprovar → order_check
   → `validada_dry_run` → resultado no TG. Depois liga AUTO_SEND=1 quando validar.

## Decisões pendentes (Luan)
- **A) Criação da ordem:** só quando Luan clica "Enviar p/ aprovação" (intenção explícita, sizing
  pré-preenchido) — recomendado — ou auto-criar pendente p/ toda operação da live?
- **B) Volume:** usar a sugestão do sizing como padrão, editável antes de enviar?
- **C) "Pular" no Telegram** também marca a operação como "não entrei" na carteira do dash? (via op_id)
