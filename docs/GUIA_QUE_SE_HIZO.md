# Guía: cómo funciona, qué se hizo y cómo cumple la entrega

Este documento explica el proyecto con palabras sencillas y relaciona **cada requisito** de la Guía de la Clase 12 y de la plantilla del README con el lugar donde se cumple. Así puedes defenderlo ante el profesor.

## 1. ¿Cómo funciona? (en cristiano)

Imagina una ventanilla digital. Alguien escribe un mensaje y el sistema hace esto, en orden:

1. **Quién eres.** Inicias sesión con tu correo y contraseña de Supabase. A partir de ahí, todo lo que se lee o escribe se hace *con tu identidad*.
2. **Limpieza y seguridad.** Se recorta el mensaje a 600 caracteres y se buscan trampas («ignora tus instrucciones», «dame la API key», «borra la solicitud»). Si hay trampa, se rechaza **sin llamar al modelo**.
3. **Clasificar** (la «función original» del proyecto). El modelo propone: tipo (acceso, documento, pago, queja, consulta, otro), prioridad, si necesita una persona y el código `SOL-0000` si aparece. Pero **el código tiene la última palabra** (reglas R1–R4: por ejemplo, un pago que vence mañana pasa a prioridad alta).
4. **Elegir camino.**
   * Tema sensible → **revisión humana**.
   * Hay código `SOL-xxxx` y preguntan por el estado → **herramienta**.
   * Piden estado sin código, o la pregunta es muy vaga → **aclaración**.
   * Si no, → **RAG**.
5. **Herramienta por MCP.** El modelo *propone* llamar `consultar_estado_solicitud`; el código *valida* (herramienta permitida, formato `SOL-0000`, el código debe estar escrito literalmente en el mensaje) y entonces habla con un **servidor MCP propio** (`servidor_mcp.py`, un programa aparte que solo lee datos ficticios). La respuesta se arma con el dato real.
6. **RAG (responder con los manuales).** La pregunta se convierte en un vector de 384 números (embedding); Supabase busca los 10 fragmentos más parecidos entre los 12 guardados; se pasan los 3 mejores al modelo con la orden de responder **solo** con ese contexto y citar `[F1]`, `[F2]`. El código comprueba que las citas existan y que el estado sea coherente; si no, se abstiene. Si ningún fragmento se parece (< 0,30) ni siquiera llama al modelo.
7. **Guardar.** Pregunta y respuesta (con fuentes, ruta, latencia y tokens) se guardan en tu conversación en Supabase.
8. **Mostrar.** Se ve la respuesta y, debajo, las fuentes («documento › sección (chunk_id)»).

**Seguridad en una frase:** aunque alguien manipulara la interfaz, la base de datos (RLS) solo entrega a cada persona sus propias conversaciones; la interfaz y el estado de Gradio no son la barrera.

## 2. ¿Qué es cada archivo?
| Archivo | Para qué sirve |
|---|---|
| `app/app.py` | La pantalla (login, conversaciones, chat). No tiene lógica del proyecto |
| `app/sistema.py` | El cerebro: pasos 2–6 de arriba |
| `app/almacenamiento.py` | Todo lo de Supabase: sesión, conversaciones, mensajes, lectura del corpus |
| `app/servidor_mcp.py` | El servidor MCP propio (herramienta de estado, solo lectura) |
| `app/preparar_corpus.py` | Se corre **una vez** para subir los manuales ya convertidos a vectores |
| `app/verificar_entrega.py` | Prueba todo contra tus servicios reales y deja evidencia |
| `app/corpus/` | Los 5 manuales ficticios + su catálogo |
| `app/tests/` | 64 pruebas automáticas que no necesitan internet |
| `supabase/setup.sql` | Crea tablas, permisos (RLS) y la función de búsqueda |
| `notebooks/` | Tu trabajo de los cortes anteriores (origen del código) |
| `BITACORA_PROYECTO.md` | La historia completa del proyecto (obligatoria) |
| `docs/` | Estas guías, la revisión de coherencia y el generador de la presentación |

## 3. Qué se hizo respecto de tus notebooks
* **Se conservó** lo que ya habían decidido y evaluado: modelo, prompts `clasif_v2`/`rag_v2`, contratos, reglas, seguridad, umbral, M=10/K=3 y el corpus (mismas huellas que en Colab). La recuperación es la **opción A**, la que eligieron con la evaluación (A, B y C empataron).
* **Se cambió** lo que Colab hacía de forma provisional: `userdata`/`files.upload`/`display` → variables de entorno y funciones; variables globales (`LOG_LLM`, `BITACORA`, `ALMACEN`, `MEMORIA`) → trazas por solicitud, historial en Supabase y sesión por persona; la herramienta local → servidor MCP.
* **Se añadió** lo que pide el tercer corte: login con Supabase Auth, historial por usuario con RLS, interfaz Gradio, MCP propio, pruebas, script de verificación, README, bitácora, presentación y guías.
* **No se tocó** la lógica de recuperación ni los prompts: cambiarlos habría invalidado la evaluación que ya hicieron.

