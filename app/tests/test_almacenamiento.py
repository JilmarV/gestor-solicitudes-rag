import httpx
import pytest

import almacenamiento as alm
from conftest import CFG, FakeClient


# ---------------------------------------------------------------- configuración y secretos
def test_config_rechaza_claves_administrativas():
    base = {"SUPABASE_URL": "https://abc.supabase.co"}
    with pytest.raises(alm.ErrorAlmacenamiento):
        alm.leer_config({**base, "SUPABASE_PUBLISHABLE_KEY": "sb_secret_" + "a" * 30})
    import base64, json
    jwt = lambda rol: ".".join([base64.urlsafe_b64encode(b"{}").decode().strip("="),
                               base64.urlsafe_b64encode(json.dumps({"role": rol}).encode()).decode().strip("="), "firma"])
    with pytest.raises(alm.ErrorAlmacenamiento):
        alm.leer_config({**base, "SUPABASE_PUBLISHABLE_KEY": jwt("service_role")})
    assert alm.leer_config({**base, "SUPABASE_PUBLISHABLE_KEY": jwt("anon")}).url == "https://abc.supabase.co"
    assert alm.leer_config({**base, "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_" + "a" * 20}).clave_publicable.startswith("sb_publishable_")


@pytest.mark.parametrize("url", ["", "http://abc.supabase.co", "https://example.com", "abc.supabase.co"])
def test_config_rechaza_url_invalida(url):
    with pytest.raises(alm.ErrorAlmacenamiento):
        alm.leer_config({"SUPABASE_URL": url, "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_" + "a" * 20})


def test_config_falta_clave():
    with pytest.raises(alm.ErrorAlmacenamiento):
        alm.leer_config({"SUPABASE_URL": "https://abc.supabase.co"})


def test_redactar_enmascara_claves():
    assert "gsk_" not in alm.redactar("fallo con gsk_ABCDEFGH123456")
    assert "sb_publishable_" not in alm.redactar("clave sb_publishable_abcdefghijk")
    assert "[REDACTADO]" in alm.redactar("sb_secret_abcdefghijklmn")


def test_repr_de_sesion_no_filtra_tokens(almacen):
    s = almacen.iniciar_sesion("ana@ejemplo.com", "clave-ana")
    assert s.access_token not in repr(s) and s.refresh_token not in repr(s)


# ---------------------------------------------------------------- autenticación
def test_login_correcto_e_incorrecto(almacen, db):
    s = almacen.iniciar_sesion("ana@ejemplo.com", "clave-ana")
    assert s.user_id == db.ana and almacen.verificar_sesion(s)
    with pytest.raises(alm.SesionInvalida):
        almacen.iniciar_sesion("ana@ejemplo.com", "mala")
    with pytest.raises(alm.SesionInvalida):
        almacen.iniciar_sesion("", "")
    with pytest.raises(alm.SesionInvalida):
        almacen.crear_conversacion(None)


def test_refresco_de_token_cuando_vence(almacen, db):
    s = almacen.iniciar_sesion("ana@ejemplo.com", "clave-ana")
    viejo = s.access_token
    s.expires_at = 0                          # token vencido
    almacen.listar_conversaciones(s)          # debe refrescar solo
    assert s.access_token != viejo and s.user_id == db.ana


def test_refresco_fallido_pide_nuevo_login(almacen):
    s = almacen.iniciar_sesion("ana@ejemplo.com", "clave-ana")
    s.expires_at, s.refresh_token = 0, "invalido"
    with pytest.raises(alm.SesionInvalida):
        almacen.listar_conversaciones(s)


# ---------------------------------------------------------------- historial: persistencia y orden
def test_crear_listar_cargar_en_orden(almacen):
    s = almacen.iniciar_sesion("ana@ejemplo.com", "clave-ana")
    c1 = almacen.crear_conversacion(s, "Primera")
    c2 = almacen.crear_conversacion(s, "Segunda")              # crear otra NO borra la anterior
    assert {c["id"] for c in almacen.listar_conversaciones(s)} == {c1["id"], c2["id"]}
    for i in range(3):
        almacen.guardar_mensaje(s, c1["id"], "user", f"pregunta {i}")
        almacen.guardar_mensaje(s, c1["id"], "assistant", f"respuesta {i}", {"estado": "respondida", "fuentes": [{"chunk_id": "acceso-01"}]})
    msgs = almacen.cargar_mensajes(s, c1["id"])
    assert [m["contenido"] for m in msgs] == ["pregunta 0", "respuesta 0", "pregunta 1", "respuesta 1", "pregunta 2", "respuesta 2"]
    assert msgs[1]["metadata"]["fuentes"][0]["chunk_id"] == "acceso-01"
    assert almacen.cargar_mensajes(s, c2["id"]) == []          # dos conversaciones de la misma persona, separadas


def test_historial_sobrevive_a_nueva_sesion_y_nuevo_objeto(almacen, db):
    """Cerrar sesión / reiniciar la aplicación = nuevo Almacen + nueva sesión; los datos siguen en la BD."""
    s = almacen.iniciar_sesion("ana@ejemplo.com", "clave-ana")
    c = almacen.crear_conversacion(s, "Persistente")
    almacen.guardar_mensaje(s, c["id"], "user", "hola")
    reiniciado = alm.Almacen(CFG, fabrica_cliente=lambda: FakeClient(db))
    s2 = reiniciado.iniciar_sesion("ana@ejemplo.com", "clave-ana")
    assert s2.access_token != s.access_token
    assert [m["contenido"] for m in reiniciado.cargar_mensajes(s2, c["id"])] == ["hola"]


