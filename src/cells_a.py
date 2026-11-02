CELLS = []
def md(t): CELLS.append(("md", t.strip("\n")))
def code(t): CELLS.append(("code", t.strip("\n")))

md(r'''
# Gestor de solicitudes — Notebook consolidado (Segundo corte)

**Proyecto:** Gestor de solicitudes · **Equipo:** Jilmar Veloza y Andrés Galvis · **Curso:** EAM 2026-II · **Docente:** Robert García Rey

Este notebook **corre de principio a fin en Google Colab (CPU)** sin depender de ningún otro notebook. Integra el trabajo de las Clases 02 a 09:

| Clase | Aporte | Dónde está aquí |
|---|---|---|
| 02 | Tokens, contexto mínimo, temperatura | Secciones 1 y 6 (conteo de tokens, `temperature=0`) |
| 03–04 | Función original, contrato de salida, herramienta, seguridad | Secciones 5 a 8 |
| 06–07 | Corpus, chunking, metadatos | Secciones 2 y 3 |
| 08 | Embeddings + Supabase (pgvector) + RAG con citas | Secciones 4, 9 y 10 |
| 09 | BM25 + RRF + reranking, evaluación | Secciones 11 y 12 |

## Mapa de los 12 ítems mínimos de la entrega

| # | Ítem | Sección |
|---|---|---|
| 1 | Función original + entrada del usuario | 5 |
| 2 | Integración con modelo y prompt RAG versionado | 6 y 9 |
| 3 | Salida controlada (contrato, Pydantic, reglas de negocio) | 5 y 9 |
| 4 | Herramienta integrada (`consultar_estado_solicitud`) | 7 |
| 5 | Seguridad y manejo de errores | 1 y 8 |
| 6 | Pruebas, logs y bitácora (5 casos iniciales, latencia, tokens) | 13 |
| 7 | Corpus documentado | 2 |
| 8 | Chunking y metadatos | 3 |
| 9 | Embeddings + Supabase (conexión segura, tabla, reutilización, SQL) | 4 |
| 10 | Recuperación y respuesta con fuentes verificables + enrutamiento RAG vs herramienta | 9 y 10 |
| 11 | Mejora justificada (baseline vs BM25+RRF y/o reranking) | 11 |
| 12 | Evaluación integrada (dev/reserva, métricas, revisión humana, fallo real, límites) | 12 |

### Secretos que debes crear en Colab (icono de llave, “Secrets”)
`SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` (empieza por `sb_publishable_`), `SUPABASE_EMAIL`, `SUPABASE_PASSWORD`, `GROQ_API_KEY`. **Nunca** pegues claves en celdas ni en el repositorio.

> Todos los datos son **ficticios** (solicitudes, códigos SOL-xxxx, manuales). No se usan datos personales reales.
''')

