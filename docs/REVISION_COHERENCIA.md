# Revisión de coherencia entre los documentos recibidos

Se compararon: Guía de la entrega final (Clase 12), plantilla del README, Guía del segundo corte (PDF), notebooks de las Clases 06, 07, 08, 09 y el notebook consolidado (código **y** salidas guardadas).

## Lo que concuerda
* El proyecto es el mismo en todos los documentos: *Gestor de solicitudes* (clasificar, responder con fuentes, consultar estado). Mismo equipo, curso y docente.
* Modelo de embeddings, dimensión (384), normalización y coseno: iguales en Clases 06–09 y consolidado.
* LLM `openai/gpt-oss-20b`, tabla `clase08_fragmentos` y función `clase08_buscar_fragmentos`: coherentes entre Clase 08, 09 y consolidado y con lo que pide la guía final.
* Los hashes del corpus que imprimió Colab coinciden con los del corpus entregado en `app/corpus/` (88be7f076029, 541930d3816d, d5c052e51fd5, 029a5053bb4a, f74d4b8341a3) y los 12 `chunk_id` coinciden con los de Colab.
* Los 8 casos integrados del consolidado (8/8) y los 3 de comportamiento (3/3) son consistentes con las rutas que describe la guía del 2.º corte.

## Inconsistencias o vacíos encontrados y cómo se resolvieron
| # | Dónde | Qué pasa | Resolución |
|---|---|---|---|
| 1 | Guía 2.º corte §7.1 y §8 vs. salidas de Colab | La guía presenta como «fallo real» que R3 («contraseña») no recupera `acceso-01` (medido con BM25 solo). En Colab con embeddings R3 **sí** lo recupera (A, B y C con Recall@3 = 1,0) y la tabla de fallos salió vacía | Se documenta en la bitácora (E1). No se inventó un fallo de recuperación; el fallo real observado es de **fidelidad** del modelo (D1) |
| 2 | Guía 2.º corte §7.2 y §7.4 | Tablas A/B/C y «____/11» en blanco | Tabla 7.2 completada con las salidas reales (`evidencias/resultados_colab_segundo_corte.md`). **La revisión humana 11/11 sigue sin hacerse** (el notebook dice «pendiente») |
| 3 | Guía 2.º corte §3 | «El mayor fragmento ≈ 63 tokens» | Tokenizador real: máximo 76 |
| 4 | SQL Clase 08/consolidado vs. Guía final | RLS `owner_id = auth.uid()` también para **leer**: un usuario nuevo no ve el corpus, pero la guía pide una app multiusuario | `setup.sql` abre solo la lectura del corpus a usuarios autenticados y mantiene privado el historial |
| 5 | Clases 07–09 vs. consolidado | Dos corpus distintos en la misma tabla (`soporte_didactico-<huella>`, 7 fragmentos; y `gestor-solicitudes-v1`, 12) | La app usa solo `gestor-solicitudes-v1`; documentado |
| 6 | Clase 08 vs. consolidado | Dos prompts diferentes con la misma etiqueta `rag_v2` | La app usa el del consolidado; se recomienda renombrar si se edita |
| 7 | Guía final §5 | Parte de «el notebook integrado de la Clase 11» (clientes MCP, `MEMORIA`): **no estaba entre los archivos recibidos**; el consolidado solo llega hasta la Clase 09 y no tiene MCP ni historial | Se construyó un MCP propio y el historial en Supabase. Confirma si tu Clase 11 tiene otro MCP |
| 8 | Plantilla README | Pide `MCP_URL`; un MCP propio por stdio no usa URL | Se sustituyó por `MCP_MODO` y se retiró `MCP_URL` |
| 9 | Guía final (sección 9) vs. instalación real | `gradio 5.50.0` no es instalable junto a `pydantic 2.13.5` (versión de las Clases 08–09) | Se fijó `gradio 6.32.0` y se probó |
| 10 | Consolidado, celda 36 y revisión | Las 11 respuestas salieron `respondida`; ninguna `parcial` ni abstención. D1 distorsiona la fuente («no basta con repetir» → «no es necesario repetir») | Registrado como error observado (E3); mitigación propuesta y **no** aplicada por no estar evaluada |
| 11 | Consolidado §9 | El caso «cafetería» no fue frenado por el umbral 0,30 (hubo llamadas al modelo): abstuvo el modelo | Registrado como limitación (E7) |
| 12 | Guía final §8 y plantilla | Piden «aprobación humana para acciones sensibles» | La herramienta es de solo lectura; se documenta que no aplica y qué haría falta si hubiera escritura |
| 13 | Guía 2.º corte §11 | Ítems 6, 9, 11 y 12 «Ejecutar en Colab / Completar» | Ejecutados (resultados en la evidencia). El 12 queda parcial por la revisión humana |
| 14 | Guía final §14 | Exige probar dos usuarios, RLS y recuperación tras reiniciar | Hay pruebas offline (64) y un script contra servicios reales (`verificar_entrega.py`), **pendiente de ejecutar** |

## Lo que no se pudo verificar desde aquí (honestidad)
* Conexión real a Supabase (Auth, RLS de Postgres, pgvector) y a Groq: no hay acceso desde el entorno de preparación. Se usó un Supabase simulado; el SQL se validó solo sintácticamente.
* Carga del modelo de embeddings de Hugging Face (descarga bloqueada): la fragmentación se verificó con un tokenizador de prueba (mismos 12 ids y secciones que Colab).
* Despliegue en Render y su consumo de memoria.
