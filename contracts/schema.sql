-- =============================================================================
-- contracts/schema.sql — FROZEN DATABASE CONTRACT (agree in Hour 1)
-- TriageDesk — Supabase (Postgres + pgvector) schema.
--
-- Owner: Member B. Consumed by everyone (tools read/write these tables;
-- the frontend reads tickets/analytics; agents persist state via checkpoints).
--
-- Run this in the Supabase SQL editor (or via migration) on a fresh project.
-- Embedding dimension = 768 (Gemini text-embedding-004).
-- =============================================================================

-- Extensions ------------------------------------------------------------------
create extension if not exists vector;
create extension if not exists "uuid-ossp";

-- =============================================================================
-- AUTH / USERS
-- Supabase Auth manages auth.users. We mirror role here for app authorization.
-- =============================================================================
create table if not exists profiles (
    id          uuid primary key references auth.users(id) on delete cascade,
    email       text not null,
    full_name   text,
    role        text not null default 'agent' check (role in ('agent', 'admin')),
    created_at  timestamptz not null default now()
);

-- =============================================================================
-- CRM-LIKE DATA (backs the brain's lookup_* tools)
-- =============================================================================
create table if not exists customers (
    id          text primary key,                  -- e.g. CUST-42
    name        text not null,
    email       text not null,
    plan        text not null default 'free',       -- free | pro | enterprise
    created_at  timestamptz not null default now()
);

create table if not exists orders (
    id           text primary key,                  -- e.g. ORD-9001
    customer_id  text not null references customers(id) on delete cascade,
    amount_cents integer not null,
    currency     text not null default 'usd',
    status       text not null default 'paid',       -- paid | refunded | failed | pending
    charged_at   timestamptz not null default now(),
    description  text
);

create table if not exists subscriptions (
    id            text primary key,                 -- e.g. SUB-7001
    customer_id   text not null references customers(id) on delete cascade,
    plan          text not null,
    status        text not null default 'active',    -- active | past_due | canceled
    renews_at     timestamptz,
    created_at    timestamptz not null default now()
);

-- =============================================================================
-- TICKETS (core)
-- =============================================================================
create table if not exists tickets (
    id              text primary key,               -- e.g. TCK-1001
    customer_id     text references customers(id) on delete set null,
    subject         text not null,
    body            text not null,
    -- snapshot of latest classification (full structured value)
    category        text,
    severity        text,
    sentiment       text,
    status          text not null default 'open',   -- open | in_progress | awaiting_human | resolved | escalated | refused
    final_reply     text,
    escalated       boolean not null default false,
    assigned_to     uuid references profiles(id) on delete set null,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- Per-ticket conversation messages (inbound mocked, outbound real via Resend)
create table if not exists messages (
    id           uuid primary key default uuid_generate_v4(),
    ticket_id    text not null references tickets(id) on delete cascade,
    direction    text not null check (direction in ('inbound', 'outbound')),
    sender       text,                              -- customer email or 'agent'/'system'
    body         text not null,
    created_at   timestamptz not null default now()
);

-- Full brain reasoning trace per ticket (the scratchpad, persisted for the UI)
create table if not exists agent_traces (
    id           uuid primary key default uuid_generate_v4(),
    ticket_id    text not null references tickets(id) on delete cascade,
    step         integer not null,
    tool         text not null,
    reason       text,
    args         jsonb,
    result       jsonb,
    ok           boolean,
    created_at   timestamptz not null default now()
);

-- =============================================================================
-- TOOL SIDE-EFFECT TABLES
-- =============================================================================
create table if not exists bug_reports (
    id           text primary key default ('BUG-' || substr(uuid_generate_v4()::text, 1, 8)),
    ticket_id    text references tickets(id) on delete set null,
    title        text not null,
    description  text not null,
    severity     text not null default 'medium',
    status       text not null default 'filed',     -- filed | triaged | closed
    created_at   timestamptz not null default now()
);

-- Refund is MOCKED: we write the intent + outcome here, no real payment provider.
create table if not exists refunds (
    id            text primary key default ('REF-' || substr(uuid_generate_v4()::text, 1, 8)),
    ticket_id     text references tickets(id) on delete set null,
    order_id      text references orders(id) on delete set null,
    amount_cents  integer not null,
    status        text not null default 'pending',  -- pending | approved | processed(mock) | rejected
    approved_by   uuid references profiles(id) on delete set null,
    created_at    timestamptz not null default now()
);

-- =============================================================================
-- KNOWLEDGE BASE (RAG) — admin-uploaded docs, live re-indexed
-- =============================================================================
create table if not exists kb_documents (
    id           uuid primary key default uuid_generate_v4(),
    title        text not null,
    source_path  text,                              -- Supabase Storage path
    uploaded_by  uuid references profiles(id) on delete set null,
    created_at   timestamptz not null default now()
);

create table if not exists kb_chunks (
    id           uuid primary key default uuid_generate_v4(),
    document_id  uuid not null references kb_documents(id) on delete cascade,
    content      text not null,
    embedding    vector(768),                       -- Gemini text-embedding-004
    created_at   timestamptz not null default now()
);

-- Vector similarity search function (called by the retrieve_kb tool)
create or replace function match_kb_chunks(
    query_embedding vector(768),
    match_count int default 4
)
returns table (
    chunk_id uuid,
    document_title text,
    content text,
    score float
)
language sql stable as $$
    select c.id,
           d.title,
           c.content,
           1 - (c.embedding <=> query_embedding) as score
    from kb_chunks c
    join kb_documents d on d.id = c.document_id
    order by c.embedding <=> query_embedding
    limit match_count;
$$;

create index if not exists kb_chunks_embedding_idx
    on kb_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- =============================================================================
-- AUDIT LOG (every high-impact action + human decision)
-- =============================================================================
create table if not exists audit_log (
    id           uuid primary key default uuid_generate_v4(),
    ticket_id    text references tickets(id) on delete set null,
    actor        uuid references profiles(id) on delete set null,  -- null = system/agent
    action       text not null,                     -- e.g. 'send_email', 'process_refund', 'approve'
    detail       jsonb,
    created_at   timestamptz not null default now()
);

-- =============================================================================
-- ROW LEVEL SECURITY (minimal, demo-appropriate)
-- Authenticated agents can read/write tickets; only admins manage the KB.
-- =============================================================================
alter table tickets       enable row level security;
alter table messages      enable row level security;
alter table agent_traces  enable row level security;
alter table kb_documents  enable row level security;
alter table kb_chunks     enable row level security;
alter table audit_log     enable row level security;

-- Any authenticated user (agent or admin) can work tickets.
create policy "authenticated can read tickets"  on tickets for select to authenticated using (true);
create policy "authenticated can write tickets" on tickets for all    to authenticated using (true) with check (true);
create policy "authenticated read messages"     on messages for select to authenticated using (true);
create policy "authenticated write messages"    on messages for all    to authenticated using (true) with check (true);
create policy "authenticated read traces"       on agent_traces for select to authenticated using (true);
create policy "authenticated read audit"        on audit_log for select to authenticated using (true);

-- KB read = anyone authenticated; KB write/upload = admins only.
create policy "authenticated read kb docs"   on kb_documents for select to authenticated using (true);
create policy "authenticated read kb chunks" on kb_chunks    for select to authenticated using (true);
create policy "admins manage kb docs" on kb_documents for all to authenticated
    using (exists (select 1 from profiles p where p.id = auth.uid() and p.role = 'admin'))
    with check (exists (select 1 from profiles p where p.id = auth.uid() and p.role = 'admin'));
create policy "admins manage kb chunks" on kb_chunks for all to authenticated
    using (exists (select 1 from profiles p where p.id = auth.uid() and p.role = 'admin'))
    with check (exists (select 1 from profiles p where p.id = auth.uid() and p.role = 'admin'));

-- NOTE: LangGraph's Postgres checkpointer (for HITL pause/resume) creates and
-- manages its own tables in this database. Member A configures it; no manual
-- DDL needed here.