## 4. Requisitos de la Guía de la Clase 12 → dónde se cumplen
| Requisito | Dónde |
|---|---|
| Interfaz Gradio que atiende una solicitud nueva sin ejecutar celdas | `app/app.py` |
| Carpeta `app/` ejecutable con `app.py`, `sistema.py`, `almacenamiento.py`, `servidor_mcp.py` (propio), `requirements.txt`, `.env.ejemplo`, `README.md`, `presentacion_proyecto.pdf` | `app/` |
| Persistir y recuperar conversaciones de cada usuario en Supabase | `almacenamiento.py` + `setup.sql` |
| Identidad por Supabase Auth; sin cliente global mutable; sin clave administrativa | `Almacen._cliente` (cliente efímero con el token de la persona); `leer_config` rechaza claves `secret`/`service_role` |
| Tablas separadas del corpus, RLS de lectura e inserción por propietario; un UUID ajeno no da acceso | `setup.sql` sección B + control de propietario en Python |
| `almacenamiento.py` comprueba el propietario antes de leer o escribir | `asegurar_propietario` |
| Crear una conversación nueva no borra las anteriores | `crear_conversacion` + prueba `test_crear_listar_cargar_en_orden` |
| Persistencia sobrevive a refrescar, cerrar sesión y reiniciar | Los datos están en Supabase; `gr.State` solo guarda la sesión activa |
| Ventana de historial como contexto ≠ conservar todo | `ventana_historial`=6 y `consulta_efectiva` (README, «Qué mensajes se conservan…») |
| Mostrar respuesta, fuentes y resultado de herramientas; manejar aclaraciones, falta de evidencia y errores técnicos | `formatear_respuesta`, rutas de `atender` |
| Conservar validaciones del notebook | `sistema.py` (sanitizar, Pydantic, reglas, `validar_llamada`, `validar_respuesta`) |
| MCP propio documentado: procedencia, versión, transporte, permisos, herramientas | `servidor_mcp.py` + README «Configuración del MCP» |
| Aprobación humana para acciones sensibles | No aplica: solo lectura (explicado en el README) |
| Configuración en `.env`/`.env.ejemplo` con `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` obligatorias | `app/.env.ejemplo`, `almacenamiento.leer_config` |
| `.gitignore` con `.env`, `.env.*`, `!.env.ejemplo`, `.venv/`, `__pycache__/`, `*.pyc`, `*.sqlite3*` | `.gitignore` |
| README completo y reproducible (instalación, variables, corpus, Auth, tablas, RLS, MCP, ejecución, pruebas, despliegue, problemas, limitaciones) | `app/README.md` (plantilla llenada) |
| Despliegue en Render (Root `app`, build, start, `0.0.0.0`, `PORT`) | `app/README.md` y esta guía, paso 10 |
| Pruebas: RAG con fuentes, sin evidencia, entrada incompleta, herramienta, acción prohibida, error técnico; dos usuarios; dos conversaciones; recuperar tras reiniciar; no leer ni escribir lo ajeno | `app/tests/`, `verificar_entrega.py` |
| Presentación PDF para quien no asistió a clase | `app/presentacion_proyecto.pdf` |
| `BITACORA_PROYECTO.md` en la raíz, enlazada desde el README | Raíz |
| Corpus de Supabase y permisos distinguidos del historial | `setup.sql` A vs B; README «Preparación del corpus» |

## 5. Qué NO está hecho todavía (y es tuyo)
1. Ejecutar `verificar_entrega.py` contra tu Supabase y tus claves → la evidencia real de RLS, historial y modelo.
2. Desplegar en Render y registrar URL + pruebas desde esa URL.
3. Revisión humana de las 11 respuestas.
4. Completar fechas, aportes individuales y conclusiones propias en la bitácora.
5. Probar la instalación desde un clon limpio.
Todo está marcado en los documentos con «COMPLETAR» o «Pendiente»; no se rellenó con resultados inventados.

## 6. Preguntas que puede hacer el profesor (y dónde está la respuesta)
* *¿Por qué no usaron reranking si mejora la precisión?* → Empató con A en las 8 preguntas de desarrollo y añadió ≈ 2,9 s; criterio fijado antes de abrir la reserva (bitácora D8).
* *¿Cómo garantizan que un usuario no lea chats ajenos?* → RLS en Postgres + control de propietario + cliente por operación; prueba P4c–P4g con consultas directas a PostgREST.
* *¿Qué pasa si el modelo inventa?* → Validamos citas y estado, pero **no** la fidelidad de cada frase: lo mostró D1; está documentado como limitación y con mitigación propuesta.
* *¿Por qué MCP propio?* → Separa la herramienta del resto, usa el protocolo estándar y evita dependencias de Node; es de solo lectura.
* *¿Qué se envía al modelo del historial?* → Casi nada: solo la pregunta anterior si el turno previo fue una aclaración.