md("## 1. Preparación: dependencias, configuración y secretos (ítem 5: seguridad)")
code(r'''
%pip -q install "supabase==2.32.0" "sentence-transformers==6.1.0" "rank-bm25==0.2.2" groq "pydantic>=2" tiktoken pandas
''')
code(r'''
import os, re, json, time, hashlib, unicodedata, zipfile, textwrap, datetime, math
from pathlib import Path
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal, Optional

# ---------------- Configuración central (nada secreto aquí) ----------------
CONFIG = {
    "modo_llm": "groq",                 # "groq" (real) | "mock" (sin API: solo clasificación/herramienta/RAG extractivo)
    "modelo_llm": "openai/gpt-oss-20b",
    "reasoning_effort": "low",
    "modelo_emb": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "dim_emb": 384,
    "corpus_id": "gestor-solicitudes-v1",
    "version_corpus": "1.0-didactica",
    "tabla": "clase08_fragmentos",
    "rpc": "clase08_buscar_fragmentos",
    "chunk_max_tokens": 110,
    "chunk_solape": 12,
    "bm25": {"k1": 1.5, "b": 0.75, "epsilon": 0.25},
    "rrf_c": 60,
    "candidatos_M": 10,
    "contexto_K": 3,
    "reranker": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
    "reranker_rev": "1427fd652930e4ba29e8149678df786c240d8825",
    "umbral_similitud": 0.30,           # abstención previa al LLM (heurística; se calibra en la sección 12)
    "max_chars_entrada": 600,
    "prompt_rag_version": "rag_v2",
    "prompt_clasif_version": "clasif_v2",
    "almacen": "supabase",              # "supabase" | "local" (solo para pruebas sin credenciales; se avisa en pantalla)
}

def secreto(nombre, obligatorio=True):
    """Lee un secreto de Colab (userdata) o de variables de entorno. Nunca lo imprime."""
    valor = None
    try:
        from google.colab import userdata
        valor = userdata.get(nombre)
    except Exception:
        valor = os.environ.get(nombre)
    if obligatorio and not valor:
        raise RuntimeError(f"Falta el secreto {nombre}. Créalo en Colab > Secrets y activa 'Acceso desde el notebook'.")
    return valor

_PATRON_SECRETO = re.compile(r"(sb_publishable_\w+|sb_secret_\w+|gsk_\w+|eyJ[\w\-]{20,}\.[\w\-]{10,}\.[\w\-]{10,})")
def redactar(texto):
    """Enmascara claves que accidentalmente aparezcan en logs o mensajes de error."""
    return _PATRON_SECRETO.sub("[REDACTADO]", str(texto))

def normalizar(t):
    t = unicodedata.normalize("NFKC", t).casefold()
    return re.sub(r"\s+", " ", t).strip()

LOG_LLM = []     # una fila por llamada al modelo: etapa, latencia, tokens
print("Configuración cargada. Modo LLM:", CONFIG["modo_llm"], "| Almacén:", CONFIG["almacen"])
''')
code(r'''
# ---------------- Cliente Groq + registro de latencia/tokens ----------------
_groq = None
def cliente_groq():
    global _groq
    if _groq is None:
        from groq import Groq
        _groq = Groq(api_key=secreto("GROQ_API_KEY"))
    return _groq

def llamar_llm(mensajes, etapa, schema=None, nombre_schema="salida", tools=None, max_tokens=700):
    """Una sola puerta de entrada al modelo: aplica parámetros fijos, mide latencia y tokens.
    Si falla NO cae en silencio a 'mock': lanza ErrorModelo para que el flujo responda de forma segura."""
    if CONFIG["modo_llm"] != "groq":
        raise ErrorModelo("modo mock: no hay llamada real")
    kw = dict(model=CONFIG["modelo_llm"], messages=mensajes, temperature=0,
              max_completion_tokens=max_tokens, reasoning_effort=CONFIG["reasoning_effort"])
    if schema is not None:
        kw["response_format"] = {"type": "json_schema",
                                 "json_schema": {"name": nombre_schema, "strict": True, "schema": schema}}
    if tools is not None:
        kw.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
    t0 = time.perf_counter()
    try:
        r = cliente_groq().chat.completions.create(**kw)
    except Exception as e:
        raise ErrorModelo(redactar(f"{type(e).__name__}: {e}")) from None
    dt = (time.perf_counter() - t0) * 1000
    u = getattr(r, "usage", None)
    LOG_LLM.append({"etapa": etapa, "latencia_ms": round(dt, 1),
                    "prompt_tokens": getattr(u, "prompt_tokens", None),
                    "completion_tokens": getattr(u, "completion_tokens", None)})
    return r

class ErrorModelo(Exception):
    pass
''')

