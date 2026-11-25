"""Utilidades de prueba: un 'Supabase falso' en memoria que emula Auth + PostgREST + las políticas RLS de
supabase/setup.sql. Sirve para probar la lógica de Python SIN red. NO demuestra que las políticas reales de
Postgres funcionen: eso lo comprueba app/verificar_entrega.py contra el proyecto real."""
import itertools
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import almacenamiento as alm  # noqa: E402


class _Resp:
    def __init__(self, data):
        self.data = data


class FakeDB:
    def __init__(self, rls=True):
        self.rls = rls
        self.usuarios = {}          # email -> (password, uid)
        self.tokens = {}            # access_token -> uid
        self.refresh = {}           # refresh_token -> uid
        self.tablas = {"conversaciones": [], "mensajes": [], "clase08_fragmentos": []}
        self._seq = itertools.count(1)
        self.llamadas = []          # (tabla/operacion, uid) para auditar qué token usó cada operación
        self.expira_en = 3600

    def crear_usuario(self, email, password):
        uid = str(uuid.uuid4())
        self.usuarios[email] = (password, uid)
        return uid

    def emitir(self, uid):
        n = next(self._seq)
        at, rt = f"access-{uid[:6]}-{n}", f"refresh-{uid[:6]}-{n}"
        self.tokens[at], self.refresh[rt] = uid, uid
        return at, rt


def _ahora():
    return datetime.now(timezone.utc).isoformat()


class _Auth:
    def __init__(self, db):
        self.db = db

    def sign_in_with_password(self, d):
        pw, uid = self.db.usuarios.get(d["email"], (None, None))
        if pw is None or pw != d["password"]:
            raise Exception("Invalid login credentials")
        at, rt = self.db.emitir(uid)
        return type("R", (), {"user": type("U", (), {"id": uid})(),
                              "session": type("S", (), {"access_token": at, "refresh_token": rt,
                                                        "expires_at": time.time() + self.db.expira_en})()})()

    def refresh_session(self, rt):
        uid = self.db.refresh.get(rt)
        if not uid:
            raise Exception("Invalid refresh token")
        at, nrt = self.db.emitir(uid)
        return type("R", (), {"user": type("U", (), {"id": uid})(),
                              "session": type("S", (), {"access_token": at, "refresh_token": nrt,
                                                        "expires_at": time.time() + self.db.expira_en})()})()

    def get_user(self, token):
        uid = self.db.tokens.get(token)
        if not uid:
            raise Exception("invalid JWT")
        return type("R", (), {"user": type("U", (), {"id": uid})()})()


