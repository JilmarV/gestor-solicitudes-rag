"""preparar_corpus.py — Carga UNA vez el corpus del RAG en Supabase (no se ejecuta por pregunta).

Qué hace (equivale a las secciones 2, 3 y 4 del notebook consolidado):
  1. Lee app/corpus/*.md + catalogo.json y calcula la huella SHA-256 de cada documento.
  2. Fragmenta por secciones (##); si una sección supera 110 tokens la parte en ventanas con solape 12.
     A cada fragmento le antepone «Título / Sección».
  3. Calcula embeddings (paraphrase-multilingual-MiniLM-L12-v2, 384 dim, normalizados) SOLO si el índice
     guardado en Supabase no coincide (ids, huellas, modelo y revisión). Si coincide, lo reutiliza.
  4. Sube los fragmentos con tu sesión de Supabase Auth (RLS: quedan a tu nombre; el resto de usuarios
     autenticados podrá LEERLOS por la política corpus_lectura_autenticados de supabase/setup.sql).

Uso (desde app/, con el entorno virtual activo y app/.env completo):
    python preparar_corpus.py --email cuenta-del-equipo@ejemplo.com        # pide la contraseña sin mostrarla
    python preparar_corpus.py --email ... --forzar                          # recalcula aunque esté vigente
    python preparar_corpus.py --solo-fragmentos                              # no usa red: imprime los fragmentos

Al terminar imprime la REVISIÓN del modelo de embeddings (opcional: EMB_REVISION en .env).
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"), override=False)
except ImportError:
    pass

DIR_CORPUS = Path(__file__).with_name("corpus")
MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIM = 384
CORPUS_ID = os.environ.get("CORPUS_ID", "gestor-solicitudes-v1")
CHUNK_MAX_TOKENS = 110
CHUNK_SOLAPE = 12
MAX_SEQ_MODELO = 128


def limpiar(t: str) -> str:
    t = unicodedata.normalize("NFC", t.replace("\r\n", "\n"))
    return re.sub(r"[ \t]+", " ", t).strip()


def cargar_documentos() -> dict:
    catalogo = json.loads((DIR_CORPUS / "catalogo.json").read_text(encoding="utf-8"))
    docs = {}
    for nombre, meta in catalogo.items():
        ruta = DIR_CORPUS / nombre
        if not ruta.exists():
            raise FileNotFoundError(f"Falta el documento {ruta}")
        texto = limpiar(ruta.read_text(encoding="utf-8"))
        docs[nombre] = {**meta, "texto": texto, "source_hash": hashlib.sha256(texto.encode("utf-8")).hexdigest()}
    return docs


def secciones(titulo: str, texto: str):
    for p in re.split(r"\n(?=## )", texto):
        if p.startswith("# "):
            p = p.split("\n", 1)[1] if "\n" in p else ""
            if not p.strip():
                continue
        m = re.match(r"## ([^\n]+)\n(.*)", p, flags=re.S)
        if m:
            yield titulo, m.group(1).strip(), m.group(2).strip()


def ventanas(texto: str, tokenizador, max_tokens: int, solape: int) -> list[str]:
    ids = tokenizador.encode(texto, add_special_tokens=False)
    if len(ids) <= max_tokens:
        return [texto]
    out, ini = [], 0
    while ini < len(ids):
        out.append(tokenizador.decode(ids[ini:ini + max_tokens]).strip())
        if ini + max_tokens >= len(ids):
            break
        ini += max_tokens - solape
    return out


def fragmentar(docs: dict, tokenizador) -> list[dict]:
    frags = []
    for nombre, d in docs.items():
        n = 0
        for titulo, sec, cuerpo in secciones(d["titulo"], d["texto"]):
            for tr in ventanas(cuerpo, tokenizador, CHUNK_MAX_TOKENS, CHUNK_SOLAPE):
                n += 1
                contenido = f"{titulo} / {sec}\n{tr}"
                frags.append({
                    "chunk_id": f"{nombre.removesuffix('.md')}-{n:02d}",
                    "content": contenido,
                    "metadata": {"source": nombre, "section": sec, "version": d["version"], "source_hash": d["source_hash"],
                                 "estrategia": "ventanas", "tokens": len(tokenizador.encode(contenido, add_special_tokens=False))},
                })
    return frags


def indice_vigente(guardado: list[dict], frags: list[dict], modelo: str, revision: str) -> bool:
    g = {x["chunk_id"]: x for x in guardado}
    if set(g) != {f["chunk_id"] for f in frags}:
        return False
    for f in frags:
        x = g[f["chunk_id"]]
        if (x["metadata"].get("source_hash") != f["metadata"]["source_hash"] or x["metadata"].get("section") != f["metadata"]["section"]
                or x["configuracion"].get("modelo") != modelo or x["configuracion"].get("revision") != revision):
            return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", help="Correo de la cuenta de Supabase Auth del equipo que cargará el corpus")
    ap.add_argument("--forzar", action="store_true", help="Recalcular y subir aunque el índice esté vigente")
    ap.add_argument("--solo-fragmentos", action="store_true", help="Solo fragmenta e imprime (sin Supabase ni embeddings)")
    args = ap.parse_args()

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODELO)
    docs = cargar_documentos()
    frags = fragmentar(docs, tok)
    mayor = max(f["metadata"]["tokens"] for f in frags)
    print(f"Documentos: {len(docs)} · Fragmentos: {len(frags)} · máx. {mayor} tokens (límite del modelo: {MAX_SEQ_MODELO})")
    if mayor > MAX_SEQ_MODELO:
        print("ERROR: un fragmento supera el límite del modelo de embeddings.", file=sys.stderr)
        return 1
    for f in frags:
        print(f"  {f['chunk_id']:<22} {f['metadata']['source']:<20} {f['metadata']['section']:<26} {f['metadata']['tokens']:>3} tokens")
    if args.solo_fragmentos:
        return 0

    from almacenamiento import Almacen, ErrorAlmacenamiento
    email = args.email or os.environ.get("CORPUS_EMAIL") or input("Correo de la cuenta del equipo: ").strip()
    clave = os.environ.get("CORPUS_PASSWORD") or getpass.getpass("Contraseña (no se muestra): ")
    try:
        almacen = Almacen()
        sesion = almacen.iniciar_sesion(email, clave)
    except ErrorAlmacenamiento as e:
        print("ERROR:", e, file=sys.stderr)
        return 1
    del clave

    from huggingface_hub import model_info
    revision = os.environ.get("EMB_REVISION", "").strip()
    if not revision:
        try:
            revision = model_info(MODELO).sha
        except Exception as e:
            print("ERROR: no pude fijar la revisión del modelo de embeddings:", e, file=sys.stderr)
            return 1
    config = {"modelo": MODELO, "revision": revision, "dim": DIM, "normalizado": True, "metrica": "coseno",
              "chunk_max_tokens": CHUNK_MAX_TOKENS, "solape": CHUNK_SOLAPE}

    try:
        guardado = almacen.leer_indice_propio(sesion, CORPUS_ID)
        if not args.forzar and indice_vigente(guardado, frags, MODELO, revision):
            print(f"✔ Índice vigente en Supabase ({len(frags)} fragmentos): se reutiliza, no se recalculan embeddings.")
        else:
            from sentence_transformers import SentenceTransformer
            modelo = SentenceTransformer(MODELO, revision=revision, device="cpu")
            assert modelo.get_sentence_embedding_dimension() == DIM
            t0 = time.perf_counter()
            vecs = modelo.encode([f["content"] for f in frags], normalize_embeddings=True, batch_size=16, show_progress_bar=False)
            filas = [{"corpus_id": CORPUS_ID, "chunk_id": f["chunk_id"], "content": f["content"], "metadata": f["metadata"],
                      "configuracion": config, "embedding": v.tolist()} for f, v in zip(frags, vecs)]
            almacen.upsert_fragmentos(sesion, filas)
            borrados = almacen.borrar_fragmentos_sobrantes(sesion, CORPUS_ID, [f["chunk_id"] for f in frags])
            print(f"✔ Índice construido: {len(filas)} fragmentos en {time.perf_counter() - t0:.1f}s (sobrantes borrados: {borrados})")
        n = len(almacen.leer_indice_propio(sesion, CORPUS_ID))
        print(f"Filas del corpus '{CORPUS_ID}' a tu nombre en Supabase: {n}")
    except ErrorAlmacenamiento as e:
        print("ERROR:", e, file=sys.stderr)
        return 1
    print(f"\nRevisión de embeddings (opcional, para fijarla en .env):  EMB_REVISION={revision}")
    return 0


if __name__ == "__main__":
    sys.exit(main())