md("## 2. Corpus documentado (ítem 7)\n\nCorpus **didáctico y ficticio** de 5 documentos Markdown. Se escribe en `corpus/` desde este mismo notebook para que no dependa de archivos externos. Cada documento tiene fuente, versión, licencia/autorización y nota de privacidad (catálogo más abajo).")
code(r'''
CORPUS_DOCS = {
"tipos_solicitud.md": """# Tipos de solicitud

## Tipos disponibles
El gestor reconoce cuatro tipos de solicitud: acceso, documento, pago y queja. Cada solicitud recibe un código con el formato SOL-0000 y se asigna a un único tipo.

## Cómo elegir el tipo
Use el tipo acceso cuando no puede ingresar a la plataforma. Use documento para constancias y certificados. Use pago para cobros, recibos o vencimientos. Use queja para inconformidades sobre un servicio.
""",
"prioridades.md": """# Prioridades de atención

## Niveles de prioridad
Las solicitudes se clasifican en prioridad alta, media o baja. La prioridad define el orden de atención, no el tipo de solicitud.

## Reglas de prioridad
Una solicitud de pago con vencimiento en menos de 48 horas se clasifica con prioridad alta. Las solicitudes de documento sin fecha límite tienen prioridad media. Las consultas generales tienen prioridad baja.
""",
"responsables.md": """# Responsables por área

## Áreas de atención
Las solicitudes de tipo documento las atiende la oficina de registro académico. Las solicitudes de pago las atiende tesorería. Las solicitudes de acceso las atiende soporte técnico.

## Escalamiento
Cuando una solicitud no tiene un área clara, se escala a revisión humana y se contacta a la coordinación del servicio.
""",
"acceso.md": """# Manual de acceso

## Recuperar acceso
Si no puede ingresar a la plataforma, seleccione Recuperar acceso en la pantalla de inicio e ingrese su correo institucional. El sistema envía un enlace temporal. Si el enlace no llega, revise la carpeta de spam y espere cinco minutos; no basta con repetir el envío del enlace varias veces seguidas.

## Error 403
El error 403 indica que el sistema reconoció a la persona pero no autoriza el recurso solicitado. Este error no demuestra por sí solo que la cuenta esté bloqueada. Para reportarlo, adjunte una captura con el mensaje visible e incluya la fecha y el recurso al que intentó acceder.

## Consulta de estados
El código SOL-1001 identifica una solicitud de ejemplo, pero este manual no contiene los estados individuales de las solicitudes. Para conocer el estado actual de una solicitud use la consulta de estado con su código.
""",
"constancias.md": """# Manual de constancias

## Solicitar una constancia
La solicitud de constancia se radica en el módulo de documentos. Indique el tipo de constancia y el correo al que desea recibirla. Antes de radicar, verifique que no tenga una solicitud abierta para el mismo trámite.

## Estado de una constancia
Que una solicitud aparezca como en revisión no significa que la constancia ya esté emitida. Mientras la solicitud no esté cerrada, la constancia no se entrega.

## Correcciones
Si la solicitud tiene un dato erróneo, corríjala desde la solicitud original; crear varias solicitudes iguales no reemplaza la corrección de la original. Si no puede corregirla, contacte al área responsable e indique ese código.
""",
}
CATALOGO = {  # documentación del corpus (ítem 7)
 "tipos_solicitud.md": {"titulo": "Tipos de solicitud", "tema": "clasificación", "origen": "redactado por el equipo"},
 "prioridades.md":     {"titulo": "Prioridades de atención", "tema": "priorización", "origen": "redactado por el equipo"},
 "responsables.md":    {"titulo": "Responsables por área", "tema": "enrutamiento", "origen": "redactado por el equipo"},
 "acceso.md":          {"titulo": "Manual de acceso", "tema": "acceso", "origen": "redactado por el equipo"},
 "constancias.md":     {"titulo": "Manual de constancias", "tema": "documentos", "origen": "redactado por el equipo"},
}
for d in CATALOGO.values():
    d.update(version=CONFIG["version_corpus"], licencia="Uso académico del equipo; contenido ficticio",
             privacidad="Sin datos personales; códigos SOL-xxxx ficticios", idioma="es")

CORPUS_DIR = Path("corpus"); CORPUS_DIR.mkdir(exist_ok=True)
for nombre, texto in CORPUS_DOCS.items():
    (CORPUS_DIR / nombre).write_text(texto.strip() + "\n", encoding="utf-8")

def limpiar(t):
    t = unicodedata.normalize("NFC", t.replace("\r\n", "\n"))
    return re.sub(r"[ \t]+", " ", t).strip()

filas = []
for nombre in CORPUS_DOCS:
    t = limpiar((CORPUS_DIR / nombre).read_text(encoding="utf-8"))
    CATALOGO[nombre]["source_hash"] = hashlib.sha256(t.encode("utf-8")).hexdigest()
    CATALOGO[nombre]["texto"] = t
    filas.append({"fuente": nombre, **{k: v for k, v in CATALOGO[nombre].items() if k not in ("texto", "source_hash")},
                  "hash": CATALOGO[nombre]["source_hash"][:12], "caracteres": len(t)})
pd.DataFrame(filas)
''')

