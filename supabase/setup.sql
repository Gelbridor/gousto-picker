-- Gousto Picks: shared preferences and votes for one household.
-- Run once in Supabase: SQL Editor > New query > paste this > Run.
--
-- The table has row level security on and no policies, so nothing can read or write it directly.
-- The page talks to it only through the three functions below, and every call must include
-- the household's secret sync code (16+ characters), which only lives in your sync link.

create table if not exists public.household_state (
  code        text primary key check (length(code) >= 16),
  prefs       jsonb not null default '{}'::jsonb,   -- shared preferences
  votes       jsonb not null default '{}'::jsonb,   -- { "Tom": { "Recipe name": { "v": 1, ... } }, "Emily": { ... } }
  updated_at  timestamptz not null default now()
);
alter table public.household_state enable row level security;

create or replace function public.gp_get(p_code text) returns jsonb
language sql security definer set search_path = public as $$
  select coalesce(
    (select jsonb_build_object('prefs', prefs, 'votes', votes, 'updated_at', updated_at)
       from public.household_state where code = p_code and length(p_code) >= 16),
    '{}'::jsonb);
$$;

create or replace function public.gp_save_prefs(p_code text, p_prefs jsonb) returns void
language plpgsql security definer set search_path = public as $$
begin
  if length(p_code) < 16 then raise exception 'sync code too short'; end if;
  insert into public.household_state (code, prefs) values (p_code, p_prefs)
  on conflict (code) do update set prefs = excluded.prefs, updated_at = now();
end $$;

create or replace function public.gp_save_votes(p_code text, p_who text, p_votes jsonb) returns void
language plpgsql security definer set search_path = public as $$
begin
  if length(p_code) < 16 then raise exception 'sync code too short'; end if;
  if length(p_who) < 1 or length(p_who) > 40 then raise exception 'name must be 1-40 characters'; end if;
  insert into public.household_state (code, votes) values (p_code, jsonb_build_object(p_who, p_votes))
  on conflict (code) do update
    set votes = jsonb_set(public.household_state.votes, array[p_who], p_votes, true), updated_at = now();
end $$;

revoke all on function public.gp_get(text), public.gp_save_prefs(text, jsonb), public.gp_save_votes(text, text, jsonb) from public;
grant execute on function public.gp_get(text), public.gp_save_prefs(text, jsonb), public.gp_save_votes(text, text, jsonb) to anon, authenticated;

-- Make the new functions visible to the Data API straight away.
notify pgrst, 'reload schema';
