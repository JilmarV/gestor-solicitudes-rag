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

# ------------------------------------------------------------------ identidad visual
# Gradio 6 recibe tema y CSS en launch(), no en Blocks().
TEMA = gr.themes.Base(
    primary_hue=gr.themes.colors.blue,
    neutral_hue=gr.themes.colors.slate,
    font=[gr.themes.GoogleFont("Schibsted Grotesk"), "system-ui", "sans-serif"],
    radius_size=gr.themes.sizes.radius_sm,
).set(
    body_background_fill="#F3F5F8",
    block_background_fill="transparent",
    block_border_width="0px",
    block_shadow="none",
    input_background_fill="#FFFFFF",
    input_border_color="#D3DAE4",
    input_border_color_focus="#F2C14E",
    button_primary_background_fill="#10223F",
    button_primary_background_fill_hover="#2447A8",
    button_primary_text_color="#FFFFFF",
    button_secondary_background_fill="#FFFFFF",
    button_secondary_border_color="#D3DAE4",
    body_background_fill_dark="#0B1220",
    block_background_fill_dark="transparent",
    input_background_fill_dark="#15213A",
    input_border_color_dark="#2A3A57",
    input_border_color_focus_dark="#F2C14E",
    button_primary_background_fill_dark="#2447A8",
    button_primary_background_fill_hover_dark="#3358BE",
    button_secondary_background_fill_dark="#15213A",
    button_secondary_border_color_dark="#2A3A57",
    button_secondary_text_color_dark="#E6ECF5",
)

ASSETS = Path(__file__).with_name("assets")


def _icono(nombre: str) -> str:
    return str(ASSETS / f"{nombre}.svg")


CABECERA = """
<div class="marca">
  <svg xmlns="http://www.w3.org/2000/svg" width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#F2C14E" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/></svg>
  <h1>Gestor de solicitudes</h1>
</div>
<p>Pregunta por un trámite y recibe la respuesta con la fuente del manual, o consulta en qué estado va tu solicitud.</p>
"""

MARCA = """
<div class="marca">
  <svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#F2C14E" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/></svg>
  <span>Gestor de solicitudes</span>
</div>
"""

EJEMPLOS = ["¿Cómo recupero mi contraseña?", "¿Cuál es el estado de SOL-1003?", "Ya pagué y no aparece, ¿qué hago?",
            "¿Cuánto tarda una solicitud?", "¿Cómo presento una queja?", "¿Qué estados puede tener una solicitud?"]

