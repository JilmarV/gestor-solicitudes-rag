# Gestor de solicitudes

Asistente web para una institución educativa. Clasifica las solicitudes que llegan por canales informales, responde con fuentes tomadas de los manuales (RAG), consulta el estado de una solicitud con una herramienta MCP propia y guarda el historial de cada persona en Supabase, con permisos por usuario.

Proyecto final de *Inteligencia Artificial Generativa y Sistemas Inteligentes* (EAM 2026-II).
Equipo: Jilmar Said Veloza Páez y Andrés Felipe Galvis Téllez.

| Pieza | Tecnología |
|---|---|
| Interfaz | Gradio 6 (solo Python: sin HTML, CSS ni JavaScript propios aparte del tema) |
| Modelo | `openai/gpt-oss-20b` en Groq |
| Recuperación | Embeddings `paraphrase-multilingual-MiniLM-L12-v2` + pgvector en Supabase |
| Herramienta | Servidor MCP propio por `stdio`, de solo lectura |
| Usuarios e historial | Supabase Auth + tablas con RLS |

## Qué hay en este repositorio

| Ruta | Contenido |
|---|---|
| `app/` | Aplicación: código, corpus, iconos y pruebas |
| `app/presentacion_proyecto.pdf` | Presentación del proyecto |
| `supabase/setup.sql` | Tablas, políticas RLS y función de búsqueda |

### Archivos de `app/`

| Archivo | Responsabilidad |
|---|---|
| `app.py` | Interfaz Gradio: ingreso, conversaciones, chat con fuentes y estado por sesión (`gr.State`). No contiene lógica del proyecto |
| `sistema.py` | Recorrido de cada mensaje: seguridad de entrada, clasificación, reglas, enrutamiento, RAG, validación y cliente MCP |
| `almacenamiento.py` | Identidad (Auth), conversaciones, mensajes y lectura del corpus en Supabase. Comprueba el propietario antes de leer o escribir |
| `servidor_mcp.py` | Servidor MCP propio con una herramienta de solo lectura |
| `preparar_corpus.py` | Carga única del corpus en Supabase: fragmenta, calcula embeddings y sube |
| `verificar_entrega.py` | Pruebas contra los servicios reales (Auth, RLS, historial, casos de uso) |
| `corpus/` | 13 manuales `.md` ficticios y `catalogo.json` (fuente, versión, licencia, privacidad) |
| `assets/` | Iconos SVG de los botones |
| `tests/` | 83 pruebas automáticas, sin red |
| `requirements.txt` · `requirements-dev.txt` · `.env.ejemplo` | Dependencias, herramientas de prueba y variables (sin secretos) |

## Qué hace

Ante cada mensaje el sistema elige uno de seis caminos:

| Camino | Cuándo | Qué hace |
|---|---|---|
| Rechazo | El texto intenta manipular al sistema, pedir secretos o ejecutar acciones de escritura | Se corta **antes** de llamar al modelo |
| Conversación | El mensaje es solo un saludo, un gracias, una despedida o «¿qué puedes hacer?» | Responde sin modelo ni fuentes y ofrece el menú de temas. «Hola, ¿cómo recupero mi contraseña?» **no** entra aquí: sigue el flujo normal |
| Revisión humana | Tema sensible (por ejemplo, amenaza legal), caso no clasificable o petición de hablar con una persona | Marca el caso para una persona |
| Herramienta (MCP) | Hay un código `SOL-0000` y preguntan por el estado | Consulta de solo lectura y respuesta desde el dato real |
| Aclaración | Piden estado sin código o la pregunta es vaga | Pide el dato que falta |
| RAG | Pregunta informativa sobre los manuales | Busca fragmentos y responde con citas, o dice que no tiene evidencia |

**Temas del corpus:** acceso y contraseñas, constancias, pagos, quejas, seguimiento de solicitudes, tipos y prioridades, tiempos de atención, responsables, canales de atención, privacidad, glosario y ejemplos de solicitudes.

**Fuera del alcance.** No crea, edita ni borra solicitudes. No hay base real de solicitudes ni autenticación de quien consulta un código. No responde sobre temas que no estén en los manuales. No procesa datos personales reales. Los manuales y las solicitudes `SOL-1001…SOL-1004` (en `servidor_mcp.py`) son **ficticios**.

