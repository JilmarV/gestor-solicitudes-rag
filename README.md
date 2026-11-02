# Gestor de solicitudes

Asistente académico para clasificar solicitudes, consultar el estado de una solicitud y responder preguntas sobre manuales institucionales con RAG (*Retrieval-Augmented Generation*). El proyecto usa Supabase para almacenar los fragmentos y sus embeddings, Groq para las respuestas estructuradas y un notebook de Google Colab como punto de entrada.

> **Alcance:** proyecto académico del segundo corte de EAM 2026-II. Todos los datos, códigos de solicitud y documentos son ficticios.

## Funcionalidades

- **Clasificación estructurada:** identifica el tipo de solicitud (`acceso`, `documento`, `pago`, `queja`, `consulta` u `otro`), prioridad, código `SOL-0000`, resumen y necesidad de revisión humana.
- **Reglas de negocio:** valida y corrige la salida del modelo. Por ejemplo, un pago que vence en menos de 48 horas pasa a prioridad alta y un caso sensible se deriva a revisión humana.
- **Consulta de estado:** `consultar_estado_solicitud` es una herramienta de solo lectura con lista blanca, argumentos validados y datos ficticios.
- **RAG con fuentes:** recupera fragmentos relevantes, responde usando únicamente el contexto entregado y muestra las fuentes `fuente / sección / chunk_id`.
- **Enrutamiento:** decide entre rechazo de seguridad, revisión humana, consulta de estado, solicitud de aclaración o RAG.
- **Evaluación reproducible:** compara búsqueda semántica, búsqueda híbrida BM25 + RRF y búsqueda híbrida con reranking.

## Arquitectura

```text
Entrada del usuario
        |
        v
Sanitización y detección de riesgo
        |
        v
Clasificación estructurada + reglas de negocio
        |
        +--> revisión humana
        +--> herramienta de estado SOL-0000
        +--> aclaración
        '--> RAG
                |
                v
        embedding -> Supabase (top-M)
                |
                +--> A: búsqueda semántica
                +--> B: BM25 + RRF
                '--> C: B + cross-encoder
                |
                v
        top-K = 3 -> respuesta JSON -> validación de citas
```

La ruta única de atención es `atender(texto)`. La precedencia es intencional: seguridad, revisión humana, herramienta, aclaración y finalmente RAG.

## Ejecución en Google Colab

### 1. Preparar Supabase

