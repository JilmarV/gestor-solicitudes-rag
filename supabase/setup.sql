create extension if not exists vector;

create table if not exists public.clase08_fragmentos (
  id bigint generated always as identity primary key,
  owner_id uuid not null default auth.uid(),
  corpus_id text not null,
  chunk_id text not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  configuracion jsonb not null default '{}'::jsonb,
  embedding vector(384) not null,
  created_at timestamptz not null default now(),
  unique (owner_id, corpus_id, chunk_id)
);

alter table public.clase08_fragmentos enable row level security;

create policy "propios_select" on public.clase08_fragmentos for select to authenticated using (owner_id = auth.uid());
create policy "propios_insert" on public.clase08_fragmentos for insert to authenticated with check (owner_id = auth.uid());
create policy "propios_update" on public.clase08_fragmentos for update to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
create policy "propios_delete" on public.clase08_fragmentos for delete to authenticated using (owner_id = auth.uid());

create or replace function public.clase08_buscar_fragmentos(
  query_embedding vector(384), p_corpus_id text, p_modelo text, p_revision text, match_count int default 10)
returns table (chunk_id text, content text, metadata jsonb, similitud float)
language sql stable security invoker as $$
  select f.chunk_id, f.content, f.metadata, 1 - (f.embedding <=> query_embedding) as similitud
  from public.clase08_fragmentos f
  where f.owner_id = auth.uid() and f.corpus_id = p_corpus_id
    and f.configuracion->>'modelo' = p_modelo and f.configuracion->>'revision' = p_revision
  order by f.embedding <=> query_embedding
  limit match_count;
$$;
