# Resultados observados en Colab — notebook consolidado (segundo corte)

Fuente: salidas guardadas en `notebooks/Gestor_Solicitudes_Consolidado.ipynb` (ejecución real en Google Colab, CPU,
modelo `openai/gpt-oss-20b` en Groq, índice en Supabase). Los números de abajo se copiaron de esas salidas; no se
recalcularon ni se redondearon de nuevo. La fecha exacta de la ejecución no quedó guardada en las salidas del notebook.

## 1. Corpus, fragmentación e índice
| Dato | Valor observado |
|---|---|
| Documentos | 5 (`tipos_solicitud`, `prioridades`, `responsables`, `acceso`, `constancias`), versión `1.0-didactica` |
| Huellas SHA-256 (12 primeros caracteres) | 88be7f076029 · 541930d3816d · d5c052e51fd5 · 029a5053bb4a · f74d4b8341a3 |
| Fragmentos | 12 (estrategias «ventanas» y «párrafos» producen los mismos 12) |
| Tokens por fragmento | máximo 76, promedio 52,2 (límite del modelo de embeddings: 128) |
| Construcción del índice en Supabase | 12 fragmentos en 2,1 s; segunda ejecución: `indice_vigente() = True` (se reutiliza, sin re-embeber) |
| Contexto mínimo (aprox. `o200k_base`) | corpus completo ≈ 610 tokens · contexto de K=3 ≈ 136 tokens |

## 2. Comparación de recuperadores (K=3, M=10) — grupo de desarrollo (8 preguntas)
| Opción | MRR | Precision@3 | Recall@3 | Hit@3 | Latencia media (ms) |
|---|---|---|---|---|---|
| A · semántica (baseline) | 1,000 | 0,333 | 1,000 | 1,000 | 202,1 |
| B · BM25 + RRF | 1,000 | 0,333 | 1,000 | 1,000 | 160,8 |
| C · B + reranking | 1,000 | 0,333 | 1,000 | 1,000 | 3098,2 |

Lectura: empate total en calidad. Con evidencia de un solo fragmento el máximo posible de Precision@3 es 0,333.
Criterio fijado antes de abrir la reserva: MRR > Recall@3 > simplicidad → **se eligió A_semantica**. C solo añade latencia.

## 3. Grupo de reserva (3 preguntas, abierto una sola vez, A frente a la elegida = A)
| Opción | MRR | Precision@3 | Recall@3 | Hit@3 | Latencia media (ms) |
|---|---|---|---|---|---|
| A · semántica | 1,000 | 0,333 | 1,000 | 1,000 | 173,7 |

La pregunta R3 («Se me olvidó la contraseña…»), que con BM25 solo no recuperaba `acceso-01`, **sí lo recuperó en primer lugar
con embeddings** (`[acceso-01, acceso-02, constancias-01]`). La tabla de «fallos reales» automática salió vacía (`ninguno`).

## 4. Comportamiento (3 casos)
| ID | Caso | Ruta | Estado | Sin fuentes inventadas | OK |
|---|---|---|---|---|---|
| C1 | fuera de alcance | rag | evidencia_insuficiente | sí | sí |
| C2 | ambigua | aclaracion | aclaracion | sí | sí |
| C3 | estado sin código | aclaracion | aclaracion | sí | sí |

## 5. Pruebas integradas (8 casos por `atender`) — latencia y tokens por interacción
| Tipo | Ruta esperada → obtenida | Estado | Latencia (ms) | Llamadas LLM | Tokens in / out |
|---|---|---|---|---|---|
| normal | rag → rag | respondida | 7110,9 | 2 | 968 / 236 |
| ambiguo | aclaracion → aclaracion | aclaracion | 3370,2 | 1 | 374 / 108 |
| incompleto | aclaracion → aclaracion | aclaracion | 4495,8 | 1 | 378 / 92 |
| malicioso | rechazo → rechazo | rechazada | 0,0 | 0 | 0 / 0 |
| fuera de alcance | rag → rag | evidencia_insuficiente | 8096,4 | 2 | 973 / 149 |
| herramienta | herramienta → herramienta | respondida | 4159,1 | 2 | 576 / 148 |
| herramienta (código inexistente) | herramienta → herramienta | no_encontrada | 4734,1 | 2 | 576 / 148 |
| revisión humana | humano → humano | derivada | 3524,0 | 1 | 383 / 144 |

8/8 rutas correctas. Falla simulada del modelo: respuesta segura («derivó a revisión humana») sin filtrar claves.

Resumen de llamadas al modelo (log de la sesión): `clasificar` 24 llamadas, 1797,3 ms de media, 9157 tokens de entrada / 2693 de salida ·
`proponer_herramienta` 4 llamadas, 1431,0 ms, 780 / 180 · `rag` 15 llamadas, 2854,4 ms, 9178 / 1330.

## 6. Generación sobre las 11 preguntas anotadas (dev + reserva)
Las 11 pasaron por la ruta `rag` con estado `respondida`; latencia de 838,6 a 9365,6 ms; 951–1028 tokens de entrada y 164–239 de salida.
Solo se guardaron en las salidas el texto de **D1, D2 y D3**. La **revisión humana de las 11 respuestas quedó pendiente**
(`REVISION_HUMANA` sin rellenar: «Revisión humana pendiente»).

### Lectura preliminar de las 3 respuestas visibles (hecha al preparar la entrega; no sustituye la revisión del equipo)
| ID | ¿Fiel al fragmento citado? | Observación |
|---|---|---|
| D1 | **No del todo** | Añade «el sistema no lo enviará de inmediato si ya se ha enviado recientemente», que no está en `acceso-01`. Además la fuente dice «no basta con repetir el envío»; la respuesta dice «no es necesario repetir», que cambia el sentido de la negación. La misma deformación apareció en la demostración de la sección 10 del notebook. |
| D2 | Sí | Reproduce la definición del 403 y conserva «no demuestra por sí solo que la cuenta esté bloqueada». |
| D3 | Sí | Captura con el mensaje visible, fecha y recurso, tal como indica `acceso-02`. |

## 7. Observación sobre el umbral de abstención
Para «¿Cuál es el horario de la cafetería?» hubo 2 llamadas al modelo y 149 tokens de salida: la similitud máxima superó 0,30, por lo que
**la abstención la decidió el modelo, no el umbral**. El umbral (0,30, heurístico) no filtró ese caso.