CSS = """
.gradio-container { max-width: none !important; margin: 0 !important; }
#panel-login, #panel-chat { width: 100%; max-width: 880px; margin: 0 auto !important; padding: 0 16px 16px; }
.sidebar-content { padding-top: 56px !important; }
#cabecera { background: #10223F; margin: 16px auto 18px; padding: 26px 24px 22px; border-radius: 6px; width: min(760px, 100%); }
#cabecera h1 { font-weight: 700; font-size: clamp(1.6rem, 4vw, 2.2rem); letter-spacing: -0.02em; margin: 0; color: #F3F5F8; }
#cabecera .marca { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
#cabecera p { margin: 0; max-width: 56ch; color: #C9D3E3; line-height: 1.5; }
#aviso { width: min(760px, 100%); margin: 0 auto 8px; font-size: 0.88rem; color: #4A5A73; border-left: 3px solid #F2C14E; padding: 2px 0 2px 12px; }
#aviso p { max-width: 70ch; margin: 0; }
.alerta { width: min(760px, 100%); margin: 0 auto 6px; background: #FDECEA; border-left: 3px solid #B3261E; padding: 6px 12px; font-size: 0.85rem; color: #7A1A14; }
.alerta p { margin: 0; }
#form-login { width: 100%; max-width: 420px; margin: 24px auto 0 !important; gap: 12px; }
#form-login h3 { font-weight: 700; letter-spacing: -0.01em; text-align: center; }
button img, button svg { width: 18px; height: 18px; }
#topbar { background: #10223F; border-radius: 6px; padding: 10px 14px; margin: 12px 0; align-items: center; gap: 12px; flex-wrap: nowrap; }
#marca { flex: 1 1 auto; min-width: 0; }
#marca .marca { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.1rem; letter-spacing: -0.01em; color: #F3F5F8; }
#saludo { flex: 0 1 auto; min-width: 0; font-size: 0.85rem; color: #C9D3E3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#marca .marca span { color: #F3F5F8 !important; }
#saludo p, #saludo strong { color: #C9D3E3; margin: 0; }
#saludo a { color: #F2C14E; text-decoration: none; }
#lateral { background: #FFFFFF; }
#lateral button { width: 100%; min-height: 44px; border: 1px solid #D3DAE4; }
#lista .wrap { display: flex; flex-direction: column; gap: 4px; }
#lista label { width: 100%; padding: 9px 10px; border-radius: 6px; border: 1px solid transparent; border-left: 4px solid transparent; background: transparent; line-height: 1.3; cursor: pointer; }
#lista label:hover { background: #F3F5F8; }
#lista label.selected { background: #E8EDF5; border-left-color: #F2C14E; }
#lista input[type=radio] { display: none; }
#chat .user { background: #10223F !important; border: 0 !important; }
#chat .user, #chat .user * { color: #FFFFFF !important; opacity: 1 !important; }
#chat .bot { background: #FFFFFF !important; border: 1px solid #D3DAE4 !important; border-left: 4px solid #F2C14E !important; }
#chat .bot, #chat .bot * { color: #10223F !important; opacity: 1 !important; }
#chat .message .message { border: 0 !important; background: transparent !important; padding: 0 !important; }
#chat .message-content { font-size: 0.97rem; line-height: 1.55; }
#chat .bot h1, #chat .bot h2, #chat .bot h3, #chat .bot h4 { font-size: 0.95rem; font-weight: 700; margin: 14px 0 4px; }
#chat .bot code { font-size: 0.82rem; }
#chat button.example { background: #FFFFFF !important; border: 1px solid #D3DAE4 !important; border-left: 4px solid #F2C14E !important; border-radius: 6px; text-align: left; }
#chat button.example:hover { background: #E8EDF5 !important; }
#chat button.example, #chat button.example * { color: #10223F !important; }
#chat { min-height: 280px; }
#entrada { align-items: end; gap: 10px; }
#entrada button { min-height: 44px; }
#estado, #aviso-pie { font-size: 0.82rem; color: #4A5A73; }
#estado p, #aviso-pie p { margin: 0; }
textarea:focus, input:focus { box-shadow: -3px 0 0 #F2C14E !important; }
button:focus-visible { outline: 2px solid #2447A8; outline-offset: 2px; }
@media (max-width: 640px) { #cabecera { padding: 20px 16px 16px; } #saludo { display: none; } #entrada { flex-wrap: wrap; } }
/* Modo oscuro. Una regla por selector: Gradio antepone su contenedor y, en listas con comas, solo el primer .dark queda bien. */
.dark #cabecera { background: #14213D; border: 1px solid #2A3A57; }
.dark #topbar { background: #14213D; border: 1px solid #2A3A57; }
.dark #aviso { color: #A9B6CC; }
.dark #estado { color: #A9B6CC; }
.dark #aviso-pie { color: #A9B6CC; }
.dark #aviso p { color: #E6ECF5; }
.dark #form-login h3 { color: #E6ECF5; }
.dark .alerta { background: #3A1715; color: #F4B6B0; }
.dark #lateral { background: #111B2E; }
.dark #lateral button { background: #15213A; border: 1px solid #2A3A57; color: #E6ECF5; }
.dark #topbar button { background: #15213A; border: 1px solid #2A3A57; color: #E6ECF5; }
.dark button.secondary img { filter: invert(1) brightness(1.15); }
.dark #lista label { color: #E6ECF5; }
.dark #lista label:hover { background: #1B2A45; }
.dark #lista label.selected { background: #1E2D4A; border-left-color: #F2C14E; }
.dark #chat .user { background: #2447A8 !important; }
.dark #chat .bot { background: #15213A !important; border-color: #2A3A57 !important; border-left-color: #F2C14E !important; color: #E6ECF5 !important; }
.dark #chat .bot * { color: #E6ECF5 !important; }
.dark #chat button.example { background: #15213A !important; border-color: #2A3A57 !important; border-left-color: #F2C14E !important; color: #E6ECF5 !important; }
.dark #chat button.example * { color: #E6ECF5 !important; }
.dark #chat button.example:hover { background: #1B2A45 !important; }
/* sin animaciones: barra y spinner de carga, y los puntos animados del chat */
.progress-text, .progress-level, .generating, .wrap.default .progress-bar { animation: none !important; }
.dot-flashing, .typing, .pending { animation: none !important; }
* { scroll-behavior: auto !important; }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
"""


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
        estado_sesion = gr.State(None)     # SesionUsuario de ESTA pestaña/sesión
        estado_conv = gr.State(None)       # id de la conversación activa

        with gr.Sidebar(open=True, visible=False, width=300, elem_id="lateral") as panel_lateral:
            btn_nueva = gr.Button("Nueva conversación", icon=_icono("nueva"))
            selector = gr.Radio(label="Mis conversaciones", choices=[], value=None, interactive=True, elem_id="lista")

        with gr.Column(visible=True, elem_id="panel-login") as panel_login:
            gr.HTML(CABECERA, elem_id="cabecera")
            if sis.CONFIG["modo_llm"] != "groq":
                gr.Markdown("⚠️ **Modo mock activo** (`MODO_LLM=mock`): no hay modelo real. Úsalo solo para pruebas; la entrega usa Groq.",
                            elem_classes="alerta")
            if sis.CONFIG["mcp_modo"] != "stdio":
                gr.Markdown("⚠️ **MCP_MODO=local**: la herramienta se llama sin servidor MCP. Úsalo solo para pruebas; la entrega usa `stdio`.",
                            elem_classes="alerta")
            gr.Markdown(AVISO, elem_id="aviso")
            with gr.Column(elem_id="form-login"):
                gr.Markdown("### Iniciar sesión")
                email = gr.Textbox(label="Correo", placeholder="usuario@ejemplo.com")
                password = gr.Textbox(label="Contraseña", type="password")
                btn_login = gr.Button("Iniciar sesión", variant="primary", icon=_icono("entrar"))
                msg_login = gr.Markdown("")

        with gr.Column(visible=False, elem_id="panel-chat") as panel_chat:
            with gr.Row(elem_id="topbar"):
                gr.HTML(MARCA, elem_id="marca")
                saludo = gr.Markdown("", elem_id="saludo")
                btn_salir = gr.Button("Salir", scale=0, min_width=100, icon=_icono("salir"))
            chatbot = gr.Chatbot(show_label=False, height="calc(100vh - 400px)", elem_id="chat",
                                 placeholder="**¿En qué te ayudo?**\n\nPregunta por un trámite y te respondo con la fuente del manual.",
                                 examples=[{"text": t} for t in EJEMPLOS])
            with gr.Row(elem_id="entrada"):
                caja = gr.Textbox(show_label=False, placeholder="Escribe tu pregunta o el código de tu solicitud",
                                  lines=2, scale=5, max_length=sis.CONFIG["max_chars_entrada"])
                btn_enviar = gr.Button("Enviar", variant="primary", scale=1, icon=_icono("enviar"))
            estado_msg = gr.Markdown("", elem_id="estado")
            gr.Markdown("Demostración con datos ficticios. No escribas datos personales ni contraseñas.", elem_id="aviso-pie")

        # ---------------------------------------------------------- manejadores
        def _a_login(mensaje: str):
            return {estado_sesion: None, estado_conv: None, panel_login: gr.update(visible=True), panel_chat: gr.update(visible=False),
                    panel_lateral: gr.update(visible=False), msg_login: mensaje, chatbot: [], selector: gr.update(choices=[], value=None), estado_msg: "", saludo: "", password: ""}

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
                    panel_lateral: gr.update(visible=True), msg_login: "", password: "", saludo: f"Sesión: **{ses.email}**",
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

            chat += [{"role": "user", "content": texto}, {"role": "assistant", "content": "Buscando en los manuales…"}]
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

        def usar_ejemplo(evt: gr.SelectData):
            """Pone la sugerencia elegida en la caja; la persona decide cuándo enviarla."""
            valor = evt.value
            return valor.get("text", "") if isinstance(valor, dict) else str(valor)

        def cerrar_sesion():
            return _a_login("Sesión cerrada.")

        # ---------------------------------------------------------- eventos
        comunes = [estado_sesion, estado_conv, panel_login, panel_chat, panel_lateral, msg_login, selector, chatbot, caja, estado_msg, saludo, password]
        btn_login.click(iniciar_sesion, [email, password], comunes, api_name="iniciar_sesion")
        password.submit(iniciar_sesion, [email, password], comunes, api_name=False)
        btn_nueva.click(nueva_conversacion, [estado_sesion], comunes, api_name="nueva_conversacion")
        selector.input(elegir_conversacion, [selector, estado_sesion], comunes, api_name="elegir_conversacion")
        btn_enviar.click(enviar, [caja, chatbot, estado_sesion, estado_conv], comunes, api_name="enviar")
        caja.submit(enviar, [caja, chatbot, estado_sesion, estado_conv], comunes, api_name=False)
        btn_salir.click(cerrar_sesion, None, comunes, api_name="cerrar_sesion")
        chatbot.example_select(usar_ejemplo, None, caja, api_name=False)

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
    demo.launch(server_name=host, server_port=puerto, show_error=False, theme=TEMA, css=CSS,
                allowed_paths=[str(ASSETS)])


if __name__ == "__main__":
    main()