def test_mensaje_vacio_o_rol_invalido(almacen):
    s = almacen.iniciar_sesion("ana@ejemplo.com", "clave-ana")
    c = almacen.crear_conversacion(s)
    for rol, txt in (("user", "  "), ("system", "x"), ("tool", "x")):
        with pytest.raises(alm.ErrorAlmacenamiento):
            almacen.guardar_mensaje(s, c["id"], rol, txt)


# ---------------------------------------------------------------- aislamiento entre usuarios
@pytest.mark.parametrize("rls", [True, False])
def test_usuario_no_lee_ni_escribe_conversacion_ajena(almacen, db, rls):
    """Con RLS activo el fallo viene de la BD; con RLS simulado como ausente, el control de propietario
    en Python sigue impidiendo el acceso (defensa en profundidad)."""
    db.rls = rls
    ana = almacen.iniciar_sesion("ana@ejemplo.com", "clave-ana")
    beto = almacen.iniciar_sesion("beto@ejemplo.com", "clave-beto")
    conv_ana = almacen.crear_conversacion(ana, "Privada de Ana")
    almacen.guardar_mensaje(ana, conv_ana["id"], "user", "secreto de Ana")
    with pytest.raises(alm.AccesoDenegado):
        almacen.cargar_mensajes(beto, conv_ana["id"])                      # conoce el UUID y aun así no lee
    with pytest.raises(alm.AccesoDenegado):
        almacen.guardar_mensaje(beto, conv_ana["id"], "user", "intruso")   # ni inserta
    with pytest.raises(alm.AccesoDenegado):
        almacen.renombrar_conversacion(beto, conv_ana["id"], "hackeada")
    assert almacen.listar_conversaciones(beto) == []
    assert [m["contenido"] for m in almacen.cargar_mensajes(ana, conv_ana["id"])] == ["secreto de Ana"]
    assert len(db.tablas["mensajes"]) == 1


def test_uuid_invalido_no_llega_a_la_base(almacen, db):
    s = almacen.iniciar_sesion("ana@ejemplo.com", "clave-ana")
    n = len(db.llamadas)
    for malo in ["' or 1=1 --", "123", "", None]:
        with pytest.raises(alm.AccesoDenegado):
            almacen.cargar_mensajes(s, malo)
    assert len(db.llamadas) == n


def test_cada_operacion_usa_el_token_de_su_persona(almacen, db):
    """No hay cliente global: operaciones intercaladas de dos personas usan cada una su identidad."""
    ana = almacen.iniciar_sesion("ana@ejemplo.com", "clave-ana")
    beto = almacen.iniciar_sesion("beto@ejemplo.com", "clave-beto")
    db.llamadas.clear()
    for _ in range(3):
        almacen.crear_conversacion(ana, "A")
        almacen.crear_conversacion(beto, "B")
    por_op = [uid for (_t, op, uid) in db.llamadas if op == "insert"]
    assert por_op == [db.ana, db.beto] * 3
    assert {c["usuario_id"] for c in almacen.listar_conversaciones(ana)} == {db.ana}
    assert {c["usuario_id"] for c in almacen.listar_conversaciones(beto)} == {db.beto}


# ---------------------------------------------------------------- corpus
def test_corpus_lectura_compartida_pero_escritura_propia(almacen, db):
    ana = almacen.iniciar_sesion("ana@ejemplo.com", "clave-ana")
    beto = almacen.iniciar_sesion("beto@ejemplo.com", "clave-beto")
    cfg = {"modelo": "m", "revision": "r"}
    fila = lambda cid: {"corpus_id": "c", "chunk_id": cid, "content": "x", "metadata": {}, "configuracion": cfg, "embedding": [1.0, 0.0]}
    almacen.upsert_fragmentos(ana, [fila("a-01"), fila("a-02")])
    assert almacen.leer_config_corpus(beto, "c") == cfg                    # Beto puede LEER el corpus de Ana
    r = almacen.buscar_fragmentos(beto, [1.0, 0.0], 5, "c", "m", "r")
    assert {x["chunk_id"] for x in r} == {"a-01", "a-02"}
    assert almacen.leer_indice_propio(beto, "c") == []                     # pero no es suyo
    with pytest.raises(alm.ErrorAlmacenamiento):
        almacen.leer_config_corpus(beto, "otro-corpus")                    # corpus vacío -> error claro
    assert almacen.borrar_fragmentos_sobrantes(ana, "c", ["a-01"]) == 1


# ---------------------------------------------------------------- el cliente REAL de supabase-py usa el token del usuario
def test_cliente_real_envia_authorization_del_usuario():
    """Sin red: transporte simulado. Confirma que el Bearer es el del usuario y que apikey es la publicable."""
    vistas = []

    def manejador(req):
        vistas.append((req.url.path, req.headers.get("authorization"), req.headers.get("apikey")))
        return httpx.Response(200, json=[])

    from supabase import ClientOptions, create_client
    def fabrica():
        return create_client(CFG.url, CFG.clave_publicable, options=ClientOptions(
            persist_session=False, auto_refresh_token=False, httpx_client=httpx.Client(transport=httpx.MockTransport(manejador))))

    a = alm.Almacen(CFG, fabrica_cliente=fabrica)
    import time
    ses = lambda tok, uid: alm.SesionUsuario(uid, f"{uid}@x.com", tok, "r", time.time() + 3000)
    a.listar_conversaciones(ses("TOKEN_ANA", "ana"))
    a.listar_conversaciones(ses("TOKEN_BETO", "beto"))
    assert vistas[0][1] == "Bearer TOKEN_ANA" and vistas[1][1] == "Bearer TOKEN_BETO"
    assert all(v[2] == CFG.clave_publicable for v in vistas)
