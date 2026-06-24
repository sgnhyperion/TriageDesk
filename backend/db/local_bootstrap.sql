-- =============================================================================
-- local_bootstrap.sql — DEV-ONLY shim so the FROZEN contracts/schema.sql runs
-- unmodified on a plain local Postgres (pgvector image), not Supabase.
--
-- WHY THIS EXISTS
--   contracts/schema.sql is written for Supabase. It assumes things Supabase
--   provides out of the box that a vanilla Postgres does not:
--     1. the built-in roles `authenticated`, `anon`, `service_role`
--        (used by `... to authenticated` in the RLS policies)
--     2. the `auth` schema + `auth.users` table (profiles FKs to auth.users)
--     3. the `auth.uid()` function (used inside the RLS policies)
--   We create thin local stand-ins for those here, BEFORE applying schema.sql,
--   so the contract file itself stays untouched (it's frozen).
--
--   None of this changes behaviour: our backend connects as the `postgres`
--   superuser, which bypasses RLS anyway. The shim is purely so the DDL in
--   schema.sql executes. Swap DATABASE_URL to a real Supabase project later and
--   this file is simply never run.
-- =============================================================================

-- Extensions (schema.sql also declares these with `if not exists`; we create
-- them up front so the auth.users default below can use uuid generation).
create extension if not exists vector;
create extension if not exists "uuid-ossp";

-- Supabase's default roles. RLS policies target `authenticated`.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin bypassrls;
  end if;
end
$$;

-- Minimal `auth` schema so profiles' FK (references auth.users) resolves.
create schema if not exists auth;

create table if not exists auth.users (
    id    uuid primary key default uuid_generate_v4(),
    email text
);

-- Supabase exposes auth.uid() = the current request's user id. Locally there is
-- no JWT context, so we return NULL. (Superuser connections bypass RLS, so the
-- policies that call this never actually gate our backend queries.)
create or replace function auth.uid()
returns uuid
language sql
stable
as $$
    select null::uuid;
$$;
