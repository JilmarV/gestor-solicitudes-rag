"""app.py — Interfaz Gradio del Gestor de solicitudes.

Responsabilidades: pantalla de ingreso (Supabase Auth), lista de conversaciones, chat con fuentes,
estado de CADA sesión (gr.State). La lógica del proyecto vive en sistema.py; la persistencia en
almacenamiento.py. Aquí no se duplica ninguna de las dos.

Ejecución local (desde app/):   python app.py          → http://127.0.0.1:7860
Alojamiento (Render):           GRADIO_SERVER_NAME=0.0.0.0 y PORT lo suministra la plataforma.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"), override=False)   # las variables del alojamiento tienen prioridad
except ImportError:  # python-dotenv es opcional si las variables ya están en el entorno
    pass

import gradio as gr

import almacenamiento as alm
import sistema as sis

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("gestor")

TITULO_DEFECTO = "Nueva conversación"
AVISO = ("Los datos y manuales de esta demostración son **ficticios**. No escribas datos personales reales "
         "ni contraseñas. Cada persona ve solo sus propias conversaciones.")


# ------------------------------------------------------------------ utilidades de presentación
def _etiqueta(c: dict) -> str:
    fecha = str(c.get("updated_at") or "")[:16].replace("T", " ")
    return f"{c['titulo']} · {fecha}"


def _opciones(convs: list[dict]) -> list[tuple[str, str]]:
    return [(_etiqueta(c), c["id"]) for c in convs]


def _a_chat(mensajes: list[dict]) -> list[dict]:
    """Reconstruye lo que ve la persona a partir de lo guardado (incluye fuentes del asistente)."""
    chat = []
    for m in mensajes:
        if m["rol"] == "assistant":
            meta = m.get("metadata") or {}
            contenido = sis.formatear_respuesta({"respuesta": m["contenido"], "fuentes": meta.get("fuentes") or [],
                                                 "limitacion": meta.get("limitacion"), "ruta": meta.get("ruta")})
        else:
            contenido = m["contenido"]
        chat.append({"role": m["rol"], "content": contenido})
    return chat


def crear_app(almacen: Optional[alm.Almacen] = None, sistema: Optional[sis.Sistema] = None) -> gr.Blocks:
    almacen = almacen or alm.Almacen()
    sistema = sistema or sis.Sistema(almacen)
    ventana = sis.CONFIG["ventana_historial"]

    with gr.Blocks(title="Gestor de solicitudes") as demo:
        gr.Markdown("# Gestor de solicitudes\nClasifica solicitudes, responde con fuentes de los manuales y consulta el estado de una solicitud.")
        if sis.CONFIG["modo_llm"] != "groq":
            gr.Markdown("⚠️ **MODO MOCK ACTIVO** (`MODO_LLM=mock`): sin modelo real; solo para pruebas. No es la configuración de entrega.")
        if sis.CONFIG["mcp_modo"] != "stdio":
            gr.Markdown("⚠️ **MCP_MODO=local**: la herramienta se llama sin servidor MCP; solo para pruebas. La entrega usa `stdio`.")
        gr.Markdown(AVISO)

        estado_sesion = gr.State(None)     # SesionUsuario de ESTA pestaña/sesión
        estado_conv = gr.State(None)       # id de la conversación activa

        with gr.Column(visible=True) as panel_login:
            gr.Markdown("### Iniciar sesión")
            email = gr.Textbox(label="Correo", placeholder="usuario@ejemplo.com")
            password = gr.Textbox(label="Contraseña", type="password")
            btn_login = gr.Button("Entrar", variant="primary")
            msg_login = gr.Markdown("")

        with gr.Column(visible=False) as panel_chat:
            saludo = gr.Markdown("")
            with gr.Row():
                selector = gr.Dropdown(label="Mis conversaciones", choices=[], value=None, interactive=True, scale=4)
                btn_nueva = gr.Button("➕ Nueva conversación", scale=1)
                btn_salir = gr.Button("Cerrar sesión", scale=1)
            chatbot = gr.Chatbot(label="Conversación", height=420)
            with gr.Row():
                caja = gr.Textbox(label="Tu mensaje", placeholder="Ej.: ¿Dónde pido una constancia? · ¿Cuál es el estado de SOL-1003?",
                                  lines=2, scale=5, max_length=sis.CONFIG["max_chars_entrada"])
                btn_enviar = gr.Button("Enviar", variant="primary", scale=1)
            estado_msg = gr.Markdown("")

        # ---------------------------------------------------------- manejadores
        def _a_login(mensaje: str):
            return {estado_sesion: None, estado_conv: None, panel_login: gr.update(visible=True), panel_chat: gr.update(visible=False),
                    msg_login: mensaje, chatbot: [], selector: gr.update(choices=[], value=None), estado_msg: "", saludo: "", password: ""}

        def iniciar_sesion(correo, clave):
            try:
                ses = almacen.iniciar_sesion(correo, clave)
                convs = almacen.listar_conversaciones(ses)
                conv_id = convs[0]["id"] if convs else None
                chat = _a_chat(almacen.cargar_mensajes(ses, conv_id)[-200:]) if conv_id else []
            except alm.ErrorAlmacenamiento as e:
                log.warning("inicio de sesión fallido: %s", alm.redactar(e))
                return _a_login(f"⚠️ {alm.redactar(e)}")
            log.info("sesión iniciada user_id=%s", ses.user_id)
            return {estado_sesion: ses, estado_conv: conv_id, panel_login: gr.update(visible=False), panel_chat: gr.update(visible=True),
                    msg_login: "", password: "", saludo: f"Sesión: **{ses.email}**",
                    selector: gr.update(choices=_opciones(convs), value=conv_id), chatbot: chat,
                    estado_msg: "Conversaciones cargadas desde Supabase." if convs else "Aún no tienes conversaciones: escribe tu primer mensaje."}

        def nueva_conversacion(ses):
            try:
                conv = almacen.crear_conversacion(ses, TITULO_DEFECTO)
                convs = almacen.listar_conversaciones(ses)
            except alm.SesionInvalida as e:
                return _a_login(f"⚠️ {alm.redactar(e)}")
            except alm.ErrorAlmacenamiento as e:
                return {estado_msg: f"⚠️ No se pudo crear la conversación: {alm.redactar(e)}"}
            return {estado_conv: conv["id"], chatbot: [], selector: gr.update(choices=_opciones(convs), value=conv["id"]),
                    estado_msg: "Conversación nueva creada. Las anteriores se conservan."}

        def elegir_conversacion(conv_id, ses):
            if not conv_id:
                return {estado_conv: None, chatbot: []}
            try:
                chat = _a_chat(almacen.cargar_mensajes(ses, conv_id)[-200:])
            except alm.SesionInvalida as e:
                return _a_login(f"⚠️ {alm.redactar(e)}")
            except alm.ErrorAlmacenamiento as e:
                return {estado_msg: f"⚠️ {alm.redactar(e)}"}
            return {estado_conv: conv_id, chatbot: chat, estado_msg: ""}

        def enviar(texto, chat, ses, conv_id):
            texto = (texto or "").strip()
            if not texto:
                yield {estado_msg: "Escribe un mensaje."}
                return
            if ses is None:
                yield _a_login("Inicia sesión para continuar.")
                return
            chat = list(chat or [])
            try:
                if conv_id is None:
                    conv_id = almacen.crear_conversacion(ses, texto[:60])["id"]
                    previo: list[dict] = []
                else:
                    previo = almacen.cargar_mensajes(ses, conv_id)
                    if not previo:
                        almacen.renombrar_conversacion(ses, conv_id, texto[:60])
                historial = previo[-ventana:]
                almacen.guardar_mensaje(ses, conv_id, "user", texto)
            except alm.SesionInvalida as e:
                yield _a_login(f"⚠️ {alm.redactar(e)}")
                return
            except alm.ErrorAlmacenamiento as e:
                yield {estado_msg: f"⚠️ No se pudo guardar tu mensaje, por eso no lo envié al sistema: {alm.redactar(e)}"}
                return

            chat += [{"role": "user", "content": texto}, {"role": "assistant", "content": "⏳ Procesando…"}]
            yield {chatbot: chat, caja: "", estado_conv: conv_id, estado_msg: ""}

            r = sistema.atender(texto, ses, historial)
            aviso = ""
            try:
                almacen.guardar_mensaje(ses, conv_id, "assistant", r["respuesta"], sis.metadata_para_guardar(r))
            except alm.SesionInvalida as e:
                yield _a_login(f"⚠️ {alm.redactar(e)}")
                return
            except alm.ErrorAlmacenamiento as e:
                log.error("no se guardó la respuesta: %s", alm.redactar(e))
                aviso = "\n\n⚠️ _Esta respuesta no se pudo guardar en tu historial._"
            chat[-1] = {"role": "assistant", "content": sis.formatear_respuesta(r) + aviso}
            try:
                convs = almacen.listar_conversaciones(ses)
                sel = gr.update(choices=_opciones(convs), value=conv_id)
            except alm.ErrorAlmacenamiento:
                sel = gr.update()
            log.info("solicitud atendida ruta=%s estado=%s latencia_ms=%s", r["ruta"], r["estado"], r["latencia_ms"])
            yield {chatbot: chat, selector: sel, estado_msg: "" if not aviso else "⚠️ Respuesta no guardada."}

        def cerrar_sesion():
            return _a_login("Sesión cerrada.")

        # ---------------------------------------------------------- eventos
        comunes = [estado_sesion, estado_conv, panel_login, panel_chat, msg_login, selector, chatbot, caja, estado_msg, saludo, password]
        btn_login.click(iniciar_sesion, [email, password], comunes, api_name="iniciar_sesion")
        password.submit(iniciar_sesion, [email, password], comunes, api_name=False)
        btn_nueva.click(nueva_conversacion, [estado_sesion], comunes, api_name="nueva_conversacion")
        selector.input(elegir_conversacion, [selector, estado_sesion], comunes, api_name="elegir_conversacion")
        btn_enviar.click(enviar, [caja, chatbot, estado_sesion, estado_conv], comunes, api_name="enviar")
        caja.submit(enviar, [caja, chatbot, estado_sesion, estado_conv], comunes, api_name=False)
        btn_salir.click(cerrar_sesion, None, comunes, api_name="cerrar_sesion")

    demo.queue(default_concurrency_limit=4, max_size=20)
    return demo


def main() -> None:
    try:
        almacen = alm.Almacen()                       # valida SUPABASE_URL y la clave publicable
        if sis.CONFIG["modo_llm"] == "groq" and not os.environ.get("GROQ_API_KEY"):
            raise alm.ErrorAlmacenamiento("Falta GROQ_API_KEY (o usa MODO_LLM=mock solo para pruebas).")
    except alm.ErrorAlmacenamiento as e:
        log.error("Configuración incompleta: %s", e)
        sys.exit(1)
    demo = crear_app(almacen)
    host = os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1")
    puerto = int(os.environ.get("PORT", "7860"))
    log.info("Arrancando en %s:%s (modo_llm=%s, mcp=%s)", host, puerto, sis.CONFIG["modo_llm"], sis.CONFIG["mcp_modo"])
    demo.launch(server_name=host, server_port=puerto, show_error=False)


if __name__ == "__main__":
    main()