class _Query:
    def __init__(self, cli, tabla):
        self.cli, self.tabla = cli, tabla
        self.op, self.payload, self.filtros, self.orden, self.lim = "select", None, [], None, None

    def select(self, *_a, **_k): self.op = "select"; return self
    def insert(self, fila): self.op, self.payload = "insert", fila; return self
    def update(self, fila): self.op, self.payload = "update", fila; return self
    def upsert(self, filas, on_conflict=None): self.op, self.payload = "upsert", filas; return self
    def delete(self): self.op = "delete"; return self
    def eq(self, c, v): self.filtros.append((c, v)); return self
    def order(self, c, desc=False): self.orden = (c, desc); return self
    def limit(self, n): self.lim = n; return self

    # --- RLS (réplica de supabase/setup.sql)
    def _uid(self):
        return self.cli.db.tokens.get(self.cli.token)

    def _visible(self, fila, uid):
        db = self.cli.db
        if not db.rls:
            return True
        if uid is None:
            return False
        if self.tabla == "conversaciones":
            return fila["usuario_id"] == uid
        if self.tabla == "mensajes":
            return fila["usuario_id"] == uid and any(c["id"] == fila["conversacion_id"] and c["usuario_id"] == uid
                                                      for c in db.tablas["conversaciones"])
        return True  # corpus: lectura para autenticados

    def _puede_escribir(self, fila, uid):
        db = self.cli.db
        if not db.rls:
            return True
        if uid is None:
            return False
        if self.tabla == "conversaciones":
            return fila.get("usuario_id", uid) == uid
        if self.tabla == "mensajes":
            return fila.get("usuario_id", uid) == uid and any(
                c["id"] == fila["conversacion_id"] and c["usuario_id"] == uid for c in db.tablas["conversaciones"])
        return fila.get("owner_id", uid) == uid

    def execute(self):
        db, uid = self.cli.db, self._uid()
        t = db.tablas[self.tabla]
        db.llamadas.append((self.tabla, self.op, uid))
        if self.op == "insert" or self.op == "upsert":
            filas = self.payload if isinstance(self.payload, list) else [self.payload]
            out = []
            for f in filas:
                f = dict(f)
                if not self._puede_escribir(f, uid):
                    raise Exception("new row violates row-level security policy")
                if self.tabla == "conversaciones":
                    f.setdefault("id", str(uuid.uuid4())); f.setdefault("usuario_id", uid)
                    f.setdefault("created_at", _ahora()); f["updated_at"] = _ahora()
                elif self.tabla == "mensajes":
                    f["id"] = next(db._seq); f.setdefault("usuario_id", uid); f.setdefault("created_at", _ahora())
                    f.setdefault("metadata", {})
                else:
                    f.setdefault("owner_id", uid)
                    t[:] = [x for x in t if not (x["owner_id"] == f["owner_id"] and x["corpus_id"] == f["corpus_id"] and x["chunk_id"] == f["chunk_id"])]
                t.append(f); out.append(dict(f))
            return _Resp(out)
        filas = [f for f in t if self._visible(f, uid) and all(f.get(c) == v for c, v in self.filtros)]
        if self.op == "update":
            for f in filas:
                f.update(self.payload)
            return _Resp([dict(f) for f in filas])
        if self.op == "delete":
            for f in filas:
                if f.get("owner_id", uid) == uid or not db.rls:
                    t.remove(f)
            return _Resp([])
        if self.orden:
            filas.sort(key=lambda f: f[self.orden[0]], reverse=self.orden[1])
        if self.lim:
            filas = filas[: self.lim]
        return _Resp([dict(f) for f in filas])


class _RPC:
    def __init__(self, cli, params):
        self.cli, self.p = cli, params

    def execute(self):
        db = self.cli.db
        uid = db.tokens.get(self.cli.token)
        if uid is None and db.rls:
            raise Exception("permission denied for function")
        q = np.array(self.p["query_embedding"])
        filas = [f for f in db.tablas["clase08_fragmentos"] if f["corpus_id"] == self.p["p_corpus_id"]
                 and f["configuracion"]["modelo"] == self.p["p_modelo"] and f["configuracion"]["revision"] == self.p["p_revision"]]
        vistos, out = set(), []
        for f in sorted(filas, key=lambda f: -float(np.dot(q, np.array(f["embedding"])))):
            if f["chunk_id"] in vistos:
                continue
            vistos.add(f["chunk_id"])
            out.append({"chunk_id": f["chunk_id"], "content": f["content"], "metadata": f["metadata"],
                        "similitud": float(np.dot(q, np.array(f["embedding"])))})
        return _Resp(out[: self.p["match_count"]])


class FakeClient:
    def __init__(self, db):
        self.db, self.token = db, None
        self.auth = _Auth(db)

    @property
    def postgrest(self):
        return _PostgrestShim(self)

    def table(self, nombre): return _Query(self, nombre)
    def rpc(self, nombre, params): return _RPC(self, params)


class _PostgrestShim:
    def __init__(self, cli):
        self._cli = cli

    def auth(self, token):
        self._cli.token = token
        return self


CFG = alm.ConfigSupabase(url="https://demo.supabase.co", clave_publicable="sb_publishable_" + "x" * 24)


@pytest.fixture
def db():
    d = FakeDB()
    d.ana = d.crear_usuario("ana@ejemplo.com", "clave-ana")
    d.beto = d.crear_usuario("beto@ejemplo.com", "clave-beto")
    return d


@pytest.fixture
def almacen(db):
    return alm.Almacen(CFG, fabrica_cliente=lambda: FakeClient(db))
