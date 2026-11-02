from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Flowable, Preformatted
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import glob
reg = glob.glob("/usr/share/fonts/**/DejaVuSans.ttf", recursive=True); bold = glob.glob("/usr/share/fonts/**/DejaVuSans-Bold.ttf", recursive=True)
mono = glob.glob("/usr/share/fonts/**/DejaVuSansMono.ttf", recursive=True)
pdfmetrics.registerFont(TTFont("F", reg[0])); pdfmetrics.registerFont(TTFont("FB", bold[0])); pdfmetrics.registerFont(TTFont("FM", mono[0]))
pdfmetrics.registerFontFamily("F", normal="F", bold="FB", italic="F", boldItalic="FB")
AZ = colors.HexColor("#1F3A5F"); GR = colors.HexColor("#F1F4F8"); AM = colors.HexColor("#FFF4D6")
ss = getSampleStyleSheet()
B = ParagraphStyle("B", fontName="F", fontSize=9.5, leading=14, spaceAfter=6)
H1 = ParagraphStyle("H1", fontName="FB", fontSize=16, leading=20, textColor=AZ, spaceBefore=6, spaceAfter=8)
H2 = ParagraphStyle("H2", fontName="FB", fontSize=11.5, leading=15, textColor=AZ, spaceBefore=8, spaceAfter=4)
SM = ParagraphStyle("SM", parent=B, fontSize=8.3, leading=11.5)
TT = ParagraphStyle("TT", fontName="FB", fontSize=26, leading=32, textColor=AZ)
def P(t, s=B): return Paragraph(t, s)
def tabla(data, widths, head=True, fs=8.3):
    d = [[Paragraph(str(c), ParagraphStyle("c", parent=SM, fontSize=fs, leading=fs+3, fontName="FB" if (head and i == 0) else "F",
          textColor=colors.white if (head and i == 0) else colors.black)) for c in r] for i, r in enumerate(data)]
    t = Table(d, colWidths=widths, repeatRows=1 if head else 0)
    st = [("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#B8C2CF")), ("VALIGN", (0,0), (-1,-1), "TOP"),
          ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4)]
    if head: st += [("BACKGROUND", (0,0), (-1,0), AZ)] + [("BACKGROUND", (0,i), (-1,i), GR) for i in range(2, len(data), 2)]
    t.setStyle(TableStyle(st)); return t