### Recorrido de una solicitud

```
Gradio (app.py)                                   Supabase Auth: cada persona inicia sesión
   │  mensaje + sesión de ESA persona                         │ token por sesión, no global
   ▼                                                          ▼
almacenamiento.py ── comprueba propietario ── guarda el mensaje ──► conversaciones / mensajes (RLS)
   │
   ▼
sistema.atender(texto, sesión, historial)
   1 sanitizar (longitud, patrones de inyección)             → rechazo
   2 conversación social (saludos, gracias…)                 → respuesta directa
   3 clasificar (Structured Outputs + Pydantic + reglas)     → revisión humana
   4 decidir ruta ──► herramienta: el modelo PROPONE, el código VALIDA (lista blanca, SOL-0000,
   │                  código literal en el mensaje) → cliente MCP ⇄ servidor_mcp.py (stdio)
   │              └─► aclaración
   └─► RAG: embedding de la pregunta → pgvector (top-10) → top-3 → prompt rag_v2 → JSON validado
            (citas existentes, estado coherente) → respuesta con fuentes [F1]… o «evidencia insuficiente»
   ▼
almacenamiento.py ── guarda la respuesta + metadatos (ruta, estado, fuentes, latencia, tokens)
   ▼
Gradio muestra respuesta + fuentes
```

| Elemento | Valor |
|---|---|
| Modelo | `temperature=0`, `reasoning_effort="low"` (variable `GROQ_MODEL`) |
| Embeddings | 384 dimensiones, normalizados, similitud coseno, revisión fijada (se lee de la configuración guardada con el corpus; opcional `EMB_REVISION`) |
| RAG | Recuperación semántica, M=10 candidatos, K=3 fragmentos al modelo, umbral heurístico 0,30 |
| Flujo | El modelo propone y el código decide: las reglas de negocio están en código |
| Fuentes | Cada fragmento conserva `source`, `section`, `version`, `source_hash` y `chunk_id`; la respuesta cita `[F1]…` tras verificar que la cita existe |

### Qué mensajes se conservan y cuáles llegan al modelo

- **Se conservan todos** en Supabase (`mensajes`), con metadatos: `ruta`, `estado`, `fuentes`, `limitacion`, `latencia_ms`, tokens y versiones de prompt. Son de solo-añadir.
- La interfaz carga hasta 200 mensajes al abrir una conversación y el sistema usa una **ventana de los 6 últimos** (`ventana_historial`).
- **Al modelo solo llega** el mensaje actual y, únicamente cuando el turno anterior del asistente fue una *aclaración*, la pregunta anterior unida a la respuesta («Dime el estado de mi solicitud» → «SOL-1003»). No es una memoria conversacional completa.
- El historial se recupera de la base de datos, no de `gr.State`: sobrevive a refrescar la página, cerrar sesión y reiniciar el servidor.

## Interfaz

Todo el diseño se hace con Gradio: un tema (`TEMA`) y una hoja de estilos (`CSS`) en `app/app.py`, que se pasan a `launch()`.

- **Login:** cabecera con el título y el aviso de datos ficticios, y el formulario centrado.
- **Chat:** barra superior con la sesión y *Salir*, **barra lateral** (`gr.Sidebar`) con *Nueva conversación* y la lista de conversaciones, y el chat con las fuentes de cada respuesta.
- **Estado vacío:** seis preguntas de ejemplo como botones. Un clic las pone en la caja; la persona decide cuándo enviarlas. Se editan en la constante `EJEMPLOS`.
- **Iconos:** SVG de trazo en `app/assets/`, usados con `gr.Button(icon=...)`. El birrete de la cabecera va en línea.
- **Modo oscuro:** paleta completa, que se activa desde *Configuración* en el pie de Gradio o con `?__theme=dark` en la URL. En el CSS, cada regla `.dark` va en su propia línea: Gradio antepone su contenedor y, en una lista con comas, solo el primer selector queda bien.
- **Pie de Gradio:** *Runs*, *Usar vía API*, *Construido con Gradio* y *Configuración* se conservan. El chat se ajusta a la altura de la ventana para que el pie quede a la vista.
- **Celular:** el menú lateral se abre por defecto y cubre el chat hasta cerrarlo con la flecha.
- Sin animaciones de carga, y se respeta `prefers-reduced-motion`.

