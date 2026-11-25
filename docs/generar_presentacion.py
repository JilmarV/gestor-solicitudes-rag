"""generar_presentacion.py — Genera app/presentacion_proyecto.pdf (16:9) con reportlab.

Uso (desde la raíz del repositorio):
    pip install -r docs/requirements-docs.txt
    python docs/generar_presentacion.py [--url https://TU-APP.onrender.com]

Las cifras de evaluación son las de evidencias/resultados_colab_segundo_corte.md. Si existe
evidencias/resultados_app.json (lo crea app/verificar_entrega.py) se muestran los resultados reales de la aplicación;
si no existe, la diapositiva lo dice explícitamente (no se inventan resultados).
Solo usa fuentes estándar del PDF (Helvetica): por eso no hay símbolos fuera de Latin-1.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

RAIZ = Path(__file__).resolve().parent.parent
W, H = 960, 540
TEAL, INK, GRIS, CLARO, AMBAR, ROJO = HexColor("#0F766E"), HexColor("#1F2937"), HexColor("#6B7280"), HexColor("#E6F2F1"), HexColor("#B45309"), HexColor("#B91C1C")
FONT, BOLD = "Helvetica", "Helvetica-Bold"


class Pres:
    def __init__(self, ruta: Path):
        self.c = canvas.Canvas(str(ruta), pagesize=(W, H))
        self.c.setTitle("Gestor de solicitudes - Presentación del proyecto")
        self.c.setAuthor("Jilmar Said Veloza Páez y Andrés Felipe Galvis Téllez")
        self.n = 0

    def nueva(self, titulo: str, subtitulo: str = ""):
        if self.n:
            self.c.showPage()
        self.n += 1
        c = self.c
        c.setFillColor(TEAL); c.rect(0, H - 70, W, 70, stroke=0, fill=1)
        c.setFillColor(white); c.setFont(BOLD, 28); c.drawString(40, H - 46, titulo)
        if subtitulo:
            c.setFont(FONT, 13); c.drawRightString(W - 40, H - 44, subtitulo)
        c.setFillColor(GRIS); c.setFont(FONT, 10)
        c.drawString(40, 18, "Gestor de solicitudes - IA Generativa y Sistemas Inteligentes - EAM 2026-II")
        c.drawRightString(W - 40, 18, str(self.n))

    def texto(self, x, y, t, size=16, font=FONT, color=INK, ancho=880, leading=None) -> float:
        c = self.c; leading = leading or size * 1.3
        c.setFillColor(color); c.setFont(font, size)
        for linea in simpleSplit(t, font, size, ancho):
            c.drawString(x, y, linea); y -= leading
        return y

    def bullets(self, items, x=50, y=H - 105, size=16, ancho=860, gap=8):
        for it in items:
            sub = it.startswith("  ")
            t = it.strip()
            self.c.setFillColor(TEAL); self.c.circle(x + (22 if sub else 0), y + size * 0.32, 3, stroke=0, fill=1)
            y = self.texto(x + (34 if sub else 14), y, t, size - (2 if sub else 0), ancho=ancho - (34 if sub else 14)) - gap
        return y

    def caja(self, x, y, w, h, titulo, cuerpo="", relleno=CLARO, color=INK, size=12):
        c = self.c
        c.setFillColor(relleno); c.setStrokeColor(TEAL); c.roundRect(x, y, w, h, 8, stroke=1, fill=1)
        c.setFillColor(color); c.setFont(BOLD, size + 1); c.drawCentredString(x + w / 2, y + h - 18, titulo)
        if cuerpo:
            yy = y + h - 34
            c.setFont(FONT, size)
            for linea in simpleSplit(cuerpo, FONT, size, w - 14):
                c.drawCentredString(x + w / 2, yy, linea); yy -= size * 1.25

    def flecha(self, x1, y1, x2, y2):
        c = self.c; c.setStrokeColor(TEAL); c.setFillColor(TEAL); c.setLineWidth(1.6); c.line(x1, y1, x2, y2)
        import math
        a = math.atan2(y2 - y1, x2 - x1)
        p = c.beginPath(); p.moveTo(x2, y2)
        p.lineTo(x2 - 9 * math.cos(a - 0.4), y2 - 9 * math.sin(a - 0.4)); p.lineTo(x2 - 9 * math.cos(a + 0.4), y2 - 9 * math.sin(a + 0.4)); p.close()
        c.drawPath(p, stroke=0, fill=1)

    def tabla(self, x, y, anchos, filas, size=12, encabezado=True, alto=None, colores=None):
        c = self.c; alto = alto or size * 2.0
        for i, fila in enumerate(filas):
            xx = x
            lineas_max = 1
            celdas = [simpleSplit(str(v), BOLD if (i == 0 and encabezado) else FONT, size, a - 10) for v, a in zip(fila, anchos)]
            lineas_max = max(len(l) for l in celdas)
            h = max(alto, lineas_max * size * 1.2 + 10)
            for j, (lineas, a) in enumerate(zip(celdas, anchos)):
                c.setFillColor(TEAL if (i == 0 and encabezado) else (CLARO if i % 2 else white))
                c.setStrokeColor(HexColor("#CBD5E1")); c.rect(xx, y - h, a, h, stroke=1, fill=1)
                col = white if (i == 0 and encabezado) else (colores.get((i, j), INK) if colores else INK)
                c.setFillColor(col); c.setFont(BOLD if (i == 0 and encabezado) else FONT, size)
                yy = y - size - 3
                for l in lineas:
                    c.drawString(xx + 5, yy, l); yy -= size * 1.2
                xx += a
            y -= h
        return y

    def guardar(self):
        self.c.showPage(); self.c.save()


def construir(url: str, ruta: Path) -> None:
    p = Pres(ruta)
    resultados = None
    jr = RAIZ / "evidencias" / "resultados_app.json"
    if jr.exists():
        resultados = json.loads(jr.read_text(encoding="utf-8"))

    # 1 portada
    p.nueva("Gestor de solicitudes")
    p.texto(50, H - 130, "Un asistente que clasifica solicitudes, responde con fuentes verificables y consulta su estado", 22, BOLD, TEAL, ancho=860, leading=30)
    p.bullets(["Inteligencia Artificial Generativa y Sistemas Inteligentes - EAM 2026-II",
               "Profesor: Robert García Rey",
               "Equipo: Jilmar Said Veloza Páez y Andrés Felipe Galvis Téllez",
               "Entrega final - Noviembre 2026",
               "Aplicación desplegada: " + (url if url else "(URL por registrar al desplegar)")], y=H - 250, size=18, gap=12)
    p.texto(50, 70, "Todos los datos del proyecto (manuales y solicitudes SOL-xxxx) son ficticios.", 13, FONT, GRIS)

    # 2 problema
    p.nueva("El problema y los usuarios")
    p.bullets(["En una institución educativa llegan muchas solicitudes por canales informales: «no puedo entrar», «¿ya me dieron la constancia?», «¿cómo va SOL-1003?».",
               "Hay que entender qué pide la persona, responder con la información correcta de los manuales y consultar el estado de una solicitud...",
               "  ...sin inventar datos y sin exponer información sensible.",
               "Usuarios: (a) estudiantes y personal que preguntan; (b) el equipo de atención, que recibe los casos que requieren una persona; (c) el equipo docente/técnico que audita las respuestas (por eso cada respuesta trae fuentes y trazas).",
               "Fuera de alcance: modificar solicitudes, datos reales, temas ajenos a los 5 manuales."], size=17, gap=12)

    # 3 cinco caminos
    p.nueva("Qué hace: cinco caminos")
    p.tabla(40, H - 95, [150, 370, 390], [
        ["Camino", "Cuándo", "Qué hace"],
        ["Rechazo", "El texto intenta manipular al sistema, pedir secretos o escribir datos", "Se corta antes de llamar al modelo"],
        ["Revisión humana", "Tema sensible (p. ej. amenaza legal) o no clasificable", "Marca el caso para una persona"],
        ["Herramienta (MCP)", "Hay un código SOL-0000 y preguntan por el estado", "Consulta de solo lectura y responde con el dato real"],
        ["Aclaración", "Piden estado sin código o la pregunta es vaga", "Pide el dato que falta"],
        ["RAG", "Pregunta informativa sobre los manuales", "Busca fragmentos y responde con citas, o dice que no tiene evidencia"],
    ], size=14, alto=46)

    # 4 glosario
    p.nueva("Glosario mínimo", "para quien no asistió a clase")
    izq = [("LLM / modelo", "Programa de lenguaje que genera texto. Aquí: gpt-oss-20b servido por Groq."),
           ("Token", "Trozo de texto que el modelo cuenta; define costo y límites."),
           ("Salida estructurada", "Obligar al modelo a responder con un JSON de forma fija (un contrato)."),
           ("Pydantic", "Biblioteca que valida que ese JSON tenga los campos y valores permitidos."),
           ("RAG", "Responder usando documentos recuperados, no solo la memoria del modelo.")]
    der = [("Embedding", "Vector de 384 números que representa el significado de un texto."),
           ("Similitud coseno", "Qué tan cerca están dos vectores (1 = misma dirección)."),
           ("MCP", "Protocolo estándar para que una aplicación use herramientas externas."),
           ("Supabase / RLS", "Base de datos con seguridad por fila: cada usuario solo ve sus filas."),
           ("Abstención", "Decir «no tengo evidencia» en vez de inventar.")]
    for col, (x, datos) in enumerate(((40, izq), (500, der))):
        y = H - 100
        for t, d in datos:
            p.texto(x, y, t, 15, BOLD, TEAL, ancho=430); y = p.texto(x, y - 18, d, 13, ancho=430) - 10

    # 5 recorrido
    p.nueva("Recorrido de una solicitud")
    p.caja(40, 382, 190, 76, "Gradio", "mensaje + sesión de la persona")
    p.caja(270, 382, 190, 76, "almacenamiento", "valida dueño y guarda el mensaje")
    p.caja(500, 382, 190, 76, "Sanitizar", "longitud y patrones de inyección")
    p.caja(730, 382, 190, 76, "Clasificar", "modelo propone, código decide")
    for a_, b_ in ((230, 270), (460, 500), (690, 730)):
        p.flecha(a_ + 2, 420, b_ - 2, 420)
    p.flecha(825, 382, 825, 358)
    p.caja(40, 316, 880, 40, "Decidir ruta (5 caminos)", "", relleno=HexColor("#D1E7E4"))
    ramas = [(40, "Rechazo / Humano", "respuesta segura, sin fuentes", HexColor("#FDECEC")),
             (270, "Aclaración", "pide el dato que falta", HexColor("#FFF4DB")),
             (500, "Herramienta MCP", "valida y consulta estado (solo lectura)", CLARO),
             (730, "RAG", "embedding, Supabase top-10, top-3, modelo, validación", CLARO)]
    for x, t, d, col in ramas:
        p.caja(x, 176, 190, 100, t, d, relleno=col)
        p.flecha(x + 95, 316, x + 95, 278)
        p.flecha(x + 95, 176, x + 95, 140)
    p.caja(40, 66, 880, 72, "Respuesta + fuentes", "se guarda en la conversación (Supabase, con RLS) y se muestra: documento - sección - chunk_id", relleno=HexColor("#E8F5E9"))

    # 6 corpus
    p.nueva("Datos: corpus y fragmentos")
    p.bullets(["Corpus ficticio de 5 manuales redactados por el equipo, con catálogo (fuente, versión 1.0-didactica, licencia, privacidad) y huella SHA-256.",
               "Fragmentación por secciones (##); ventanas con solape solo si una sección supera 110 tokens; cada fragmento lleva «Título / Sección» como encabezado.",
               "Resultado observado en Colab: 12 fragmentos, máximo 76 tokens (límite del modelo de embeddings: 128).",
               "Embeddings: paraphrase-multilingual-MiniLM-L12-v2, 384 dimensiones, normalizados, similitud coseno, revisión del modelo fijada.",
               "Índice en Supabase (pgvector). Se reutiliza si ids, huellas, modelo y revisión coinciden: no se re-embebe por pregunta ni por reinicio."], size=16, gap=11)
    p.tabla(60, 190, [250, 160, 110, 110], [["Documento", "Tema", "Fragmentos", "Huella"],
            ["tipos_solicitud.md", "clasificación", "2", "88be7f076029"], ["prioridades.md", "priorización", "2", "541930d3816d"],
            ["responsables.md", "enrutamiento", "2", "d5c052e51fd5"], ["acceso.md", "acceso", "3", "029a5053bb4a"], ["constancias.md", "documentos", "3", "f74d4b8341a3"]], size=11, alto=20)

    # 7 RAG
    p.nueva("Responder con fuentes verificables")
    p.bullets(["La pregunta se convierte en embedding; Supabase devuelve los 10 fragmentos más cercanos; al modelo solo llegan los 3 mejores (contexto mínimo: ~136 tokens frente a ~610 del corpus completo).",
               "Si la similitud máxima es menor que 0,30, se abstiene sin llamar al modelo.",
               "El modelo responde en JSON: estado (respondida, parcial, aclaración, evidencia insuficiente), texto con citas [F1], [F2] y limitación.",
               "El código verifica que cada cita exista, que el estado sea coherente con las citas y traduce [F1] a documento - sección - chunk_id.",
               "Una cita válida no prueba por sí sola que la afirmación sea correcta: por eso hay revisión humana."], size=16, gap=10)
    p.caja(50, 90, 860, 75, "Ejemplo observado en Colab", "Pregunta: «¿Cuál es el estado de SOL-1003?»  ->  ruta herramienta  ->  «La solicitud SOL-1003 está pendiente de documentos (área: tesorería, última actualización: 2026-09-16).»", relleno=CLARO, size=13)

    # 8 salida controlada y seguridad
    p.nueva("Salida controlada y seguridad")
    p.caja(40, 330, 270, 110, "1. Structured Outputs", "El modelo debe responder con el esquema JSON fijo")
    p.caja(345, 330, 270, 110, "2. Validación Pydantic", "Sin campos extra, valores permitidos, código SOL-0000")
    p.caja(650, 330, 270, 110, "3. Reglas de negocio", "R1 código literal - R2 tipo otro - R3 tema sensible - R4 pago urgente")
    p.flecha(310, 385, 345, 385); p.flecha(615, 385, 650, 385)
    p.bullets(["Entrada: se recorta a 600 caracteres y se bloquean patrones de inyección y de escritura antes de llamar al modelo.",
               "El texto del usuario viaja delimitado como datos, nunca como instrucciones.",
               "Secretos solo en variables de entorno; los errores y logs pasan por una función que enmascara claves.",
               "Si el modelo, Supabase o el MCP fallan: respuesta segura (derivación a revisión humana) y error registrado sin claves."], y=290, size=15, gap=9)

    # 9 MCP
    p.nueva("Herramienta por MCP propio")
    p.caja(40, 330, 190, 100, "Modelo", "propone llamar consultar_estado_solicitud")
    p.caja(290, 330, 230, 100, "Código valida", "herramienta permitida - SOL-0000 - código literal en el mensaje")
    p.caja(580, 330, 150, 100, "Cliente MCP", "subproceso stdio")
    p.caja(780, 330, 150, 100, "servidor_mcp.py", "solo lectura")
    p.flecha(230, 380, 290, 380); p.flecha(520, 380, 580, 380); p.flecha(730, 380, 780, 380)
    p.bullets(["Servidor MCP propio (v1.0.0, SDK mcp 1.30): una única herramienta de solo lectura sobre solicitudes ficticias SOL-1001 a SOL-1004.",
               "El cliente descubre las herramientas y usa solo la permitida (lista blanca). No escucha en la red.",
               "Sin efectos secundarios: no requiere aprobación humana ni hay riesgo de duplicados. Una herramienta de escritura sí la exigiría.",
               "Si el servidor no responde: «el servicio de consulta de estados no está disponible», sin trazas ni claves."], y=290, size=15, gap=9)

    # 10 persistencia
    p.nueva("Usuarios, historial y separación")
    p.caja(40, 340, 200, 95, "Supabase Auth", "correo y contraseña de CADA persona")
    p.caja(290, 340, 290, 95, "conversaciones", "id - usuario_id - titulo - fechas")
    p.caja(630, 340, 290, 95, "mensajes", "id (orden) - conversacion_id - rol - contenido - metadata")
    p.flecha(240, 388, 290, 388); p.flecha(580, 388, 630, 388)
    p.bullets(["RLS: solo el dueño lee o crea sus conversaciones; un mensaje solo se lee o inserta si su conversación es del mismo usuario. Conocer un UUID ajeno no da acceso.",
               "Cada operación usa un cliente efímero con el token de la persona: no hay cliente global compartido. La clave publishable nunca identifica a nadie.",
               "El historial vive en la base de datos: sobrevive a refrescar, cerrar sesión y reiniciar el servidor (gr.State solo guarda la sesión activa).",
               "Al modelo no se envía el historial completo: solo la pregunta anterior cuando el turno previo fue una aclaración.",
               "El corpus es de lectura compartida entre usuarios autenticados; el historial es privado."], y=300, size=14, gap=8)

    # 11 evaluación
    p.nueva("Evaluación de la recuperación", "K=3, M=10, 8 preguntas de desarrollo")
    p.tabla(40, H - 100, [250, 100, 130, 120, 100, 160], [["Opción", "MRR", "Precision@3", "Recall@3", "Hit@3", "Latencia media"],
            ["A - semántica (baseline)", "1,000", "0,333", "1,000", "1,000", "202,1 ms"],
            ["B - BM25 + RRF", "1,000", "0,333", "1,000", "1,000", "160,8 ms"],
            ["C - B + reranking", "1,000", "0,333", "1,000", "1,000", "3098,2 ms"]], size=14, alto=34)
    p.bullets(["Empate total en calidad. Con evidencia de un solo fragmento, 0,333 es el máximo posible de Precision@3.",
               "Criterio fijado antes de abrir la reserva: MRR, luego Recall@3, luego la opción más simple -> se eligió A.",
               "Reserva (3 preguntas, abierta una sola vez): A con MRR 1,000 y Recall@3 1,000; la pregunta «contraseña», que fallaba con BM25 solo, se recuperó primera.",
               "Límite: 12 fragmentos y 11 preguntas anotadas por el mismo equipo; las diferencias pueden ser ruido."], y=H - 270, size=15, gap=9)

    # 12 pruebas colab
    p.nueva("Pruebas de comportamiento", "observadas en Colab")
    p.tabla(30, H - 95, [210, 190, 190, 130, 90, 90], [["Caso", "Ruta (esperada = obtenida)", "Estado", "Latencia", "Llam. LLM", "Tokens in/out"],
            ["normal (RAG)", "rag", "respondida", "7110,9 ms", "2", "968 / 236"],
            ["ambiguo", "aclaracion", "aclaracion", "3370,2 ms", "1", "374 / 108"],
            ["incompleto (sin código)", "aclaracion", "aclaracion", "4495,8 ms", "1", "378 / 92"],
            ["malicioso", "rechazo", "rechazada", "0,0 ms", "0", "0 / 0"],
            ["fuera de alcance", "rag", "evidencia_insuficiente", "8096,4 ms", "2", "973 / 149"],
            ["herramienta (existe)", "herramienta", "respondida", "4159,1 ms", "2", "576 / 148"],
            ["herramienta (no existe)", "herramienta", "no_encontrada", "4734,1 ms", "2", "576 / 148"],
            ["revisión humana", "humano", "derivada", "3524,0 ms", "1", "383 / 144"]], size=12, alto=28)
    p.texto(40, 130, "8 de 8 rutas correctas. Falla simulada del modelo: respuesta segura sin filtrar claves. Los 3 casos de comportamiento (fuera de alcance, ambigua, estado sin código) también correctos.", 14, ancho=880)

    # 13 pruebas app
    p.nueva("Pruebas de la aplicación")
    p.bullets(["64 pruebas automáticas sin red (pytest): lógica del sistema, aislamiento entre usuarios, token por persona, historial tras reiniciar, interfaz completa con dos usuarios y servidor MCP real por stdio. Resultado: 64 aprobadas.",
               "Límite honesto: usan un Supabase simulado; no sustituyen la comprobación de las políticas RLS reales."], size=15, y=H - 100, gap=10)
    if resultados:
        filas = [["ID", "Prueba", "Estado"]] + [[r["id"], r["prueba"][:78], r["estado"]] for r in resultados["resultados"][:14]]
        col = {(i, 2): (TEAL if r["estado"] == "APROBADA" else ROJO) for i, r in enumerate(resultados["resultados"][:14], 1)}
        ok = sum(r["estado"] == "APROBADA" for r in resultados["resultados"])
        p.texto(40, H - 190, f"Contra servicios reales ({resultados['fecha']}): {ok} de {len(resultados['resultados'])} aprobadas", 15, BOLD, TEAL)
        p.tabla(40, H - 205, [60, 740, 110], filas, size=10, alto=19, colores=col)
    else:
        p.caja(40, 150, 880, 110, "Contra servicios reales: aún sin ejecutar", "El script app/verificar_entrega.py comprueba con dos usuarios reales: historial en orden, recuperación con sesión nueva, que un usuario no pueda leer ni escribir en la conversación de otro (consultas directas a la base) y los casos funcionales con el modelo real. Sus resultados se publican en evidencias/resultados_app.md.", relleno=HexColor("#FFF4DB"), size=13)

    # 14 fallos y limitaciones
    p.nueva("Fallo observado y limitaciones")
    p.texto(40, H - 100, "Fallo real observado: fidelidad del modelo", 17, BOLD, ROJO)
    p.bullets(["En la respuesta D1, el modelo añadió una afirmación que no está en el fragmento y cambió «no basta con repetir el envío» por «no es necesario repetir».",
               "La validación comprueba que las citas existan y el estado sea coherente, pero no que cada frase esté respaldada.",
               "Acción propuesta (no aplicada por no estar evaluada): prompt más estricto y nueva revisión humana de las 11 respuestas, que sigue pendiente."], y=H - 125, size=14, gap=8)
    p.texto(40, 255, "Limitaciones", 17, BOLD, TEAL)
    p.bullets(["Corpus de 5 manuales y 12 fragmentos; evaluación hecha por el mismo equipo.",
               "Umbral de abstención 0,30 heurístico: en el caso «cafetería» abstuvo el modelo, no el umbral.",
               "Seguridad por patrones: no detiene toda inyección; se mitiga con herramienta de solo lectura.",
               "Datos y herramienta ficticios; sin pruebas de carga; memoria conversacional mínima."], y=230, size=14, gap=7)

    # 15 despliegue
    p.nueva("Cómo reproducirlo y desplegarlo")
    p.bullets(["Clonar, crear el entorno virtual e instalar app/requirements.txt; copiar app/.env.ejemplo como app/.env y completar claves propias.",
               "Supabase: ejecutar supabase/setup.sql, crear usuarios en Auth y cargar el corpus con python preparar_corpus.py.",
               "Local: python app.py -> http://127.0.0.1:7860. Pruebas: python -m pytest tests.",
               "Render (Web Service): Root Directory app - Build pip install -r requirements.txt - Start python app.py - variables en Environment - GRADIO_SERVER_NAME=0.0.0.0 - plan de 2 GB de RAM recomendado por el modelo de embeddings.",
               "Despliegue: " + (url if url else "pendiente de registrar la URL y las pruebas desde ella"),
               "Cada paso está explicado en app/README.md y en docs/GUIA_PASO_A_PASO.md."], size=15, gap=10)

    # 16 equipo y cierre
    p.nueva("Equipo, aportes y mejoras pendientes")
    p.bullets(["Equipo: Jilmar Said Veloza Páez y Andrés Felipe Galvis Téllez. Aportes individuales: ver BITACORA_PROYECTO.md, sección 10.",
               "Documentación integral de los tres cortes: BITACORA_PROYECTO.md (decisiones, experimentos, errores, evidencias).",
               "Mejoras pendientes:",
               "  Revisión humana de las 11 respuestas y prompt rag_v3 más estricto.",
               "  Corpus más grande y más preguntas anotadas por personas distintas; calibrar el umbral.",
               "  Autenticación de quien consulta un código y datos reales autorizados.",
               "  Pruebas de carga y de concurrencia."], size=16, gap=11)
    p.guardar()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="", help="URL pública de la aplicación desplegada")
    ap.add_argument("--salida", default=str(RAIZ / "app" / "presentacion_proyecto.pdf"))
    a = ap.parse_args()
    construir(a.url.strip(), Path(a.salida))
    print("Presentación generada:", a.salida)