md("## 3. Chunking y metadatos (ítem 8)\n\n**Decisión:** primero se separa por secciones (`##`), porque cada sección del manual responde a una pregunta concreta; solo si una sección supera `chunk_max_tokens` se parte en **ventanas de tokens con solape**. A cada fragmento se le antepone `Título / Sección` para que el embedding conozca su contexto. Se compara con la alternativa “por párrafos”.")
code(r'''
from transformers import AutoTokenizer
TOK = AutoTokenizer.from_pretrained(CONFIG["modelo_emb"])

def secciones(nombre, texto):
    titulo = CATALOGO[nombre]["titulo"]
    partes = re.split(r"\n(?=## )", texto)
    for p in partes:
        if p.startswith("# "):            # título del documento
            p = p.split("\n", 1)[1] if "\n" in p else ""
            if not p.strip(): continue
        m = re.match(r"## ([^\n]+)\n(.*)", p, flags=re.S)
        if m: yield titulo, m.group(1).strip(), m.group(2).strip()

def ventanas(texto, max_tokens, solape):
    ids = TOK.encode(texto, add_special_tokens=False)
    if len(ids) <= max_tokens:
        return [texto]
    out, ini = [], 0
    while ini < len(ids):
        out.append(TOK.decode(ids[ini:ini + max_tokens]).strip())
        if ini + max_tokens >= len(ids): break
        ini += max_tokens - solape
    return out

def parrafos(texto):
    return [p.strip() for p in texto.split("\n\n") if p.strip()]

def fragmentar(estrategia="ventanas"):
    frags = []
    for nombre in CORPUS_DOCS:
        n = 0
        for titulo, sec, cuerpo in secciones(nombre, CATALOGO[nombre]["texto"]):
            trozos = ventanas(cuerpo, CONFIG["chunk_max_tokens"], CONFIG["chunk_solape"]) if estrategia == "ventanas" else parrafos(cuerpo)
            for tr in trozos:
                n += 1
                contenido = f"{titulo} / {sec}\n{tr}"
                frags.append({
                    "chunk_id": f"{nombre.removesuffix('.md')}-{n:02d}",
                    "content": contenido,
                    "metadata": {"source": nombre, "section": sec, "version": CONFIG["version_corpus"],
                                 "source_hash": CATALOGO[nombre]["source_hash"], "estrategia": estrategia,
                                 "tokens": len(TOK.encode(contenido, add_special_tokens=False))},
                })
    return frags

FRAGMENTOS = fragmentar("ventanas")
comparacion = pd.DataFrame([{"estrategia": e, "fragmentos": len(f), "tokens_max": max(x["metadata"]["tokens"] for x in f),
                             "tokens_prom": round(np.mean([x["metadata"]["tokens"] for x in f]), 1)}
                            for e, f in (("ventanas", FRAGMENTOS), ("parrafos", fragmentar("parrafos")))])
display(comparacion)
assert all(f["metadata"]["tokens"] <= 128 for f in FRAGMENTOS), "Un fragmento supera max_seq_length=128 del modelo de embeddings"
pd.DataFrame([{"chunk_id": f["chunk_id"], **{k: f["metadata"][k] for k in ("source", "section", "tokens")}} for f in FRAGMENTOS])
''')

