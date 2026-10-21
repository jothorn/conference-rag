-- Conference RAG schema: authenticated talk search and a public page-view counter.
create schema if not exists extensions;
create extension if not exists vector with schema extensions;
create extension if not exists pg_trgm with schema extensions;
grant usage on schema extensions to anon, authenticated;

create table if not exists public.sentence_embeddings (
  id uuid primary key default gen_random_uuid(),
  talk_id uuid not null,
  title text not null,
  speaker text,
  calling text,
  year integer,
  season text,
  url text not null,
  sentence_num integer not null check (sentence_num > 0),
  text text not null,
  embedding extensions.vector(1536),
  created_at timestamptz not null default now(),
  constraint sentence_embeddings_talk_sentence_unique unique (talk_id, sentence_num)
);

create index if not exists sentence_embeddings_talk_id_idx
  on public.sentence_embeddings (talk_id);
create index if not exists sentence_embeddings_speaker_idx
  on public.sentence_embeddings (speaker);
create index if not exists sentence_embeddings_text_trgm_idx
  on public.sentence_embeddings using gin (text extensions.gin_trgm_ops);
create index if not exists sentence_embeddings_embedding_hnsw_idx
  on public.sentence_embeddings using hnsw (embedding extensions.vector_cosine_ops);

alter table public.sentence_embeddings enable row level security;
revoke all on public.sentence_embeddings from public, anon, authenticated;
grant select on public.sentence_embeddings to anon, authenticated;
drop policy if exists "Allow authenticated users to read" on public.sentence_embeddings;
create policy "Allow authenticated users to read"
  on public.sentence_embeddings for select to authenticated using (true);

create table if not exists public.page_views (
  id uuid primary key default gen_random_uuid(),
  visited_at timestamptz not null default now(),
  page_url text,
  user_agent text
);

alter table public.page_views enable row level security;
revoke all on public.page_views from public, anon, authenticated;
grant select, insert on public.page_views to anon, authenticated;
drop policy if exists "Allow public inserts" on public.page_views;
create policy "Allow public inserts"
  on public.page_views for insert to anon, authenticated with check (true);
drop policy if exists "Allow public reads" on public.page_views;
create policy "Allow public reads"
  on public.page_views for select to anon, authenticated using (true);

drop function if exists public.match_sentences(extensions.vector, integer);
drop function if exists public.match_sentences(extensions.vector, integer, text);
create function public.match_sentences(
  query_embedding extensions.vector(1536),
  match_count integer default 20,
  speaker_filter text default null
)
returns table (
  id uuid,
  talk_id uuid,
  title text,
  speaker text,
  url text,
  text text,
  similarity double precision
)
language sql
stable
security invoker
set search_path = public, extensions
set hnsw.iterative_scan = 'strict_order'
as $$
  select
    se.id,
    se.talk_id,
    se.title,
    se.speaker,
    se.url,
    se.text,
    1 - (se.embedding <=> query_embedding) as similarity
  from public.sentence_embeddings as se
  where se.embedding is not null
    and (speaker_filter is null or se.speaker = speaker_filter)
  order by se.embedding <=> query_embedding
  limit least(greatest(coalesce(match_count, 20), 1), 50);
$$;
revoke all on function public.match_sentences(extensions.vector, integer, text) from public, anon;
grant execute on function public.match_sentences(extensions.vector, integer, text) to authenticated;

create or replace function public.list_speakers()
returns table (speaker text)
language sql
stable
security invoker
set search_path = public, extensions
as $$
  select distinct se.speaker
  from public.sentence_embeddings as se
  where se.speaker is not null and btrim(se.speaker) <> ''
  order by se.speaker;
$$;
revoke all on function public.list_speakers() from public, anon;
grant execute on function public.list_speakers() to authenticated;

notify pgrst, 'reload schema';