## Requisitos

- **Python 3.11** (la versión con la que se desarrolló y probó). Las dependencias están en `app/requirements.txt`: `gradio==6.32.0`, `supabase==2.32.0`, `groq==1.7.0`, `pydantic==2.13.5`, `mcp==1.30.0`, `python-dotenv==1.2.4` y `sentence-transformers==6.1.0`. Para las pruebas, `app/requirements-dev.txt` añade `pytest`.
- **Cuentas:** un proyecto de **Supabase** (Auth + Postgres con pgvector) y una cuenta de **Groq** con clave de API. Para desplegar, una cuenta de **Render**.
- **Embeddings:** el modelo pesa unos 470 MB y se descarga de Hugging Face la primera vez. Con PyTorch en CPU la aplicación necesita entre 1 y 2 GB de RAM.
- Node no hace falta: el MCP es Python. SQLite no se usa.

## Instalación

Desde una carpeta donde clonar el repositorio:

```powershell
git clone https://github.com/JilmarV/gestor-solicitudes-rag.git
cd gestor-solicitudes-rag
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r app/requirements.txt
Copy-Item app/.env.ejemplo app/.env
```

En Linux o macOS: `python3 -m venv .venv`, `.venv/bin/python -m pip install -r app/requirements.txt` y `cp app/.env.ejemplo app/.env`.

## Variables y secretos

Completa `app/.env` antes de ejecutar. Se carga con `python-dotenv` y las variables del alojamiento tienen prioridad. **`.env` no se sube** (está en `.gitignore`); solo se publica `.env.ejemplo`.

| Variable | Uso | ¿Obligatoria? |
|---|---|---|
| `GROQ_API_KEY` | Clave del proveedor del modelo | Sí (salvo `MODO_LLM=mock`, solo pruebas) |
| `GROQ_MODEL` | Modelo; por defecto `openai/gpt-oss-20b` | No |
| `SUPABASE_URL` | URL del proyecto (`https://xxxx.supabase.co`) | Sí |
| `SUPABASE_PUBLISHABLE_KEY` | Clave **publishable** (`sb_publishable_…`). La app **rechaza** claves `sb_secret_` y `service_role` | Sí |
| `MCP_MODO` | `stdio` (arranca `servidor_mcp.py` como subproceso) o `local` (solo pruebas; la interfaz lo avisa) | No (por defecto `stdio`) |
| `MODO_LLM` | `groq` o `mock` (solo pruebas; la interfaz lo avisa) | No (por defecto `groq`) |
| `CORPUS_ID` | Identificador del corpus en Supabase | No (por defecto `gestor-solicitudes-v1`) |
| `EMB_REVISION` | Revisión exacta del modelo de embeddings; si falta, se lee de la configuración guardada con el corpus | No |
| `GRADIO_SERVER_NAME` | `127.0.0.1` en local, `0.0.0.0` en alojamiento | No |
| `PORT` | Puerto HTTP; por defecto `7860` (en Render lo da la plataforma) | No |

No hay contraseñas de usuarios en `.env`: cada persona inicia sesión con su cuenta de Supabase Auth. `preparar_corpus.py` y `verificar_entrega.py` piden las contraseñas por teclado, sin mostrarlas. Nunca se usa la clave administrativa de Supabase para saltarse los permisos.

## Preparación de Supabase y del corpus

1. **Tablas y permisos:** ejecuta `supabase/setup.sql` completo en el editor SQL de tu proyecto.
2. **Usuarios de prueba:** en *Authentication → Users → Add user → Create new user*, con correo y contraseña y marcando **Auto Confirm User**. Crea al menos dos (por ejemplo `ana@…` y `beto@…`) y la cuenta del equipo que carga el corpus. Las contraseñas no van al repositorio.
3. **Cargar el corpus** (una sola vez, desde `app/`):

   ```powershell
   ..\.venv\Scripts\python.exe preparar_corpus.py --email CUENTA_DEL_EQUIPO
   ```

   Fragmenta, calcula embeddings **solo si el índice guardado no coincide** (ids, huellas, modelo y revisión) y sube a `clase08_fragmentos`. Es idempotente. `--forzar` recalcula aunque el índice esté vigente y `--solo-fragmentos` solo fragmenta e imprime, sin Supabase ni embeddings.