md(r'''
## 4. Embeddings + Supabase (ítem 9)

**Qué se hace:** (1) se crea la tabla con pgvector y RLS ejecutando el SQL de abajo **una vez** en el *SQL Editor* de Supabase; (2) el notebook inicia sesión con correo/contraseña usando la clave *publishable* (la fila queda ligada a tu `owner_id` por RLS); (3) se calculan embeddings **solo si el índice no existe o cambió** (se compara modelo, revisión y hash de cada fragmento). Las consultas **no** vuelven a embeber el corpus.

### SQL de reconstrucción / restauración
Es el contenido de `supabase/setup.sql` del repositorio. Para **reconstruir**: ejecutar el SQL, ejecutar este notebook (sección 4) y listo. Para **restaurar** tras borrar la tabla: igual. Para **limpiar** solo este corpus: `delete from clase08_fragmentos where corpus_id = 'gestor-solicitudes-v1';`
''')
code(r'''
SQL_SETUP = """
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
"""
Path("supabase").mkdir(exist_ok=True)
Path("supabase/setup.sql").write_text(SQL_SETUP.strip() + "\n", encoding="utf-8")
print("SQL guardado en supabase/setup.sql — pégalo en Supabase > SQL Editor > Run (una sola vez).")
''')
code(r'''
from sentence_transformers import SentenceTransformer
try:
    from huggingface_hub import model_info
    REV_EMB = model_info(CONFIG["modelo_emb"]).sha
except Exception as e:
    REV_EMB = "main"; print("Aviso: no se pudo fijar la revisión del modelo de embeddings:", redactar(e))
EMB = SentenceTransformer(CONFIG["modelo_emb"], revision=REV_EMB, device="cpu")
assert EMB.get_sentence_embedding_dimension() == CONFIG["dim_emb"]
CONFIG["revision_emb"] = REV_EMB

def embeber(textos):
    return EMB.encode(textos, normalize_embeddings=True, batch_size=16, show_progress_bar=False)

CFG_INDICE = {"modelo": CONFIG["modelo_emb"], "revision": REV_EMB, "dim": CONFIG["dim_emb"], "normalizado": True,
              "metrica": "coseno", "chunk_max_tokens": CONFIG["chunk_max_tokens"], "solape": CONFIG["chunk_solape"]}

class AlmacenSupabase:
    nombre = "supabase"
    def __init__(self):
        from supabase import create_client
        self.sb = create_client(secreto("SUPABASE_URL"), secreto("SUPABASE_PUBLISHABLE_KEY"))
        self.sb.auth.sign_in_with_password({"email": secreto("SUPABASE_EMAIL"), "password": secreto("SUPABASE_PASSWORD")})
    def leer_indice(self):
        r = self.sb.table(CONFIG["tabla"]).select("chunk_id,metadata,configuracion").eq("corpus_id", CONFIG["corpus_id"]).execute()
        return r.data
    def upsert(self, filas):
        self.sb.table(CONFIG["tabla"]).upsert(filas, on_conflict="owner_id,corpus_id,chunk_id").execute()
    def borrar_sobrantes(self, ids_vigentes):
        existentes = [x["chunk_id"] for x in self.leer_indice()]
        for cid in set(existentes) - set(ids_vigentes):
            self.sb.table(CONFIG["tabla"]).delete().eq("corpus_id", CONFIG["corpus_id"]).eq("chunk_id", cid).execute()
    def buscar(self, vec, m):
        r = self.sb.rpc(CONFIG["rpc"], {"query_embedding": vec.tolist(), "p_corpus_id": CONFIG["corpus_id"],
                                        "p_modelo": CFG_INDICE["modelo"], "p_revision": CFG_INDICE["revision"],
                                        "match_count": m}).execute()
        return r.data

class AlmacenLocal:
    """SOLO para pruebas sin credenciales. No cumple el requisito de Supabase de la entrega final."""
    nombre = "local"
    def __init__(self): self.filas = {}
    def leer_indice(self): return [{"chunk_id": k, "metadata": v["metadata"], "configuracion": v["configuracion"]} for k, v in self.filas.items()]
    def upsert(self, filas):
        for f in filas: self.filas[f["chunk_id"]] = f
    def borrar_sobrantes(self, ids):
        for k in set(self.filas) - set(ids): del self.filas[k]
    def buscar(self, vec, m):
        res = [{"chunk_id": k, "content": f["content"], "metadata": f["metadata"],
                "similitud": float(np.dot(vec, np.array(f["embedding"])))} for k, f in self.filas.items()]
        return sorted(res, key=lambda x: -x["similitud"])[:m]

def abrir_almacen():
    if CONFIG["almacen"] == "supabase":
        try:
            return AlmacenSupabase()
        except Exception as e:
            raise RuntimeError("No se pudo conectar a Supabase (revisa secretos y que ejecutaste el SQL): " + redactar(e)) from None
    print("⚠️ ALMACÉN LOCAL: solo para pruebas. La entrega final debe usar Supabase.")
    return AlmacenLocal()

def indice_vigente(almacen):
    """True si lo guardado coincide con el corpus actual (mismos ids, hashes, modelo y revisión) -> no re-embeber."""
    guardado = {x["chunk_id"]: x for x in almacen.leer_indice()}
    if set(guardado) != {f["chunk_id"] for f in FRAGMENTOS}: return False
    for f in FRAGMENTOS:
        g = guardado[f["chunk_id"]]
        if g["metadata"].get("source_hash") != f["metadata"]["source_hash"]: return False
        if g["metadata"].get("section") != f["metadata"]["section"]: return False
        if g["configuracion"].get("modelo") != CFG_INDICE["modelo"] or g["configuracion"].get("revision") != CFG_INDICE["revision"]: return False
    return True

def construir_o_reutilizar(almacen):
    if indice_vigente(almacen):
        print(f"✔ Índice vigente en {almacen.nombre}: se reutiliza ({len(FRAGMENTOS)} fragmentos). Sin re-embeber.")
        return "reutilizado"
    t0 = time.perf_counter()
    vecs = embeber([f["content"] for f in FRAGMENTOS])
    filas = [{"corpus_id": CONFIG["corpus_id"], "chunk_id": f["chunk_id"], "content": f["content"],
              "metadata": f["metadata"], "configuracion": CFG_INDICE, "embedding": v.tolist()}
             for f, v in zip(FRAGMENTOS, vecs)]
    almacen.upsert(filas)
    almacen.borrar_sobrantes([f["chunk_id"] for f in FRAGMENTOS])
    print(f"✔ Índice construido en {almacen.nombre}: {len(filas)} fragmentos en {time.perf_counter()-t0:.1f}s")
    return "construido"

ALMACEN = abrir_almacen()
ESTADO_INDICE = construir_o_reutilizar(ALMACEN)
''')
code(r'''
# Segunda ejecución: debe REUTILIZAR (evidencia de que no se re-embebe por consulta ni por reinicio)
assert indice_vigente(ALMACEN), "El índice debería estar vigente tras construirlo"
print("Reutilización verificada: indice_vigente() = True")
''')
