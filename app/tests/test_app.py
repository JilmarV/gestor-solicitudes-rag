"""Prueba de la interfaz de extremo a extremo SIN red: Gradio real + Almacen real sobre un Supabase falso."""
import pytest
from gradio_client import Client

import almacenamiento as alm
import app as app_mod
import sistema as sis
from conftest import CFG, FakeClient
from test_sistema import FakeEmbedder, FakeStore


@pytest.fixture
def servidor(db, monkeypatch):
    monkeypatch.setitem(sis.CONFIG, "modo_llm", "mock")
    monkeypatch.setitem(sis.CONFIG, "mcp_modo", "local")
    almacen = alm.Almacen(CFG, fabrica_cliente=lambda: FakeClient(db))
    sistema = sis.Sistema(FakeStore(), embedder=FakeEmbedder(), mcp=sis.ClienteMCP(modo="local"))
    demo = app_mod.crear_app(almacen, sistema)
    _, url, _ = demo.launch(server_name="127.0.0.1", server_port=None, prevent_thread_lock=True, quiet=True)
    yield url, db
    demo.close()


def _txt(m):
    c = m["content"]
    return c if isinstance(c, str) else "".join(p.get("text", "") for p in c)


def _chat(res):
    """Devuelve el chat como lista de {'role','content': str} (gradio_client entrega el contenido por partes)."""
    bruto = next((x for x in res if isinstance(x, list) and (not x or isinstance(x[0], dict))), [])
    return [{"role": m["role"], "content": _txt(m)} for m in bruto]


def test_flujo_dos_usuarios_historial_y_aislamiento(servidor):
    url, db = servidor
    ana, beto = Client(url, verbose=False), Client(url, verbose=False)

    # login incorrecto no abre el chat
    r = ana.predict("ana@ejemplo.com", "mala", api_name="/iniciar_sesion")
    assert any(isinstance(x, str) and "No se pudo iniciar sesión" in x for x in r)
    assert not db.tablas["conversaciones"]

    # Ana entra y conversa (conversación 1)
    ana.predict("ana@ejemplo.com", "clave-ana", api_name="/iniciar_sesion")
    r = ana.predict("¿Dónde pido una constancia y qué datos debo indicar?", [], api_name="/enviar")
    chat = _chat(r)
    assert chat[0]["content"].startswith("¿Dónde pido") and "constancias.md" in str(chat[-1]["content"])

    # Ana crea una 2.ª conversación y pregunta otra cosa; la primera NO se borra
    ana.predict(api_name="/nueva_conversacion")
    ana.predict("¿Cuál es el estado de SOL-1003?", [], api_name="/enviar")
    convs = db.tablas["conversaciones"]
    assert len(convs) == 2 and {c["usuario_id"] for c in convs} == {db.ana}
    assert len(db.tablas["mensajes"]) == 4

    # Beto entra: no ve nada de Ana
    beto.predict("beto@ejemplo.com", "clave-beto", api_name="/iniciar_sesion")
    beto.predict("¿Dónde pido una constancia y qué datos debo indicar?", [], api_name="/enviar")
    assert {c["usuario_id"] for c in db.tablas["conversaciones"]} == {db.ana, db.beto}
    ids_ana = {c["id"] for c in convs if c["usuario_id"] == db.ana}
    assert all(m["usuario_id"] == db.beto for m in db.tablas["mensajes"] if m["conversacion_id"] not in ids_ana)

    # Beto intenta abrir una conversación de Ana por su UUID desde el selector (valor controlado por el cliente)
    id_ana = next(iter(ids_ana))
    antes = len(db.tablas["mensajes"])
    # Gradio ya rechaza un valor que no está en las opciones de ESA persona; si pasara, el control de
    # propietario de almacenamiento.py lo frenaría (cubierto en test_almacenamiento.py).
    from gradio_client.exceptions import AppError
    try:
        r = beto.predict(id_ana, api_name="/elegir_conversacion")
        assert _chat(r) == [] or not any("constancias.md" in m["content"] for m in _chat(r))
    except AppError as e:
        assert "not in the list of choices" in str(e)
    assert len(db.tablas["mensajes"]) == antes

    # "Cerrar sesión y reiniciar": un cliente nuevo de Ana recupera su historial desde la BD
    ana2 = Client(url, verbose=False)
    r = ana2.predict("ana@ejemplo.com", "clave-ana", api_name="/iniciar_sesion")
    recuperado = _chat(r)
    assert recuperado and any("SOL-1003" in m["content"] or "pendiente de documentos" in m["content"] for m in recuperado)


def test_sin_sesion_no_hay_acceso(servidor):
    url, db = servidor
    c = Client(url, verbose=False)
    c.predict("hola", [], api_name="/enviar")
    assert db.tablas["mensajes"] == [] and db.tablas["conversaciones"] == []
