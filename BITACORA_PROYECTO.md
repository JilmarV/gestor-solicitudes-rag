# Bitácora unificada — Gestor de solicitudes

**Inteligencia Artificial Generativa y Sistemas Inteligentes · EAM 2026-II · Profesor: Robert García Rey**
**Equipo:** Jilmar Said Veloza Páez · Andrés Felipe Galvis Téllez

Documentación integral de los **tres cortes**. Los enlaces son relativos al repositorio. No contiene claves ni datos personales. Las instrucciones de instalación y despliegue están en [`app/README.md`](app/README.md).

> **Cómo leer las marcas.** ⚠️ **COMPLETAR** = dato que solo el equipo conoce y que no se inventó (fechas de cada práctica, aportes individuales, resultados en servicios reales). «Pendiente» = no ejecutado todavía. Todo lo demás procede de archivos del repositorio (notebooks con sus salidas, guías) o de ejecuciones descritas con su configuración.

## 1. Problema, usuarios, objetivos y alcance

* **Problema.** Llegan muchas solicitudes por canales informales («no puedo entrar», «¿ya me dieron la constancia?», «¿cómo va SOL-1003?»). Hay que entender qué pide la persona, responder con información correcta de los manuales y consultar el estado de una solicitud, sin inventar datos y sin exponer información sensible.
* **Usuarios.** Estudiantes y personal (preguntan); equipo de atención (recibe lo que requiere una persona); equipo docente/técnico (audita: por eso hay fuentes y trazas).
* **Objetivo.** Un asistente que, ante un mensaje, elige entre cinco caminos y actúa de forma controlada y verificable: rechazo, revisión humana, herramienta, aclaración y RAG.
* **Alcance.** Clasificar (tipo, prioridad, revisión humana), responder con fuentes, consultar estados de solicitudes ficticias en modo lectura, y guardar el historial por usuario. **Fuera de alcance:** modificar solicitudes, datos reales, autenticar a quien consulta un código, temas ajenos a los 5 manuales.
* **Cambios respecto de la propuesta inicial.** (1) Del clasificador/consulta de estado del primer corte se pasó a un asistente con RAG (segundo corte). (2) En el tercer corte la herramienta pasó de función local a **servidor MCP propio**, y la memoria temporal (`MEMORIA`, diccionario de Colab) pasó a **historial persistente por usuario en Supabase**. ⚠️ **COMPLETAR:** si la propuesta inicial decía algo distinto, anótalo aquí.

## 2. Arquitectura final y recorrido de una solicitud

