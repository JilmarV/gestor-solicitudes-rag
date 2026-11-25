-- =====================================================================
-- Gestor de solicitudes · Entrega final · supabase/setup.sql
-- Ejecutar UNA vez en Supabase > SQL Editor > Run. Es idempotente:
-- se puede volver a ejecutar sin perder datos.
--
-- Contiene:
--   A) Corpus del RAG (clase08_fragmentos + función de búsqueda)
--   B) Historial por usuario (conversaciones + mensajes) con RLS
--
-- Principio: el CORPUS es de lectura compartida para usuarios
-- autenticados (son manuales ficticios), pero el HISTORIAL es privado
-- de cada persona. Nunca se usa la clave "secret"/service_role.
-- =====================================================================

create extension if not exists vector;

-- ---------------------------------------------------------------------
-- A) CORPUS DEL RAG
-- ---------------------------------------------------------------------
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

-- Las políticas de la Clase 08 eran "solo el propietario lee". Para que la
-- aplicación pueda atender a TODOS los usuarios sobre el mismo corpus,
-- la lectura pasa a ser para cualquier usuario autenticado. Escribir,
-- actualizar y borrar sigue siendo solo del propietario de la fila.
drop policy if exists "propios_select" on public.clase08_fragmentos;
drop policy if exists "corpus_lectura_autenticados" on public.clase08_fragmentos;
drop policy if exists "propios_insert" on public.clase08_fragmentos;
drop policy if exists "propios_update" on public.clase08_fragmentos;
drop policy if exists "propios_delete" on public.clase08_fragmentos;

create policy "corpus_lectura_autenticados" on public.clase08_fragmentos
  for select to authenticated using (true);
create policy "propios_insert" on public.clase08_fragmentos
  for insert to authenticated with check (owner_id = auth.uid());
create policy "propios_update" on public.clase08_fragmentos
  for update to authenticated using (owner_id = auth.uid()) with check (owner_id = auth.uid());
create policy "propios_delete" on public.clase08_fragmentos
  for delete to authenticated using (owner_id = auth.uid());

revoke all on public.clase08_fragmentos from anon;
grant select, insert, update, delete on public.clase08_fragmentos to authenticated;

-- Búsqueda vectorial. SECURITY INVOKER: respeta RLS del usuario que llama.
-- "distinct on (chunk_id)" evita duplicados si dos cuentas del equipo
-- cargaron el mismo corpus_id.
create or replace function public.clase08_buscar_fragmentos(
  query_embedding vector(384),
  p_corpus_id text,
  p_modelo text,
  p_revision text,
  match_count int default 10)
returns table (chunk_id text, content text, metadata jsonb, similitud float)
language sql stable security invoker
set search_path = public, extensions
as $$
  select t.chunk_id, t.content, t.metadata, t.similitud
  from (
    select distinct on (f.chunk_id)
           f.chunk_id, f.content, f.metadata,
           1 - (f.embedding <=> query_embedding) as similitud
    from public.clase08_fragmentos f
    where f.corpus_id = p_corpus_id
      and f.configuracion->>'modelo' = p_modelo
      and f.configuracion->>'revision' = p_revision
    order by f.chunk_id, f.embedding <=> query_embedding
  ) t
  order by t.similitud desc
  limit least(greatest(match_count, 1), 50);
$$;

revoke all on function public.clase08_buscar_fragmentos(vector, text, text, text, int) from public, anon;
grant execute on function public.clase08_buscar_fragmentos(vector, text, text, text, int) to authenticated;

-- ---------------------------------------------------------------------
-- B) HISTORIAL POR USUARIO
-- ---------------------------------------------------------------------
create table if not exists public.conversaciones (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  titulo text not null default 'Nueva conversación' check (char_length(titulo) between 1 and 120),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists conversaciones_usuario_idx
  on public.conversaciones (usuario_id, updated_at desc);

create table if not exists public.mensajes (
  id bigint generated always as identity primary key,      -- orden estable de creación
  conversacion_id uuid not null references public.conversaciones(id) on delete cascade,
  usuario_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  rol text not null check (rol in ('user', 'assistant')),
  contenido text not null check (char_length(contenido) between 1 and 8000),
  metadata jsonb not null default '{}'::jsonb,             -- ruta, estado, fuentes, latencia, tokens
  created_at timestamptz not null default now()
);
create index if not exists mensajes_conversacion_idx
  on public.mensajes (conversacion_id, id);

alter table public.conversaciones enable row level security;
alter table public.mensajes enable row level security;

drop policy if exists "conv_select_propias" on public.conversaciones;
drop policy if exists "conv_insert_propias" on public.conversaciones;
drop policy if exists "conv_update_propias" on public.conversaciones;
drop policy if exists "conv_delete_propias" on public.conversaciones;
drop policy if exists "msg_select_propios" on public.mensajes;
drop policy if exists "msg_insert_propios" on public.mensajes;

create policy "conv_select_propias" on public.conversaciones
  for select to authenticated using (usuario_id = auth.uid());
create policy "conv_insert_propias" on public.conversaciones
  for insert to authenticated with check (usuario_id = auth.uid());
create policy "conv_update_propias" on public.conversaciones
  for update to authenticated using (usuario_id = auth.uid()) with check (usuario_id = auth.uid());
create policy "conv_delete_propias" on public.conversaciones
  for delete to authenticated using (usuario_id = auth.uid());

-- Un mensaje se lee o se inserta SOLO si la conversación es del usuario.
-- Conocer el UUID de una conversación ajena no concede acceso.
create policy "msg_select_propios" on public.mensajes
  for select to authenticated using (
    usuario_id = auth.uid()
    and exists (select 1 from public.conversaciones c
                where c.id = conversacion_id and c.usuario_id = auth.uid()));
create policy "msg_insert_propios" on public.mensajes
  for insert to authenticated with check (
    usuario_id = auth.uid()
    and exists (select 1 from public.conversaciones c
                where c.id = conversacion_id and c.usuario_id = auth.uid()));
-- Los mensajes son de solo-añadir: no hay políticas de update ni delete.

revoke all on public.conversaciones, public.mensajes from anon;
grant select, insert, update, delete on public.conversaciones to authenticated;
grant select, insert on public.mensajes to authenticated;
grant usage, select on sequence public.mensajes_id_seq to authenticated;

-- Al añadir un mensaje se actualiza la fecha de la conversación (orden del listado).
create or replace function public.tocar_conversacion()
returns trigger language plpgsql security invoker
set search_path = public
as $$
begin
  update public.conversaciones set updated_at = now() where id = new.conversacion_id;
  return new;
end;
$$;
drop trigger if exists mensajes_tocar_conversacion on public.mensajes;
create trigger mensajes_tocar_conversacion
  after insert on public.mensajes
  for each row execute function public.tocar_conversacion();

-- ---------------------------------------------------------------------
-- Limpieza (NO ejecutar salvo que quieras borrar datos):
--   delete from public.clase08_fragmentos where corpus_id = 'gestor-solicitudes-v1';
-- ---------------------------------------------------------------------
