"""almacenamiento.py — Persistencia en Supabase: identidad, conversaciones, mensajes y corpus.

Reglas de diseño (Clase 12):
  * La identidad viene de Supabase Auth (correo + contraseña de CADA persona).
  * NO existe un cliente global compartido: cada operación crea un cliente efímero
    con el access token de la SesionUsuario que la solicita. Dos usuarios nunca
    comparten estado de autenticación.
  * Solo se usa la clave *publishable*. Las políticas RLS (supabase/setup.sql) son
    la barrera real; además cada método comprueba el propietario antes de leer o
    escribir (defensa en profundidad: conocer un UUID no concede acceso).
  * No se imprimen claves, contraseñas ni tokens.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

_PATRON_SECRETO = re.compile(r"(sb_publishable_\w+|sb_secret_\w+|gsk_\w+|eyJ[\w\-]{20,}\.[\w\-]{10,}\.[\w\-]{10,})")
MARGEN_REFRESCO_S = 60
MAX_MENSAJES_CARGA = 500


def redactar(texto: Any) -> str:
    """Enmascara claves que accidentalmente aparezcan en mensajes de error o logs."""
    return _PATRON_SECRETO.sub("[REDACTADO]", str(texto))


# ----------------------------------------------------------------- errores
class ErrorAlmacenamiento(Exception):
    """Fallo técnico al hablar con Supabase (mensaje ya redactado, sin claves)."""


class SesionInvalida(ErrorAlmacenamiento):
    """Credenciales incorrectas, sesión vencida o sin sesión."""


class AccesoDenegado(ErrorAlmacenamiento):
    """La conversación no existe o no pertenece a la persona autenticada."""


# ----------------------------------------------------------------- configuración
@dataclass(frozen=True)
class ConfigSupabase:
    url: str
    clave_publicable: str


def _rol_de_jwt(clave: str) -> Optional[str]:
    """Si la clave es un JWT heredado (anon/service_role) devuelve su rol; si no, None."""
    partes = clave.split(".")
    if len(partes) != 3:
        return None
    try:
        relleno = "=" * (-len(partes[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(partes[1] + relleno)).get("role")
    except Exception:
        return None


def leer_config(entorno: Optional[dict] = None) -> ConfigSupabase:
    """Lee y valida SUPABASE_URL y SUPABASE_PUBLISHABLE_KEY. Rechaza claves administrativas."""
    env = os.environ if entorno is None else entorno
    url = (env.get("SUPABASE_URL") or "").strip().rstrip("/")
    clave = (env.get("SUPABASE_PUBLISHABLE_KEY") or "").strip()
    if not url or not clave:
        raise ErrorAlmacenamiento("Faltan SUPABASE_URL y/o SUPABASE_PUBLISHABLE_KEY (revisa app/.env o las variables del alojamiento).")
    u = urlparse(url)
    if u.scheme != "https" or not (u.hostname or "").endswith(".supabase.co"):
        raise ErrorAlmacenamiento("SUPABASE_URL debe ser la Project URL HTTPS del proyecto (https://xxxx.supabase.co).")
    if clave.startswith("sb_secret_") or _rol_de_jwt(clave) == "service_role":
        raise ErrorAlmacenamiento("Esa es una clave administrativa. Usa la clave PUBLISHABLE (sb_publishable_…).")
    if not (clave.startswith("sb_publishable_") or _rol_de_jwt(clave) == "anon"):
        raise ErrorAlmacenamiento("SUPABASE_PUBLISHABLE_KEY no parece una clave publicable (debe empezar por sb_publishable_).")
    return ConfigSupabase(url=url, clave_publicable=clave)


# ----------------------------------------------------------------- sesión
@dataclass
class SesionUsuario:
    """Identidad de UNA persona. Vive en el estado de su sesión de Gradio; nunca es global."""
    user_id: str
    email: str
    access_token: str
    refresh_token: str
    expires_at: float  # epoch (s)

    def __repr__(self) -> str:  # evita filtrar tokens en logs/trazas
        return f"SesionUsuario(user_id={self.user_id!r}, email={self.email!r})"


def _nuevo_cliente(cfg: ConfigSupabase):
    from supabase import ClientOptions, create_client
    return create_client(cfg.url, cfg.clave_publicable,
                         options=ClientOptions(persist_session=False, auto_refresh_token=False))


class Almacen:
    """Acceso a Supabase. La instancia solo guarda configuración (URL + clave publicable);
    NINGÚN dato de autenticación de usuarios."""

    def __init__(self, cfg: Optional[ConfigSupabase] = None, fabrica_cliente=None):
        self.cfg = cfg or leer_config()
        self._fabrica = fabrica_cliente or (lambda: _nuevo_cliente(self.cfg))

    # ---- autenticación
    def iniciar_sesion(self, email: str, password: str) -> SesionUsuario:
        email = (email or "").strip()
        if not email or not password:
            raise SesionInvalida("Escribe tu correo y tu contraseña.")
        try:
            r = self._fabrica().auth.sign_in_with_password({"email": email, "password": password})
        except Exception:
            raise SesionInvalida("No se pudo iniciar sesión: revisa correo, contraseña y que el usuario esté confirmado en Supabase Auth.") from None
        if r.user is None or r.session is None:
            raise SesionInvalida("Supabase no devolvió una sesión válida.")
        return SesionUsuario(user_id=str(r.user.id), email=email, access_token=r.session.access_token,
                             refresh_token=r.session.refresh_token,
                             expires_at=float(r.session.expires_at or (time.time() + 3000)))

    def _asegurar_vigente(self, sesion: Optional[SesionUsuario]) -> SesionUsuario:
        if sesion is None:
            raise SesionInvalida("Inicia sesión para continuar.")
        if time.time() < sesion.expires_at - MARGEN_REFRESCO_S:
            return sesion
        try:
            r = self._fabrica().auth.refresh_session(sesion.refresh_token)
        except Exception:
            raise SesionInvalida("Tu sesión expiró. Vuelve a iniciar sesión.") from None
        if r.session is None or r.user is None or str(r.user.id) != sesion.user_id:
            raise SesionInvalida("Tu sesión expiró. Vuelve a iniciar sesión.")
        sesion.access_token = r.session.access_token
        sesion.refresh_token = r.session.refresh_token
        sesion.expires_at = float(r.session.expires_at or (time.time() + 3000))
        return sesion

    def _cliente(self, sesion: Optional[SesionUsuario]):
        """Cliente efímero con el token de ESTA persona. Se descarta al terminar la operación."""
        sesion = self._asegurar_vigente(sesion)
        c = self._fabrica()
        c.postgrest.auth(sesion.access_token)
        return c

    def verificar_sesion(self, sesion: SesionUsuario) -> bool:
        """Valida el token en el servidor de Auth (get_user) y comprueba que sea de la misma persona."""
        sesion = self._asegurar_vigente(sesion)
        try:
            r = self._fabrica().auth.get_user(sesion.access_token)
        except Exception:
            raise SesionInvalida("El servidor de Auth rechazó la sesión.") from None
        return bool(r and r.user and str(r.user.id) == sesion.user_id)

    # ---- helpers
    @staticmethod
    def _uuid_valido(valor: str) -> str:
        try:
            return str(uuid.UUID(str(valor)))
        except (ValueError, AttributeError, TypeError):
            raise AccesoDenegado("Identificador de conversación inválido.") from None

    def _ejecutar(self, operacion, descripcion: str):
        try:
            return operacion()
        except (ErrorAlmacenamiento,):
            raise
        except Exception as e:
            raise ErrorAlmacenamiento(redactar(f"{descripcion}: {type(e).__name__}: {e}")) from None

    def asegurar_propietario(self, sesion: SesionUsuario, conversacion_id: str) -> dict:
        """Devuelve la conversación SOLO si es de esta persona. RLS ya filtra; aquí se vuelve a comprobar."""
        cid = self._uuid_valido(conversacion_id)
        cliente = self._cliente(sesion)
        filas = self._ejecutar(
            lambda: cliente.table("conversaciones").select("id,usuario_id,titulo,created_at,updated_at")
            .eq("id", cid).limit(1).execute().data, "leer conversación")
        if not filas or str(filas[0]["usuario_id"]) != sesion.user_id:
            raise AccesoDenegado("No tienes acceso a esa conversación.")
        return filas[0]

    # ---- conversaciones
    def crear_conversacion(self, sesion: SesionUsuario, titulo: str = "Nueva conversación") -> dict:
        titulo = (titulo or "Nueva conversación").strip().replace("\n", " ")[:80] or "Nueva conversación"
        cliente = self._cliente(sesion)
        datos = self._ejecutar(
            lambda: cliente.table("conversaciones").insert({"usuario_id": sesion.user_id, "titulo": titulo}).execute().data,
            "crear conversación")
        if not datos:
            raise ErrorAlmacenamiento("Supabase no confirmó la creación de la conversación.")
        return datos[0]

    def listar_conversaciones(self, sesion: SesionUsuario, limite: int = 50) -> list[dict]:
        cliente = self._cliente(sesion)
        filas = self._ejecutar(
            lambda: cliente.table("conversaciones").select("id,usuario_id,titulo,created_at,updated_at")
            .eq("usuario_id", sesion.user_id).order("updated_at", desc=True).limit(limite).execute().data,
            "listar conversaciones")
        return [f for f in filas if str(f["usuario_id"]) == sesion.user_id]

    def renombrar_conversacion(self, sesion: SesionUsuario, conversacion_id: str, titulo: str) -> None:
        conv = self.asegurar_propietario(sesion, conversacion_id)
        titulo = (titulo or "").strip().replace("\n", " ")[:80]
        if not titulo:
            return
        cliente = self._cliente(sesion)
        self._ejecutar(lambda: cliente.table("conversaciones").update({"titulo": titulo}).eq("id", conv["id"]).execute(),
                       "renombrar conversación")

    # ---- mensajes
    def cargar_mensajes(self, sesion: SesionUsuario, conversacion_id: str, limite: int = MAX_MENSAJES_CARGA) -> list[dict]:
        conv = self.asegurar_propietario(sesion, conversacion_id)
        cliente = self._cliente(sesion)
        filas = self._ejecutar(
            lambda: cliente.table("mensajes").select("id,rol,contenido,metadata,created_at")
            .eq("conversacion_id", conv["id"]).order("id").limit(limite).execute().data, "cargar mensajes")
        return [{"id": f["id"], "rol": f["rol"], "contenido": f["contenido"],
                 "metadata": f.get("metadata") or {}, "created_at": f.get("created_at")} for f in filas]

    def guardar_mensaje(self, sesion: SesionUsuario, conversacion_id: str, rol: str, contenido: str,
                        metadata: Optional[dict] = None) -> dict:
        if rol not in ("user", "assistant"):
            raise ErrorAlmacenamiento("Rol de mensaje inválido.")
        contenido = (contenido or "").strip()
        if not contenido:
            raise ErrorAlmacenamiento("No se guarda un mensaje vacío.")
        conv = self.asegurar_propietario(sesion, conversacion_id)
        cliente = self._cliente(sesion)
        fila = {"conversacion_id": conv["id"], "usuario_id": sesion.user_id, "rol": rol,
                "contenido": contenido[:8000], "metadata": metadata or {}}
        datos = self._ejecutar(lambda: cliente.table("mensajes").insert(fila).execute().data, "guardar mensaje")
        if not datos:
            raise ErrorAlmacenamiento("Supabase no confirmó el guardado del mensaje.")
        return datos[0]

    # ---- corpus del RAG (lectura compartida entre usuarios autenticados)
    def leer_config_corpus(self, sesion: SesionUsuario, corpus_id: str) -> dict:
        """Lee modelo y revisión de embeddings con que se indexó el corpus (una fila basta)."""
        cliente = self._cliente(sesion)
        filas = self._ejecutar(
            lambda: cliente.table("clase08_fragmentos").select("configuracion").eq("corpus_id", corpus_id)
            .limit(1).execute().data, "leer configuración del corpus")
        if not filas:
            raise ErrorAlmacenamiento("El corpus está vacío o no es legible: ejecuta app/preparar_corpus.py y revisa supabase/setup.sql.")
        return filas[0]["configuracion"]

    def buscar_fragmentos(self, sesion: SesionUsuario, vector, m: int, corpus_id: str, modelo: str, revision: str) -> list[dict]:
        cliente = self._cliente(sesion)
        vec = vector.tolist() if hasattr(vector, "tolist") else list(vector)
        return self._ejecutar(
            lambda: cliente.rpc("clase08_buscar_fragmentos", {
                "query_embedding": vec, "p_corpus_id": corpus_id, "p_modelo": modelo,
                "p_revision": revision, "match_count": m}).execute().data or [], "buscar fragmentos")

    # ---- carga del corpus (la usa app/preparar_corpus.py; la aplicación en sí solo LEE el corpus)
    def leer_indice_propio(self, sesion: SesionUsuario, corpus_id: str) -> list[dict]:
        """Fragmentos de este corpus que pertenecen a ESTA persona (para decidir si hay que re-embeber)."""
        cliente = self._cliente(sesion)
        return self._ejecutar(
            lambda: cliente.table("clase08_fragmentos").select("chunk_id,metadata,configuracion")
            .eq("corpus_id", corpus_id).eq("owner_id", sesion.user_id).limit(1000).execute().data or [],
            "leer índice propio")

    def upsert_fragmentos(self, sesion: SesionUsuario, filas: list[dict]) -> None:
        cliente = self._cliente(sesion)
        con_dueno = [{**f, "owner_id": sesion.user_id} for f in filas]
        for i in range(0, len(con_dueno), 50):
            lote = con_dueno[i:i + 50]
            self._ejecutar(lambda lote=lote: cliente.table("clase08_fragmentos").upsert(
                lote, on_conflict="owner_id,corpus_id,chunk_id").execute(), "guardar fragmentos")

    def borrar_fragmentos_sobrantes(self, sesion: SesionUsuario, corpus_id: str, ids_vigentes: list[str]) -> int:
        cliente = self._cliente(sesion)
        sobran = {f["chunk_id"] for f in self.leer_indice_propio(sesion, corpus_id)} - set(ids_vigentes)
        for cid in sobran:
            self._ejecutar(lambda cid=cid: cliente.table("clase08_fragmentos").delete()
                           .eq("corpus_id", corpus_id).eq("owner_id", sesion.user_id).eq("chunk_id", cid).execute(),
                           "borrar fragmento sobrante")
        return len(sobran)