Diagrama y tabla de componentes en [`app/README.md`](app/README.md#arquitectura-y-procedencia-del-código). Resumen:

`Gradio (app.py)` → `almacenamiento.py` (identidad + guarda mensaje) → `sistema.atender` [sanitizar → clasificar → ruta → *rechazo / humano / herramienta MCP / aclaración / RAG*] → `almacenamiento.py` (guarda respuesta y metadatos) → interfaz con fuentes.

| Componente | Archivo | Origen (notebook) |
|---|---|---|
| Función original `clasificar` + contrato + reglas R1–R4 | `app/sistema.py` | Consolidado §5 (evolución de Clases 03 y 04) |
| Seguridad de entrada y errores controlados | `app/sistema.py` | §1 y §8 |
| Herramienta de estado | `app/servidor_mcp.py` + `ClienteMCP` en `sistema.py` | §7 (Clases 04 y 07) |
| Corpus, chunking, embeddings, índice | `app/corpus/`, `app/preparar_corpus.py`, `supabase/setup.sql` | §2, §3, §4 (Clases 06, 07, 08) |
| Recuperación + RAG con citas + validación | `app/sistema.py` | §9 (Clases 08 y 09) |
| Enrutamiento `atender` | `app/sistema.py` | §10 |
| Historial por usuario, Auth, RLS | `app/almacenamiento.py`, `supabase/setup.sql` | Nuevo en el tercer corte (sustituye `MEMORIA`) |
| Interfaz | `app/app.py` | Nuevo (Clase 12; §10 como entrada) |
| Evaluación A/B/C | notebooks Clase 09 y consolidado §11–12 | Clase 09 |

## 3. Decisiones técnicas y su justificación

| # | Decisión | Justificación | Dónde se ve |
|---|---|---|---|
| D1 | LLM `openai/gpt-oss-20b` en Groq, `temperature=0`, `reasoning_effort="low"` en clasificación y RAG de la app | Es el modelo del primer corte y de las Clases 08–09; temperatura 0 por reproducibilidad | `sistema.py` `CONFIG` |
| D2 | Prompts versionados `clasif_v2` y `rag_v2` en el código y en cada mensaje guardado | Trazabilidad de qué prompt produjo cada respuesta | `sistema.py` `PROMPTS` · `mensajes.metadata.prompts` |
| D3 | Salida controlada en 3 capas: Structured Outputs estricto → Pydantic `extra="forbid"` → reglas de negocio en código | «El modelo propone, el código decide» | `sistema.py` `Solicitud`, `aplicar_reglas_negocio` |
| D4 | Corpus **ficticio** de 5 manuales con catálogo (fuente, versión, licencia, privacidad) | Evitar datos personales y problemas de licencia | `app/corpus/` |
| D5 | Fragmentar por secciones `##`, ventanas con solape solo si > 110 tokens, encabezado «Título / Sección» | Cada sección responde una pregunta concreta; encabezado da contexto al embedding | Colab: 12 fragmentos, máx. 76 tokens |
| D6 | Embeddings `paraphrase-multilingual-MiniLM-L12-v2` (384, normalizados, coseno) con revisión fijada | Multilingüe y liviano (CPU) | `configuracion` en cada fila |
| D7 | Supabase (pgvector + RLS) y **reutilizar** el índice si ids, huellas, modelo y revisión coinciden | No re-embeber por pregunta ni por reinicio | Colab: «Índice vigente… Sin re-embeber» |
| D8 | Recuperación **A · semántica** | A, B y C empataron en calidad; criterio previo MRR > Recall@3 > simplicidad; C costaba ≈ 2,9 s más por consulta de recuperación | [Resultados](evidencias/resultados_colab_segundo_corte.md) §2 |
| D9 | Umbral de abstención 0,30 antes de llamar al modelo | Heurística barata; el modelo además puede abstenerse | `CONFIG["umbral_similitud"]` |
| D10 | Herramienta **solo lectura** + validación (lista blanca, `^SOL-[0-9]{4}$`, código literal en el mensaje) | Reducir el daño de una inyección | `validar_llamada` |
| D11 | **MCP propio** por stdio con una sola herramienta | Cumple «MCP propio o existente» con una necesidad real (separar la herramienta); sin dependencias de Node | `servidor_mcp.py` |
| D12 | Identidad por **Supabase Auth**, clave **publishable** y **cliente efímero por operación** con el token de la persona | No compartir un cliente autenticado mutable entre usuarios; RLS como barrera real | `almacenamiento.py` |
| D13 | Historial en `conversaciones` y `mensajes`, mensajes **solo-añadir**, orden por identidad creciente | Orden estable y auditoría | `supabase/setup.sql` |
| D14 | Corpus de **lectura compartida** para usuarios autenticados; escritura solo del dueño; historial **privado** | La política original (`owner_id = auth.uid()`) impedía que un usuario nuevo consultara el corpus | `setup.sql` sección A |
| D15 | Contexto al modelo: mensaje actual + (solo si el turno previo fue aclaración) la pregunta anterior; ventana de 6 mensajes cargada | Conservar ≠ enviar; comportamiento simple y comprobable | `consulta_efectiva` |
| D16 | Despliegue en Render (Web Service, `app/` como raíz) | Ruta de referencia de la guía | [`app/README.md`](app/README.md#despliegue-de-referencia-en-render) |
| D17 | Dependencias fijadas; **Gradio 6.32.0** | `gradio 5.50.0` es incompatible con `pydantic 2.13.5` (conflicto de resolución al instalar), versión usada en las Clases 08–09 | `requirements.txt` |

## 4. Línea de tiempo y versiones

| Corte / hito | Alcance | Fecha | Evidencia |
|---|---|---|---|
| 1.er corte (Clases 02–05) | Tokens y contexto mínimo, función original, contrato de salida, herramienta, seguridad | ⚠️ **COMPLETAR** | Reunido en el consolidado §1, §5–§8 (no se recibieron las notas originales de estas clases) |
| 2.º corte (Clases 06–09) | Embeddings, ingestión e índice, RAG con Supabase y Groq, mejora y evaluación | Octubre 2026 (portada de la guía) · ⚠️ **COMPLETAR** fecha de cada práctica | [`notebooks/`](notebooks/) · [`evidencias/Guia_Segundo_Corte.pdf`](evidencias/Guia_Segundo_Corte.pdf) |
| 3.er corte (Clases 10–12) | Aplicación Gradio, MCP, historial por usuario, despliegue, bitácora y presentación | Preparado el 16-nov-2026 | `app/` · `supabase/setup.sql` |

Versiones usadas en Colab (de los notebooks): `sentence-transformers 6.1.0`, `supabase 2.32.0`, `groq 1.7.0` (Clases 08–09), `pydantic 2.13.5`, `rank-bm25 0.2.2`. Reranker: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, revisión `1427fd652930e4ba29e8149678df786c240d8825`. Aplicación (16-nov-2026): `gradio 6.32.0`, `supabase 2.32.0`, `groq 1.7.0`, `pydantic 2.13.5`, `mcp 1.30.0`, Python 3.13.

## 5. Experimentos y pruebas con resultados

### 5.1 Segundo corte (Colab, consolidado) — configuración: M=10, K=3, `gpt-oss-20b`, 12 fragmentos

Detalle completo, con todas las cifras: [`evidencias/resultados_colab_segundo_corte.md`](evidencias/resultados_colab_segundo_corte.md).

| Experimento | Esperado | Observado | Evidencia |
|---|---|---|---|
| Fragmentación «ventanas» vs «párrafos» | Posible diferencia | Idénticas: 12 fragmentos, máx. 76 tokens | §1 |
| Reutilización del índice | No re-embeber si no cambió | `indice_vigente() = True`; construcción inicial 2,1 s | §1 |
| A vs B vs C en desarrollo (8 preg.) | Mejora de B/C sobre A (hipótesis) | **Empate:** MRR 1,000 / Recall@3 1,000 las tres; latencias 202,1 · 160,8 · 3098,2 ms | §2 |
| Reserva (3 preg., una sola apertura) | Confirmar la decisión | A: MRR 1,000 / Recall@3 1,000 (incluye R3 «contraseña») | §3 |
| Comportamiento C1–C3 | evidencia insuficiente / aclaración / aclaración | Los tres correctos y sin fuentes inventadas | §4 |
| 8 casos integrados | Ruta esperada en los 8 | 8/8; latencia 0–8,1 s | §5 |
| Falla simulada del modelo | Respuesta segura sin claves | Correcta | §5 |
| Revisión humana de 11 respuestas | — | **Pendiente.** Lectura preliminar de D1–D3: D2 y D3 fieles; D1 no | §6 |

### 5.2 Tercer corte (aplicación)

| Prueba | Configuración | Esperado | Observado | Evidencia |
|---|---|---|---|---|
| Suite offline `pytest` (64 pruebas) | Python 3.13, Supabase y modelo **simulados**, MCP **real** por stdio, Gradio real con `gradio_client` | Todas pasan | **64 pasan** (16-nov-2026) | `app/tests/` |
| Aislamiento entre usuarios (lógica Python) | RLS simulado activo y desactivado | B no lee ni escribe en conversación de A aun con su UUID | Rechazado en ambos casos | `test_usuario_no_lee_ni_escribe_conversacion_ajena` |
| Token por persona | Transporte HTTP simulado con el cliente real de supabase-py | `Authorization` = token de cada persona, `apikey` = clave publishable | Correcto | `test_cliente_real_envia_authorization_del_usuario` |
| Historial tras «reiniciar» | Nuevo `Almacen` + nueva sesión | Mismos mensajes y orden | Correcto | `test_historial_sobrevive_a_nueva_sesion_y_nuevo_objeto` |
| UI completa con 2 usuarios | `gradio_client` | Chat, 2.ª conversación sin borrar la 1.ª, B no ve lo de A | Correcto | `tests/test_app.py` |
| MCP propio | Subproceso real | Solo expone `consultar_estado_solicitud`; SOL-1003 → pendiente de documentos | Correcto | `tests/test_sistema.py` |
| **RLS real, historial real, 8 casos con Groq y embeddings reales** | Proyecto de Supabase del equipo | Ver `verificar_entrega.py` (P1–P6) | **Pendiente de ejecutar por el equipo** | `evidencias/resultados_app.md` (se genera al ejecutar) |
| Instalación desde clon limpio · URL desplegada | — | Igual que local | **Pendiente** | — |

> Las pruebas offline verifican la lógica de Python con un Supabase simulado; **no sustituyen** la comprobación de las políticas RLS reales ni de las respuestas del modelo real.

## 6. Errores y limitaciones encontrados, correcciones y verificaciones

| # | Hallazgo | Corrección / estado |
|---|---|---|
| E1 | La guía del 2.º corte (§7.1, §8) daba por probable que la pregunta R3 («contraseña») fallara con BM25 solo y dejaba la tabla 7.2 y la revisión humana en blanco | Con embeddings reales R3 **sí** recupera `acceso-01` (A, B y C con Recall@3 = 1,0). Las tablas se completaron con las salidas de Colab ([§2–3 de los resultados](evidencias/resultados_colab_segundo_corte.md)). La revisión humana sigue pendiente |
| E2 | La guía decía «el mayor fragmento ≈ 63 tokens» (tokenizador de prueba) | Con el tokenizador real el máximo es **76** (límite 128). Dato corregido |
| E3 | **Fidelidad del modelo:** D1 añadió una afirmación ausente del fragmento y cambió «no basta con repetir» por «no es necesario repetir» | Registrado. La validación de citas no lo detecta. Mitigación propuesta: prompt más estricto (`rag_v3`) y nueva revisión humana. **No aplicada** porque no se evaluó |
| E4 | El SQL de la Clase 08 (`owner_id = auth.uid()` también en lectura) impedía que un usuario nuevo leyera el corpus | `setup.sql` cambia solo la política de lectura del corpus; el historial queda privado (D14) |
| E5 | Si dos cuentas cargan el mismo `corpus_id`, la búsqueda devolvería duplicados | La función usa `distinct on (chunk_id)` |
| E6 | Dos prompts distintos se llaman `rag_v2`: el de la Clase 08 y el del consolidado | En la app `rag_v2` es el del consolidado (el evaluado en Colab). Recomendación: nombrar `rag_v2` solo uno si se vuelve a editar |
| E7 | La abstención del caso «cafetería» la decidió el modelo; el umbral 0,30 no lo filtró | Limitación documentada; calibrar con más casos |
| E8 | `gradio 5.50.0` no instala con `pydantic 2.13.5` | Se fijó `gradio 6.32.0` y se probó (64 pruebas) |
| E9 | La plantilla pide `MCP_URL`; el MCP propio por stdio no la usa | Se **retiró** de `.env.ejemplo` y se documentó `MCP_MODO` |
| E10 | Las Clases 07–09 usaron otro corpus (`soporte_didactico-<huella>`, 7 fragmentos por párrafo, solo acceso y constancias) y el consolidado usa `gestor-solicitudes-v1` (5 manuales, 12 fragmentos) en la misma tabla | No es un error: son construcciones distintas. La app usa solo `gestor-solicitudes-v1` |
| E11 | El notebook de la Clase 11 (MCP y `MEMORIA`) no estaba entre los archivos revisados | MCP e historial se construyeron a partir del consolidado. ⚠️ **COMPLETAR:** si tu Clase 11 tiene otro MCP, indícalo y se alinea |

**Limitaciones vigentes:** corpus pequeño (las diferencias A/B/C pueden ser ruido); 11 preguntas anotadas por el mismo equipo; umbral heurístico; seguridad por patrones; herramienta sobre datos ficticios; un solo LLM y un solo modelo de embeddings; sin pruebas de carga; sin idempotencia de mensajes; memoria conversacional mínima.
**Pendientes:** ejecutar `verificar_entrega.py`; revisión humana de las 11 respuestas; prueba de instalación desde clon limpio; despliegue y prueba desde la URL pública; medir memoria real en Render.

## 7. Funcionamiento final

Una persona inicia sesión con su cuenta de Supabase Auth, ve solo sus conversaciones, escribe un mensaje y recibe una respuesta con fuentes (o una aclaración, un rechazo, un estado de solicitud o la derivación a una persona). Cada turno queda guardado con su ruta, estado, fuentes, latencia y tokens. Al volver a entrar, recupera su historial.

## 8. Conclusiones del equipo

1. En un corpus tan pequeño, la recuperación semántica simple alcanzó el máximo posible; el reranking solo añadió latencia. La mejora no se justifica con estos datos, y eso también es un resultado.
2. Validar que una cita *exista* no demuestra que la afirmación esté respaldada: hace falta revisión humana y, quizá, verificación de fidelidad.
3. Persistir el historial y decidir qué se envía al modelo son responsabilidades distintas.
4. La barrera de seguridad real está en Supabase (Auth + RLS), no en la interfaz ni en el estado de Gradio.
5. ⚠️ **COMPLETAR:** conclusiones propias del equipo (qué aprendieron, qué harían distinto).

## 9. Evidencias verificables (todas dentro del repositorio)

* [`evidencias/resultados_colab_segundo_corte.md`](evidencias/resultados_colab_segundo_corte.md) — cifras del 2.º corte.
* [`evidencias/Guia_Segundo_Corte.pdf`](evidencias/Guia_Segundo_Corte.pdf) — guía del 2.º corte (sus tablas 7.2 y 7.4 se completan aquí).
* [`notebooks/`](notebooks/) — Clases 06–09 y consolidado, con sus salidas.
* [`supabase/setup.sql`](supabase/setup.sql) — esquema, RLS y función de búsqueda.
* [`app/tests/`](app/tests/) — pruebas automáticas.
* `evidencias/resultados_app.md` / `.json` — se generan con `app/verificar_entrega.py`.
* [`app/presentacion_proyecto.pdf`](app/presentacion_proyecto.pdf).

## 10. Responsables y aportes de cada integrante

| Integrante | Componentes en los que participó | Aportes | Puede justificar |
|---|---|---|---|
| Jilmar Said Veloza Páez | ⚠️ **COMPLETAR** | ⚠️ **COMPLETAR** | ⚠️ **COMPLETAR** |
| Andrés Felipe Galvis Téllez | ⚠️ **COMPLETAR** | ⚠️ **COMPLETAR** | ⚠️ **COMPLETAR** |

(La guía exige que cada integrante pueda justificar el componente en el que participó y su relación con el recorrido completo; no se asignaron aportes sin saber quién los hizo.)