**Fragmentación.** Por secciones (`##`); si una sección supera 110 tokens se parte en ventanas con solape de 12, y a cada fragmento se le antepone «Título / Sección». Con el corpus actual: **13 documentos y 104 fragmentos**, de máximo 76 tokens (el límite del modelo es 128).

**En cada pregunta** solo se calcula el embedding de la pregunta y se llama a `clase08_buscar_fragmentos`. Nunca se vuelve a insertar el corpus.

**Quién lee el corpus.** Cualquier usuario *autenticado* puede leerlo (son manuales ficticios); insertar, actualizar y borrar sigue siendo solo del propietario de la fila. La función de búsqueda usa `security invoker` (respeta RLS) y `distinct on (chunk_id)` por si dos cuentas cargaron el mismo `corpus_id`.

## Usuarios e historiales

| Tabla | Columnas clave | Propietario | Orden |
|---|---|---|---|
| `conversaciones` | `id` (uuid), `usuario_id` (= `auth.uid()`), `titulo`, `created_at`, `updated_at` | `usuario_id` | por `updated_at` (la actualiza un trigger al insertar mensajes) |
| `mensajes` | `id` (identidad creciente), `conversacion_id`, `usuario_id`, `rol` (`user`/`assistant`), `contenido`, `metadata` (jsonb), `created_at` | `usuario_id` + conversación del mismo dueño | por `id` |

**Políticas RLS** (todas `to authenticated`):

- `conversaciones`: select, insert, update y delete solo si `usuario_id = auth.uid()`.
- `mensajes`: select e insert solo si `usuario_id = auth.uid()` **y** la conversación existe y es del mismo usuario. No hay update ni delete.
- `anon` no tiene permisos. Conocer un UUID no concede acceso.

**Recuperación del historial.** Al iniciar sesión se listan las conversaciones de la persona (la más reciente se abre sola) y se cargan sus mensajes desde Supabase; al elegir otra en la barra lateral se cargan los suyos. Crear una nueva no elimina las anteriores.

**Sesión sin cliente compartido.** `app.py` guarda una `SesionUsuario` por pestaña en `gr.State`. `almacenamiento.py` crea un cliente efímero por operación con el token de esa persona (`apikey` = clave publishable, `Authorization: Bearer <token del usuario>`) y refresca el token cuando va a vencer. No existe un cliente global cuya sesión pueda cambiar. La identidad la valida Supabase Auth, no Gradio.

## Configuración del MCP

| Campo | Valor |
|---|---|
| Nombre | `gestor-solicitudes-estado` |
| Procedencia | **Propio**, escrito por el equipo |
| Versión | 1.0.0 (`python servidor_mcp.py --version`) |
| SDK | `mcp==1.30.0` (`FastMCP`) |
| Transporte | `stdio`: la aplicación arranca `servidor_mcp.py` como subproceso con el mismo Python. No escucha en la red |
| Herramientas | **Una:** `consultar_estado_solicitud(codigo)`, solo lectura. El cliente descubre las herramientas con `list_tools` y solo usa esa (lista blanca) |
| Autorización | No requiere credenciales: es un subproceso local sobre datos ficticios. La llamada solo se ejecuta si pasa `validar_llamada` |

Normalmente **no hay que arrancarlo**: lo inicia `sistema.py` en cada consulta de estado. Para diagnosticar: `python servidor_mcp.py` (queda esperando por stdin).

**Cómo se usa.** «¿Cuál es el estado de SOL-1003?» → clasificación → ruta `herramienta` → el modelo propone la llamada → `validar_llamada` (lista blanca, patrón `^SOL-[0-9]{4}$`, el código debe aparecer **literalmente** en el mensaje) → `ClienteMCP` ⇄ `servidor_mcp.py`. La prueba `test_mcp_stdio_real` lo comprueba con un subproceso MCP real.