1. Crea un proyecto en [Supabase](https://supabase.com/).
2. Abre el **SQL Editor** y ejecuta [`supabase/setup.sql`](supabase/setup.sql).
3. En **Authentication > Users**, crea un usuario con correo y contraseña.
4. Conserva la URL y la clave publicable del proyecto.

El SQL crea la tabla `clase08_fragmentos`, habilita RLS por propietario y crea la función `clase08_buscar_fragmentos` para la búsqueda vectorial.

### 2. Configurar secretos en Colab

En **Colab > Secrets** crea estos secretos y activa **Acceso desde el notebook**:

| Secreto | Uso |
|---|---|
| `SUPABASE_URL` | URL del proyecto Supabase |
| `SUPABASE_PUBLISHABLE_KEY` | Clave publicable de Supabase |
| `SUPABASE_EMAIL` | Usuario de Supabase |
| `SUPABASE_PASSWORD` | Contraseña del usuario |
| `GROQ_API_KEY` | API key para el modelo de Groq |

No escribas estos valores en el notebook, en el repositorio ni en archivos de evidencia.

### 3. Ejecutar el notebook

Abre [`notebooks/Gestor_Solicitudes_Consolidado.ipynb`](notebooks/Gestor_Solicitudes_Consolidado.ipynb) en Colab y selecciona **Entorno de ejecución > Ejecutar todo**.

El notebook:

1. instala las dependencias;
2. genera o verifica los cinco documentos del corpus;
3. fragmenta el corpus y calcula embeddings de 384 dimensiones;
4. crea o reutiliza el índice en Supabase;
5. prueba clasificación, herramienta, seguridad y RAG;
6. compara las opciones de recuperación;
7. registra métricas, trazas y prompts;
8. exporta la evidencia sin credenciales.

El modo normal es `modo_llm="groq"` y `almacen="supabase"`. Para pruebas locales existe `modo_llm="mock"` y `almacen="local"`; este modo no sustituye la ejecución final con Supabase.

## Configuración principal

La configuración central está en `src/cells_a.py` y se incorpora al notebook mediante `src/build.py`.

| Parámetro | Valor |
|---|---|
| Modelo de generación | `openai/gpt-oss-20b` |
| Modelo de embeddings | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Dimensión del embedding | 384 |
| Corpus | `gestor-solicitudes-v1` |
| Candidatos `M` | 10 |
| Contexto final `K` | 3 |
| BM25 | `k1=1.5`, `b=0.75`, `epsilon=0.25` |
| RRF | `c=60` |
| Umbral de similitud | `0.30` |
| Reranker | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` |

Los valores de recuperación se mantienen constantes durante la comparación. La bitácora C09 documenta que no se deben ajustar después de observar la reserva.

## Corpus

El corpus es didáctico, ficticio y está en [`corpus/`](corpus):

| Archivo | Tema |
|---|---|
| `tipos_solicitud.md` | Tipos y criterios de clasificación |
| `prioridades.md` | Niveles y reglas de prioridad |
| `responsables.md` | Áreas responsables y escalamiento |
| `acceso.md` | Recuperación de acceso y error 403 |
| `constancias.md` | Solicitud, estado y correcciones de constancias |

El notebook también contiene el corpus para que la ejecución sea reproducible aunque los archivos no hayan sido creados previamente.

## Evaluación del RAG

Se comparan tres opciones con el mismo conjunto de casos:

| Opción | Descripción |
|---|---|
| `A_semantica` | Búsqueda por similitud coseno en Supabase |
| `B_hibrida_RRF` | Fusión del ranking semántico y BM25 mediante *Reciprocal Rank Fusion* |
| `C_hibrida_reranking` | Búsqueda híbrida seguida de reranking con un cross-encoder |

El notebook organiza la evaluación en 8 casos de desarrollo, 3 de reserva y 3 de comportamiento. Calcula `Precision@3`, `Recall@3`, `Hit@3`, `RR` y `MRR`, además de latencia, llamadas al modelo, tokens y revisión humana de las respuestas.

### Hallazgos registrados en la bitácora C09

- Con el corpus pequeño de la ejecución de clase, las opciones empataron en calidad: la cobertura de candidatos fue `1.0`.
- En ese escenario, `Precision@3 = 0.333` era el techo cuando había un único fragmento relevante por pregunta.
- El reranking aumentó el costo de recuperación en CPU sin mejorar las métricas observadas: mediana aproximada de `1611 ms` frente a `484 ms` para la línea base semántica.
- La propuesta documentada fue conservar **A, búsqueda semántica**, por ser la opción más sencilla y rápida mientras se amplía el corpus.
- La bitácora deja como pendientes ejecutar todos los casos reformulados del Gestor, registrar la decisión antes de abrir la reserva y completar la revisión humana formal.

## Seguridad y límites

- Las claves se leen desde Secrets o variables de entorno y nunca se imprimen.
- La entrada se normaliza, limita a 600 caracteres y se revisa contra patrones básicos de inyección y exfiltración.
- El texto del usuario se delimita como datos dentro del prompt.
- La herramienta disponible está en una lista blanca, usa Pydantic y solo acepta códigos con formato `SOL-0000`.
- El código de la solicitud debe aparecer literalmente en el mensaje antes de ejecutar la consulta de estado.
- El RAG se abstiene si la similitud máxima está por debajo del umbral y valida que las citas existan.
- Los errores se registran redactando posibles claves y tokens; no se cambia silenciosamente a otro modo.

Estas medidas son defensas de un prototipo académico, no un sistema listo para producción. La detección por patrones no garantiza detener todas las formas de inyección.

## Estructura del repositorio

```text
.
├── bitacora/
│   └── C09_2026-10-20_Mejora_Evaluacion_RAG.md
├── corpus/
│   ├── acceso.md
│   ├── constancias.md
│   ├── prioridades.md
│   ├── responsables.md
│   └── tipos_solicitud.md
├── docs/
│   └── Guia_Segundo_Corte.pdf
├── notebooks/
│   └── Gestor_Solicitudes_Consolidado.ipynb
├── src/
│   ├── build.py
│   ├── cells_a.py
│   ├── cells_b.py
│   ├── cells_c.py
│   └── make_pdf.py
├── supabase/
│   └── setup.sql
├── requirements.txt
└── README.md
```

`cells_a.py`, `cells_b.py` y `cells_c.py` son la fuente modular del notebook; `build.py` reconstruye el notebook consolidado.

## Dependencias

Las versiones y paquetes principales están en [`requirements.txt`](requirements.txt):

```text
supabase
sentence-transformers
rank-bm25
groq
pydantic
tiktoken
pandas
```

Para reconstruir el notebook fuera de Colab:

```bash
pip install -r requirements.txt
cd src
python build.py
```

La ejecución completa requiere además acceso a los secretos y a un proyecto Supabase configurado.

## Evidencia y bitácora

La bitácora de la clase 09 explica las decisiones de BM25, RRF y reranking, los problemas observados, las métricas y los pendientes de revisión:

- [`bitacora/C09_2026-10-20_Mejora_Evaluacion_RAG.md`](bitacora/C09_2026-10-20_Mejora_Evaluacion_RAG.md)
- [`docs/Guia_Segundo_Corte.pdf`](docs/Guia_Segundo_Corte.pdf)

Al finalizar el notebook se genera un ZIP de evidencia con configuración, corpus, fragmentos, métricas, trazas y prompts sin credenciales. Antes de entregar, verifica que la decisión de desarrollo, la reserva y la revisión humana estén diligenciadas.

## Equipo

**Jilmar Veloza · Andrés Galvis**  
EAM 2026-II · Docente: Robert García Rey
