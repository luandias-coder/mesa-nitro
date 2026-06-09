-- Mesa Nitro — schema Supabase (Postgres)
-- Camadas: dados do analista (sinais/posições) + execuções do usuário (carteira).

create table if not exists lives (
  data        date primary key,
  analista    text,
  video_id    text,
  criado_em   timestamptz default now()
);

create table if not exists sinais (
  id            bigint generated always as identity primary key,
  data          date references lives(data) on delete cascade,
  ts            text,
  acao          text,           -- entrada | saida | ajuste_delta
  underlying    text,
  tipo          text,           -- CALL | PUT
  codigo        text,           -- ticker real B3
  strike        numeric,
  vencimento    date,
  preco_limite  numeric,        -- preço sugerido pelo analista
  preco_atual   numeric,        -- último da grade no resolve
  delta         numeric,
  conf          text,           -- alta | media | baixa
  metodo        text,           -- exato | aprox_premio | gabarito_analista | carry_forward
  motivo        text,
  rel_codigo    text,           -- perna relacionada (saída casada)
  rel_preco     numeric,
  link          text
);
create index if not exists sinais_data_idx on sinais(data);
create index if not exists sinais_under_idx on sinais(underlying);

create table if not exists posicoes_analista (
  id            bigint generated always as identity primary key,
  data          date,           -- live de referência
  underlying    text,
  tipo          text,
  codigo        text,
  strike        numeric,
  vencimento    date,
  entry         numeric,
  atual         numeric,
  conf          text,
  metodo        text,
  pnl_real      text,           -- resultado do gabarito do analista
  atual_em      timestamptz default now()
);

-- carteira REAL do usuário (substitui o localStorage)
create table if not exists execucoes_usuario (
  id            bigint generated always as identity primary key,
  op_id         text,           -- id da operação na fila (data__codigo__acao__ts)
  data          date,
  underlying    text,
  tipo          text,
  acao          text,
  codigo        text,
  status        text,           -- done | skip
  preco_pago    numeric,
  qtd           integer,
  criado_em     timestamptz default now(),
  unique(op_id)
);

-- RLS: interim single-user. Leitura pública (publishable) nos dados; execuções liberadas.
-- TODO: amarrar a Supabase Auth (user_id) quando virar multiusuário.
alter table sinais enable row level security;
alter table posicoes_analista enable row level security;
alter table lives enable row level security;
alter table execucoes_usuario enable row level security;

drop policy if exists p_read_sinais on sinais;          create policy p_read_sinais on sinais for select using (true);
drop policy if exists p_read_pos on posicoes_analista;  create policy p_read_pos on posicoes_analista for select using (true);
drop policy if exists p_read_lives on lives;            create policy p_read_lives on lives for select using (true);
drop policy if exists p_all_exec on execucoes_usuario;  create policy p_all_exec on execucoes_usuario for all using (true) with check (true);