**Acciones sensibles.** La herramienta no tiene efectos, por eso no requiere aprobación humana. Las peticiones de escritura en texto («Borra la solicitud SOL-1001») se rechazan antes de llamar al modelo. Si se añadiera una herramienta de escritura, debería mostrar el recurso afectado y pedir confirmación antes de ejecutarla.

**Errores.** Si el subproceso no arranca, expira (20 s) o responde con una forma inesperada, `sistema.py` devuelve «El servicio de consulta de estados no está disponible…» (`ruta=error_controlado`), sin trazas ni claves.

## Ejecución local

Con Supabase listo, el corpus cargado y `app/.env` completo, desde `app/`:

```powershell
..\.venv\Scripts\python.exe app.py
```

En Linux o macOS: `../.venv/bin/python app.py`.

- URL local: **http://127.0.0.1:7860** (o el `PORT` que definas). La primera consulta tarda más: descarga y carga el modelo de embeddings.
- Para detener la aplicación: `Ctrl + C`.
- Si el puerto 7860 está ocupado, arranca con otro: `$env:PORT=7861; python app.py`.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pip install -r app/requirements-dev.txt     # solo la primera vez
cd app
..\.venv\Scripts\python.exe -m pytest tests -q                             # 83 pruebas, sin red ni claves
..\.venv\Scripts\python.exe verificar_entrega.py --email-a ana@… --email-b beto@…   # contra Supabase y Groq reales
```

- **`pytest`** usa un Supabase simulado y un modelo simulado: comprueba la lógica de Python, **no** las políticas de Postgres ni al modelo real. Cubre los caminos del sistema (rechazo, conversación, humano, herramienta, aclaración, RAG, errores controlados), el aislamiento entre usuarios, el orden y la recuperación del historial, el MCP por `stdio` y la interfaz de extremo a extremo.
- **`verificar_entrega.py`** prueba contra los servicios reales (Auth, RLS, historial) y escribe `evidencias/resultados_app.md` y `.json` en la raíz del repositorio con lo realmente observado, sin claves. `--sin-modelo` omite Groq y los embeddings; `--limpiar` borra las conversaciones de prueba.

| Verificación | Estado |
|---|---|
| Lógica de Python, aislamiento entre usuarios e historial (simulados) | Cubierta por las 83 pruebas |
| RLS real de Postgres, historial tras reiniciar el servidor, casos con el modelo real | Pendiente de ejecutar con `verificar_entrega.py` |
| Instalación desde un clon limpio | Pendiente |
| Prueba desde la URL desplegada | Pendiente: aún no hay despliegue |

## Despliegue de referencia en Render

1. Conecta el repositorio y crea un **Web Service** con runtime **Python**.
2. Elige la rama probada y configura **Root Directory: `app`**.
3. **Build Command:** `pip install -r requirements.txt`. **Start Command:** `python app.py`.
4. En **Environment** registra `GROQ_API_KEY`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` y `GRADIO_SERVER_NAME=0.0.0.0` (opcionales `GROQ_MODEL` y `EMB_REVISION`). La aplicación lee `PORT` del servicio. No se añaden al repositorio.
5. Prepara antes Supabase: ejecuta `setup.sql`, crea los usuarios y corre `preparar_corpus.py` desde tu máquina contra el mismo proyecto.
6. **Memoria:** el modelo de embeddings con PyTorch necesita entre 1 y 2 GB. Según la documentación de Render, el plan gratuito y `starter` tienen 512 MB y `standard` (`1c-2g`) tiene 2 GB, por lo que se recomienda `1c-2g` ([planes de cómputo](https://render.com/docs/compute-plans)). Con 512 MB es probable que el proceso se cierre al cargar el modelo (no se pudo medir).
7. El corpus y las conversaciones viven en **Supabase**; el disco del servidor no guarda nada necesario.
8. Despliega, revisa los *logs* (no imprimen claves) y prueba los casos desde la URL pública.

**Estado:** no desplegado. Registra aquí la URL pública, el commit evaluado y la fecha de prueba cuando exista. Un enlace temporal con `share=True` no sustituye este alojamiento.

## Seguridad y problemas frecuentes

**Datos:** solo manuales y códigos ficticios. **Permisos:** corpus legible por usuarios autenticados; historial privado por persona (RLS más control de propietario); `anon` sin acceso. **Secretos:** solo en `app/.env` o en el panel del alojamiento; `.gitignore` excluye `.env*` salvo `.env.ejemplo`, y los registros y errores pasan por `redactar()`. Si una clave llegó al repositorio, **revócala o rótala** en el proveedor y limpia el historial de Git: ocultarla después no la protege.

| Síntoma | Qué revisar (sin desactivar controles) |
|---|---|
| «Faltan SUPABASE_URL…» o «Esa es una clave administrativa» | `app/.env`; usa la clave **publishable** de *Project Settings → API* |
| «No se pudo iniciar sesión» | Usuario creado en *Authentication → Users*, confirmado (Auto Confirm) y contraseña correcta |
| Acceso denegado o «new row violates row-level security» | ¿Ejecutaste `setup.sql` completo? ¿Hay sesión vigente? Nunca desactives RLS ni uses la clave secret |
| «El corpus está vacío o no es legible» | Ejecuta `preparar_corpus.py`; confirma que `CORPUS_ID` coincide y que existe la política `corpus_lectura_autenticados` |
| «La configuración de embeddings del corpus no coincide» | El corpus se indexó con otro modelo: vuelve a correr `preparar_corpus.py --forzar` |
| Falta `GROQ_API_KEY` o «servicio de IA no disponible» | Clave y cuota de Groq; el sistema deriva a revisión humana, no inventa |
| Proceso reiniciado o «Out of memory» en el alojamiento | Falta de RAM al cargar el modelo de embeddings: sube a un plan de al menos 2 GB |
| «Servicio de consulta de estados no disponible» | El subproceso MCP no arrancó: mismo entorno virtual, `mcp` instalado, `python servidor_mcp.py --version` |
| Primera respuesta muy lenta | Descarga del modelo (~470 MB) y arranque en frío; las siguientes son rápidas |
| «Cannot find empty port» al arrancar | El puerto 7860 está ocupado: define otro con la variable `PORT` |

## Limitaciones conocidas

- **Fidelidad del modelo.** La validación comprueba que las citas existan y sean coherentes con el estado, pero **no demuestra que cada afirmación esté respaldada** por el fragmento. En una prueba anterior una respuesta cambió «no basta con repetir el envío» por «no es necesario repetir». Mitigación pendiente: endurecer el prompt y repetir una revisión humana de las respuestas.
- **Umbral de abstención 0,30:** es heurístico. En una evaluación anterior no filtró un caso fuera de alcance; lo hizo el modelo.
- **Seguridad por patrones:** no detiene toda inyección. Se mitiga con una herramienta de solo lectura, respuestas ancladas al contexto y validación de citas.
- **Conversación social por listas de frases:** `respuesta_social` solo reconoce mensajes cortos y conocidos; lo demás sigue el flujo normal.
- **Memoria conversacional mínima:** solo se une la respuesta a una aclaración con la pregunta anterior. No resuelve referencias como «¿y eso cuánto cuesta?».
- **Datos y herramienta ficticios**, sin autenticación de quien consulta un código y sin pruebas de carga ni de concurrencia.
- **Latencia:** cada respuesta con modelo tarda unos segundos. En la consulta de estado se suma la apertura del subproceso MCP.
- **Doble envío:** no hay idempotencia por mensaje; un doble clic podría guardar dos veces la misma pregunta.
- **Dependencias externas:** un LLM y un modelo de embeddings, sujetos a cambios del proveedor.

## Referencias

Gradio — [estado en Blocks](https://www.gradio.app/guides/state-in-blocks); Supabase — [Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security), [`auth.getUser`](https://supabase.com/docs/reference/python/auth-getuser), [RAG con permisos](https://supabase.com/docs/guides/ai/rag-with-permissions); Render — [Web Services](https://render.com/docs/web-services), [variables de entorno](https://render.com/docs/configure-environment-variables), [planes de cómputo](https://render.com/docs/compute-plans); Groq — [salida estructurada](https://console.groq.com/docs/structured-outputs); [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk); [Sentence Transformers](https://sbert.net).

Datos: manuales y solicitudes **ficticios**, redactados por el equipo, de uso académico. Si cambias el código, actualiza aquí versiones, comandos y la tabla de verificación.