def caja(txt, bg=AM):
    t = Table([[P(txt, SM)]], colWidths=[16.4*cm]); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),bg),("BOX",(0,0),(-1,-1),0.6,colors.HexColor("#C9A227")),("LEFTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)])); return t

class Diagrama(Flowable):
    W, H = 16.4*cm, 11.2*cm
    def wrap(self, *a): return self.W, self.H
    def box(self, c, x, y, w, h, txt, fill="#E8EEF6", stroke="#1F3A5F", fs=7.6):
        c.setFillColor(colors.HexColor(fill)); c.setStrokeColor(colors.HexColor(stroke)); c.roundRect(x, y, w, h, 5, fill=1, stroke=1)
        c.setFillColor(colors.black); c.setFont("F", fs)
        lines = txt.split("\n"); y0 = y + h/2 + (len(lines)-1)*fs*0.6 - fs*0.3
        for i, l in enumerate(lines): c.drawCentredString(x + w/2, y0 - i*fs*1.2, l)
    def arrow(self, c, x1, y1, x2, y2, label=None):
        c.setStrokeColor(colors.HexColor("#1F3A5F")); c.setLineWidth(1); c.line(x1, y1, x2, y2)
        import math; a = math.atan2(y2-y1, x2-x1); s = 5
        c.setFillColor(colors.HexColor("#1F3A5F")); p = c.beginPath(); p.moveTo(x2, y2)
        p.lineTo(x2 - s*math.cos(a-0.4), y2 - s*math.sin(a-0.4)); p.lineTo(x2 - s*math.cos(a+0.4), y2 - s*math.sin(a+0.4)); p.close(); c.drawPath(p, fill=1, stroke=0)
        if label: c.setFont("F", 6.8); c.setFillColor(colors.HexColor("#444444")); c.drawString((x1+x2)/2+3, (y1+y2)/2+2, label)
    def draw(self):
        c = self.canv; W = self.W
        self.box(c, 0.2*cm, 9.9*cm, 3.6*cm, 1.1*cm, "Persona\n(mensaje)", "#FFF4D6")
        self.box(c, 4.9*cm, 9.9*cm, 4.2*cm, 1.1*cm, "1. Sanitizar entrada\n(límite, patrones de riesgo)")
        self.box(c, 10.2*cm, 9.9*cm, 5.0*cm, 1.1*cm, "2. Clasificar (LLM + Pydantic\n+ reglas de negocio)")
        self.arrow(c, 3.8*cm, 10.45*cm, 4.9*cm, 10.45*cm); self.arrow(c, 9.1*cm, 10.45*cm, 10.2*cm, 10.45*cm)
        self.box(c, 3.3*cm, 7.7*cm, 10.0*cm, 1.1*cm, "3. Enrutador (decidir_ruta)\nprecedencia: seguridad > humano > herramienta > aclaración > RAG", "#DDE8DD", fs=7)
        self.arrow(c, 12.7*cm, 9.9*cm, 11.0*cm, 8.8*cm)
        self.box(c, 0.2*cm, 5.5*cm, 3.6*cm, 1.2*cm, "Rechazo / Humano /\nAclaración", "#F6DADA")
        self.box(c, 4.3*cm, 5.5*cm, 4.4*cm, 1.2*cm, "Herramienta\nconsultar_estado_solicitud\n(solo lectura, validada)", "#E8EEF6", fs=6.8)
        self.box(c, 9.4*cm, 5.5*cm, 6.8*cm, 1.2*cm, "Pipeline RAG", "#E8EEF6")
        self.arrow(c, 4.5*cm, 7.7*cm, 2.0*cm, 6.7*cm); self.arrow(c, 7.5*cm, 7.7*cm, 6.5*cm, 6.7*cm); self.arrow(c, 11.0*cm, 7.7*cm, 12.8*cm, 6.7*cm)
        self.box(c, 9.4*cm, 3.5*cm, 3.2*cm, 1.2*cm, "Embedding de la\npregunta (MiniLM)", fs=7)
        self.box(c, 13.0*cm, 3.5*cm, 3.2*cm, 1.2*cm, "Supabase pgvector\ntop-M (coseno)", "#E3F0E3", fs=7)
        self.arrow(c, 12.8*cm, 5.5*cm, 11.0*cm, 4.7*cm); self.arrow(c, 12.6*cm, 4.1*cm, 13.0*cm, 4.1*cm)
        self.box(c, 9.4*cm, 1.6*cm, 3.2*cm, 1.2*cm, "BM25 + RRF\n(+ reranking)", "#FFF4D6", fs=7)
        self.box(c, 13.0*cm, 1.6*cm, 3.2*cm, 1.2*cm, "Top-K=3 → LLM\ncon prompt rag_v2", fs=7)
        self.arrow(c, 14.6*cm, 3.5*cm, 11.0*cm, 2.8*cm); self.arrow(c, 12.6*cm, 2.2*cm, 13.0*cm, 2.2*cm)
        self.box(c, 4.3*cm, 0.1*cm, 8.6*cm, 1.1*cm, "Validación: citas existen · estado coherente · abstención sin inventar\n→ respuesta + fuentes (documento › sección › chunk_id)", "#DDE8DD", fs=7)
        self.arrow(c, 14.6*cm, 1.6*cm, 12.9*cm, 0.8*cm)
        self.box(c, 0.2*cm, 2.2*cm, 3.6*cm, 2.4*cm, "Bitácora y trazas\nlatencia · tokens\nrutas · errores\n(sin secretos)", "#F1F4F8", fs=7)
        self.box(c, 0.2*cm, 0.2*cm, 3.6*cm, 1.4*cm, "Carga única del corpus:\nchunking → embeddings →\nSupabase (se reutiliza)", "#E3F0E3", fs=6.4)

def foot(c, d):
    c.saveState(); c.setFont("F", 7.5); c.setFillColor(colors.grey)
    c.drawString(2*cm, 1.1*cm, "Gestor de solicitudes · Guía del segundo corte · Veloza & Galvis · EAM 2026-II"); c.drawRightString(19*cm, 1.1*cm, f"Pág. {d.page}"); c.restoreState()

S = []
S += [Spacer(1, 3*cm), P("Gestor de solicitudes", TT), P("Guía del segundo corte: asistente con RAG, herramienta y evaluación", ParagraphStyle("s", fontName="F", fontSize=13, leading=18, textColor=colors.HexColor("#444444"))), Spacer(1, 1*cm),
      tabla([["Equipo", "Jilmar Veloza · Andrés Galvis"], ["Curso", "EAM 2026-II — Docente: Robert García Rey"], ["Entregables", "Notebook consolidado (Colab) · repositorio · esta guía"],
             ["Tecnología", "Python · Groq (openai/gpt-oss-20b) · Supabase pgvector · sentence-transformers · BM25 · Pydantic"], ["Datos", "100 % ficticios; sin datos personales"]],
            [3.2*cm, 13.2*cm], head=False, fs=9), Spacer(1, 1*cm),
      caja("<b>Cómo leer esta guía.</b> Está escrita para alguien que no cursó la materia: primero el problema y los términos (secciones 1–2), luego cómo está construido el sistema (3–5), un caso completo (6), cómo se evaluó y qué significa (7), las decisiones, el fallo observado, los límites y la privacidad (8–10) y, al final, cómo ejecutar y el checklist de entrega (11–12).", GR),
      Spacer(1, 0.6*cm), caja("<b>Transparencia sobre los resultados.</b> Las cifras de la sección 7 marcadas como <i>medidas</i> se calcularon con código real y son reproducibles. Las que dependen de ejecutar en Colab (embeddings, reranking, Groq, Supabase, latencias y tokens) <b>no se inventaron</b>: el notebook las produce y hay espacios para pegarlas.")]
S += [PageBreak(), P("1. Problema, usuarios y objetivo", H1),
 P("<b>Problema.</b> En una institución educativa llegan muchas solicitudes por canales informales («no puedo entrar», «¿ya me dieron la constancia?», «¿cómo va SOL-1003?»). Hay que entender qué pide la persona, responder con la información correcta de los manuales y consultar el estado de una solicitud, <b>sin inventar</b> datos y sin exponer información sensible."),
 P("<b>Usuarios.</b> (a) Estudiantes y personal que escriben una pregunta; (b) el equipo de atención que recibe los casos que requieren una persona; (c) el equipo docente/técnico que audita las respuestas (por eso cada respuesta trae fuentes y trazas)."),
 P("<b>Objetivo.</b> Un asistente que, ante un mensaje, decide entre cinco caminos y actúa de forma controlada y verificable:"),
 tabla([["Camino", "Cuándo", "Qué hace"],
        ["Rechazo", "El texto intenta manipular al sistema o pedir secretos", "Se corta antes de llamar al modelo"],
        ["Revisión humana", "Tema sensible (p. ej. amenaza legal) o no clasificable", "Marca el caso para una persona"],
        ["Herramienta", "Hay un código SOL-0000 y preguntan por el estado", "Consulta de solo lectura y respuesta desde el dato real"],
        ["Aclaración", "Piden estado sin código o la pregunta es vaga", "Pide el dato que falta"],
        ["RAG", "Pregunta informativa sobre los manuales", "Busca fragmentos, responde con citas o dice que no sabe"]], [3.2*cm, 6.4*cm, 6.8*cm]),
 P("2. Glosario", H1),
 tabla([["Término", "Significado sencillo"],
  ["LLM / modelo", "Programa de lenguaje que genera texto. Aquí: <font name='FM'>openai/gpt-oss-20b</font> servido por Groq."],
  ["Token", "Trozo de texto (palabra o parte) que el modelo cuenta; define costo y límites."],
  ["Salida estructurada", "Forzar al modelo a responder con un JSON de forma fija (un «contrato»)."],
  ["Pydantic", "Biblioteca que valida que ese JSON tenga los campos y valores permitidos."],
  ["Herramienta (tool)", "Función del código que el modelo puede <i>proponer</i> llamar; el código valida y ejecuta."],
  ["RAG", "Responder usando documentos recuperados en vez de la memoria del modelo."],
  ["Chunk / fragmento", "Pedazo del documento (aquí, una sección) que se indexa y se cita."],
  ["Embedding", "Vector de 384 números que representa el significado de un texto; textos parecidos quedan cerca."],
  ["Similitud coseno", "Medida de cercanía entre dos vectores (1 = igual dirección)."],
  ["pgvector / Supabase", "Extensión de Postgres para guardar vectores y buscar los más cercanos; Supabase es el servicio."],
  ["RLS", "Seguridad por fila: cada usuario solo ve sus filas."],
  ["BM25", "Búsqueda por palabras exactas (léxica), clásica y rápida."],
  ["RRF", "Reciprocal Rank Fusion: combina dos rankings sumando 1/(60+posición)."],
  ["Reranker (cross-encoder)", "Modelo que lee pregunta+fragmento juntos y los reordena con más precisión."],
  ["Precision@3, Recall@3, MRR", "Qué fracción del top-3 es relevante; qué parte de la evidencia necesaria se cubrió; qué tan arriba aparece lo primero relevante."],
  ["Abstención", "Responder «no tengo evidencia» en vez de inventar."]], [4.2*cm, 12.2*cm])]
S += [PageBreak(), P("3. Documentos del corpus", H1),
 P("El corpus es <b>didáctico y ficticio</b>: cinco manuales cortos redactados por el equipo (sin licencia externa ni datos personales). Se escriben desde el notebook a <font name='FM'>corpus/</font> y cada uno tiene versión <font name='FM'>1.0-didactica</font> y un hash SHA-256 para detectar cambios y decidir si el índice se reconstruye."),
 tabla([["Documento", "Tema", "Contenido clave"],
  ["tipos_solicitud.md", "Clasificación", "4 tipos (acceso, documento, pago, queja); formato de código SOL-0000"],
  ["prioridades.md", "Priorización", "Alta/media/baja; pago que vence en &lt; 48 h = alta"],
  ["responsables.md", "Enrutamiento", "Qué área atiende cada tipo; escalamiento a revisión humana"],
  ["acceso.md", "Acceso", "Recuperar acceso, error 403, límites de la consulta de estados"],
  ["constancias.md", "Documentos", "Cómo radicar, qué significa «en revisión», correcciones"]], [3.6*cm, 2.8*cm, 10*cm]),
 Spacer(1,8), P("<b>Chunking.</b> Cada documento se parte por sección (<font name='FM'>##</font>); si una sección superara 110 tokens se parte en ventanas con solape de 12. A cada fragmento se le antepone «Título / Sección» antes de vectorizar. Resultado: <b>12 fragmentos</b>, el mayor de ~63 tokens medidos con un tokenizador de prueba (el límite del modelo es 128; el notebook lo verifica con el tokenizador real). En este corpus las secciones son de un solo párrafo, así que «ventanas» y «párrafos» producen los mismos 12 fragmentos; se mantiene «ventanas» porque protege ante manuales más largos."),
 P("<b>Metadatos por fragmento:</b> fuente, sección, versión, hash del documento, estrategia, tokens y <font name='FM'>chunk_id</font> (p. ej. <font name='FM'>acceso-02</font>). Estos metadatos son los que permiten mostrar «documento › sección › chunk_id» como fuente."),
 P("4. Diagrama del sistema", H1), Diagrama(),
 P("<b>Idea central:</b> el modelo <i>propone</i> y el código <i>decide</i>. Cada flecha pasa por una validación (entrada, contrato, herramienta, citas).", SM)]
S += [PageBreak(), P("5. Cómo funciona cada pieza", H1),
 P("5.1 Función original y salida controlada (ítems 1–3)", H2),
 P("La función <font name='FM'>clasificar(texto)</font> devuelve una <b>Solicitud</b> con tipo, prioridad, si requiere revisión humana, código (si aparece literalmente), resumen y motivo. Tres capas: (1) <i>Structured Outputs</i> estricto en Groq; (2) validación Pydantic con <font name='FM'>extra=forbid</font>; (3) reglas de negocio en código (R1 descarta códigos no presentes en el texto, R2 'otro' → humano, R3 tema sensible → humano, R4 pago por vencer → prioridad alta). Si el JSON es inválido se reintenta una vez y luego se responde de forma segura."),
 P("5.2 Herramienta de estado (ítem 4)", H2),
 P("<font name='FM'>consultar_estado_solicitud(codigo)</font> lee un diccionario ficticio. Controles: lista blanca de nombres, argumentos validados con patrón <font name='FM'>^SOL-[0-9]{4}$</font>, y el código debe estar <b>literalmente</b> en el mensaje. La respuesta se arma desde el dato real, no desde el modelo. Hay pruebas negativas (herramienta no permitida, campo extra, código mal formado, código inventado)."),
 P("5.3 Seguridad y errores (ítem 5)", H2),
 P("Sanitización y límite de 600 caracteres; patrones de inyección/exfiltración que cortan antes del modelo; texto de usuario delimitado como <i>datos</i>; secretos solo desde Colab Secrets y enmascarados en logs; si el modelo o Supabase fallan se responde «derivada a revisión humana» y se registra el error redactado. Nunca se cambia a otro modo en silencio."),
 P("5.4 Embeddings y Supabase (ítem 9)", H2),
 P("Modelo <font name='FM'>paraphrase-multilingual-MiniLM-L12-v2</font> (384 dimensiones, normalizado, coseno) con revisión fijada. El SQL (<font name='FM'>supabase/setup.sql</font>) crea la tabla con pgvector, políticas RLS por propietario y la función de búsqueda. El notebook inicia sesión con la clave <i>publishable</i>, compara ids, hashes, modelo y revisión con lo guardado y <b>solo re-embebe si algo cambió</b>; las consultas únicamente embeben la pregunta. Para reconstruir: ejecutar el SQL y la sección 4. Para restaurar: lo mismo."),
 P("5.5 Recuperación y respuesta (ítem 10)", H2),
 P("Top-M=10 desde Supabase (y, según la opción, BM25+RRF y reranking) → top-K=3 → prompt versionado <font name='FM'>rag_v2</font> → respuesta con <font name='FM'>estado</font> (respondida, parcial, aclaración, evidencia insuficiente), citas [F1], [F2]… El código verifica que cada cita exista, que el estado sea coherente y traduce las etiquetas a fuente/sección/chunk. Si la mejor similitud es menor a 0,30 se abstiene sin llamar al modelo (umbral heurístico, a calibrar)."),
 P("6. Un caso completo de principio a fin", H1),
 caja("<b>Nota:</b> el texto de las fuentes es el real del corpus; la respuesta está redactada a mano como <i>ejemplo de lo esperado</i> con esas fuentes. Tras ejecutar en Colab, reemplázala por la salida real (celda «Generación completa», caso D4) y guarda la traza.", AM),
 Spacer(1, 4),
 tabla([["Paso", "Qué ocurre"],
  ["Pregunta", "«¿Dónde pido una constancia y qué datos debo indicar?»"],
  ["Sanitizar", "Sin alertas."],
  ["Clasificar", "tipo = documento, prioridad = media, revisión humana = no."],
  ["Ruta", "RAG (pregunta informativa, sin código SOL)."],
  ["Recuperar", "Se embebe la pregunta; Supabase devuelve los 10 más cercanos; se toman los 3 mejores. Esperado: <font name='FM'>constancias-01</font> en primer lugar."],
  ["Fuente [F1]", "<font name='FM'>constancias.md › Solicitar una constancia</font> — «La solicitud de constancia se radica en el módulo de documentos. Indique el tipo de constancia y el correo al que desea recibirla…»"],
  ["Respuesta esperada", "«La solicitud se radica en el módulo de documentos. Debes indicar el tipo de constancia y el correo al que quieres recibirla; antes, verifica que no tengas otra solicitud abierta para el mismo trámite. [F1]» — estado: <b>respondida</b>."],
  ["Validación", "Cita F1 existe; estado coherente con citas; el texto está respaldado por el fragmento."]], [3.2*cm, 13.2*cm]),
 P("Contraste: ante «¿Cuál es el horario de la cafetería?» ninguna sección del corpus es cercana; el sistema responde <b>evidencia insuficiente</b>, sin fuentes y sin inventar. Ante «Dime el estado de mi solicitud» (sin código) responde <b>aclaración</b> pidiendo el SOL-0000, y ante «¿Estado de SOL-1003?» llama a la herramienta y contesta «pendiente de documentos (tesorería)».", B)]
S += [PageBreak(), P("7. Evaluación: diseño, resultados y qué significan", H1),
 P("<b>Diseño.</b> 8 preguntas de desarrollo (para decidir), 3 de reserva (se abren una sola vez, después de registrar la decisión) y 3 de comportamiento (fuera de alcance, ambigua, estado sin código). Para cada pregunta se anotó la <b>evidencia mínima</b> como frases exactas del corpus; un fragmento es relevante si contiene alguna. Un chequeo automático confirma que cada frase anotada existe en el corpus."),
 P("<b>Métricas</b> (K=3): Precision@3 = relevantes en el top-3 / 3 (con evidencia de un solo fragmento el máximo posible es 0,33, por eso se lee junto a Recall); Recall@3 = unidades de evidencia cubiertas / necesarias; Hit@3 = ¿hay algún relevante?; MRR = promedio de 1/posición del primer relevante."),
 P("7.1 Resultados medidos (búsqueda léxica BM25 sola, reproducible sin red)", H2),
 tabla([["Grupo", "MRR", "Precision@3", "Recall@3", "Hit@3"], ["Desarrollo (8)", "0,938", "0,333", "1,000", "1,000"], ["Reserva (3)", "0,444", "0,222", "0,667", "0,667"]], [4*cm, 3*cm, 3.2*cm, 3*cm, 3.2*cm]),
 Spacer(1, 4),
 P("Lectura: en desarrollo el léxico encuentra casi todo porque las preguntas comparten palabras con los manuales («error 403», «constancia»). En reserva baja: <b>R3</b> («Se me olvidó la contraseña, ¿cómo ingreso de nuevo?») no recupera la sección «Recuperar acceso» porque el manual nunca usa la palabra «contraseña»; y <b>R1</b> trae la evidencia en la 3.ª posición (RR 0,33). Es la razón de combinar con búsqueda semántica."),
 P("7.2 Comparación A / B / C (completar con la salida de Colab)", H2),
 tabla([["Opción", "MRR dev", "Recall@3 dev", "MRR reserva", "Recall@3 reserva", "Latencia ms"],
        ["A semántica (baseline)", "____", "____", "____", "____", "____"], ["B BM25 + RRF", "____", "____", "____", "—", "____"], ["C B + reranking", "____", "____", "____", "—", "____"]],
       [4.4*cm, 2*cm, 2.6*cm, 2.4*cm, 2.8*cm, 2.2*cm]),
 P("La reserva se evalúa solo con A y la opción elegida. <b>Cómo interpretar:</b> si B o C mejoran MRR/Recall en desarrollo y no empeoran en reserva, la mejora se justifica; si empatan (probable con 12 fragmentos), se conserva el resultado y se elige la más simple; si empeoran, se documenta igual. Una diferencia de una pregunta sobre 8 es <b>ruido</b>, no prueba.", SM),
 P("7.3 Comportamiento y pruebas integradas", H2),
 tabla([["Caso", "Entrada", "Ruta esperada", "Estado esperado"], ["C1 fuera de alcance", "«¿Cuál es el horario de la cafetería?»", "RAG", "evidencia insuficiente, sin fuentes"], ["C2 ambigua", "«¿Cómo lo hago?»", "aclaración", "aclaración"], ["C3 sin código", "«Dime el estado de mi solicitud»", "aclaración", "aclaración"]], [3.4*cm, 6.2*cm, 2.8*cm, 4*cm]),
 P("Además se repiten los cinco casos iniciales (normal, ambiguo, incompleto, malicioso, fuera de alcance) más herramienta (código existente e inexistente) y revisión humana; el notebook verifica la ruta de cada uno. La lógica completa se validó localmente con componentes simulados (todas las rutas pasaron); la validación con los modelos reales se hace en Colab.", B),
 P("7.4 Revisión humana", H2),
 P("El equipo lee cada respuesta generada (11 preguntas) y marca <i>correcta, fiel al contexto, citas que respaldan, estado adecuado</i> con una justificación breve en <font name='FM'>REVISION_HUMANA</font>. Resultado a reportar: ____ / 11 en cada criterio.")]
S += [PageBreak(), P("8. Decisión técnica, fallo observado y límites", H1),
 P("<b>Decisión técnica.</b> Se compararon tres recuperadores con las mismas preguntas. Criterio fijado antes de mirar la reserva: mayor MRR, luego mayor Recall@3, luego la opción más simple. Motivos para probar el híbrido: los manuales tienen términos exactos («403», «SOL-1001») que BM25 captura, mientras que los embeddings capturan paráfrasis («contraseña» frente a «Recuperar acceso»). El reranker agrega costo de latencia y un segundo modelo; solo se adopta si mejora de forma clara."),
 P("<b>Fallo real observado (medido).</b> Con búsqueda léxica sola, la pregunta R3 «Se me olvidó la contraseña, ¿cómo ingreso de nuevo?» recupera <font name='FM'>tipos_solicitud-02</font>, <font name='FM'>constancias-03</font> y <font name='FM'>constancias-02</font>, pero no <font name='FM'>acceso-01</font> (Recuperar acceso). <i>Causa:</i> desajuste de vocabulario; el manual dice «Recuperar acceso» y «no puede ingresar», no «contraseña». <i>Qué se hace:</i> la rama semántica (embeddings) debería cubrirlo; si en Colab A/B/C también fallan, la acción correcta es enriquecer el documento (sinónimos en el texto fuente) y registrarlo en la bitácora, no ajustar el sistema a esa pregunta de reserva. Completa en la bitácora si el fallo persiste con los embeddings reales."),
 P("<b>Limitaciones.</b>"),
 tabla([["Límite", "Consecuencia"],
  ["Corpus de 5 documentos / 12 fragmentos", "Las diferencias A/B/C pueden ser ruido; no generaliza a manuales grandes."],
  ["11 preguntas anotadas por el mismo equipo", "Sesgo posible; sin segundo anotador."],
  ["Umbral de abstención 0,30 heurístico", "Puede rechazar preguntas válidas o aceptar fuera de alcance; se verifica con C1 y se calibra."],
  ["Seguridad por patrones", "No detiene toda inyección; se mitiga con herramienta de solo lectura y respuestas ancladas al contexto."],
  ["Herramienta sobre datos ficticios", "No hay base real de solicitudes ni autenticación del solicitante."],
  ["Un LLM y un modelo de embeddings", "Sin comparación entre modelos; sujetos a cambios del proveedor."],
  ["Sin pruebas de carga", "Latencias medidas por consulta aislada, en CPU."]], [6*cm, 10.4*cm]),
 P("9. Privacidad y manejo de secretos", H1),
 P("Todo el contenido es ficticio. Los códigos SOL-xxxx no corresponden a personas. Las claves viven solo en Colab Secrets (nunca en celdas, ni en el repositorio, ni en la evidencia: el notebook revisa el ZIP buscando patrones de claves y falla si encuentra alguno). Supabase usa RLS por propietario y la clave <i>publishable</i>, nunca la <i>secret</i>. Los logs enmascaran claves. En un uso real habría que añadir consentimiento, retención limitada de logs y autenticación del solicitante antes de mostrar estados."),
 P("10. Cómo ejecutar", H1),
 tabla([["Paso", "Acción"], ["1", "Crear proyecto Supabase; ejecutar <font name='FM'>supabase/setup.sql</font> en SQL Editor; crear un usuario con correo y contraseña."],
  ["2", "En Colab > Secrets: SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_EMAIL, SUPABASE_PASSWORD, GROQ_API_KEY (activar acceso al notebook)."],
  ["3", "Abrir <font name='FM'>Gestor_Solicitudes_Consolidado.ipynb</font> y ejecutar todo. La primera vez construye el índice; las siguientes lo reutilizan."],
  ["4", "Completar: tabla 7.2, <font name='FM'>REVISION_HUMANA</font>, fallo real y bitácora. Descargar el ZIP de evidencia."],
  ["5", "Subir al repositorio: README, notebook, SQL, corpus, requirements, bitácora y este PDF (sin secretos)."]], [1.6*cm, 14.8*cm]),
 P("Modos: <font name='FM'>modo_llm='mock'</font> permite probar clasificación y herramienta sin API (RAG extractivo, claramente marcado); <font name='FM'>almacen='local'</font> es solo para pruebas y muestra una advertencia: la entrega final debe usar Supabase.", SM)]
S += [PageBreak(), P("11. Checklist de entrega (los 12 ítems)", H1),
 tabla([["#", "Ítem exigido", "Dónde está", "Estado"],
  ["1", "Función original + entrada del usuario", "Notebook §5 <font name='FM'>clasificar</font>, §10 <font name='FM'>atender</font>", "Listo"],
  ["2", "Integración con modelo y prompt RAG versionado", "§1 <font name='FM'>llamar_llm</font>, §9 <font name='FM'>rag_v2</font>", "Listo"],
  ["3", "Salida controlada (contrato, Pydantic, reglas)", "§5, §9 + pruebas negativas", "Listo"],
  ["4", "Herramienta integrada validada, solo lectura", "§7", "Listo"],
  ["5", "Seguridad y manejo de errores", "§1, §8, §13 (falla simulada)", "Listo"],
  ["6", "Pruebas, logs, bitácora (5 casos, latencia, tokens)", "§13, <font name='FM'>bitacora.csv</font>", "Ejecutar en Colab"],
  ["7", "Corpus documentado", "§2 + catálogo, sección 3 de esta guía", "Listo"],
  ["8", "Chunking y metadatos", "§3", "Listo"],
  ["9", "Embeddings + Supabase (SQL, reutilización)", "§4, <font name='FM'>supabase/setup.sql</font>", "Ejecutar en Colab"],
  ["10", "Recuperación, fuentes, enrutamiento RAG vs herramienta", "§9–10", "Listo"],
  ["11", "Mejora justificada A vs B/C", "§11–12", "Ejecutar en Colab"],
  ["12", "Evaluación integrada, revisión humana, fallo, límites", "§12 + secciones 7–8", "Completar con resultados"]], [0.8*cm, 6.2*cm, 6.4*cm, 3*cm]),
 P("Repositorio: README · código/notebook · SQL de Supabase · dependencias · corpus · pruebas · bitácora · PDF · sin secretos. Nuevo notebook final que corre completo en Colab sin otros notebooks."),
 P("12. Pendientes que solo el equipo puede cerrar", H1),
 P("• Ejecutar el notebook en Colab con sus credenciales y pegar la tabla A/B/C (sección 7.2).<br/>• Rellenar la revisión humana y reemplazar el caso de la sección 6 por la salida real.<br/>• Confirmar el fallo real con embeddings reales y anotarlo en la bitácora.<br/>• Si el docente exige los manuales originales de la Clase 08 (<i>acceso.md</i>, <i>constancias.md</i>), reemplazar los textos del notebook conservando las frases anotadas o reanotar los casos: el chequeo automático de la sección 12 avisa si una frase ya no existe.")]
SimpleDocTemplate("docs/Guia_Segundo_Corte.pdf", pagesize=A4, leftMargin=2.3*cm, rightMargin=2.3*cm, topMargin=2*cm, bottomMargin=1.8*cm, title="Gestor de solicitudes — Guía del segundo corte", author="Veloza & Galvis").build(S, onFirstPage=foot, onLaterPages=foot)
print("ok")
