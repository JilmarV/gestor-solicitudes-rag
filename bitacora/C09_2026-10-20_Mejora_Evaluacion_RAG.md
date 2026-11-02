---
tipo: bitacora-clase
curso: Inteligencia Artificial Generativa y Sistemas Inteligentes
periodo: EAM-2026II
equipo: Equipo_XX
corte: 2
semana:
clase: 09
fecha: 2026-10-20
estado: en-progreso
tags:
  - ai
  - bitacora
  - rag
  - gestor-de-solicitudes
---
# Bitácora — Clase 09



## 1. Datos de la sesión

| Campo    | Registro                                                                                                                                                                                                   |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tema     | Mejora y evaluación del RAG: BM25, fusión RRF y reranking                                                                                                                                                  |
| Objetivo | Comparar tres formas de recuperar evidencia (A: semántica, B: híbrida BM25 + semántica + RRF, C: híbrida + reranking), medir su efecto con métricas de recuperación y decidir con evidencia cuál conservar |
| Proyecto | **Gestor de solicitudes**: clasifica peticiones y prepara respuestas según su tipo, prioridad y responsable; detecta información faltante y dirige cada caso al proceso adecuado                           |
| Inicio   | 7:00pm                                                                                                                                                                                                     |
| Cierre   | 9:00pm                                                                                                                                                                                                     |

## 2. Participación y responsabilidades

| Integrante    | Asistió | Rol de la clase                                  | Responsabilidad asumida                                                                                                                                                     | Aporte verificable                                                                         |
| ------------- | :-----: | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Jilmar Veloza |   Sí    | Responsable de anotación y métricas              | Preparación (puntos 1–3), definición de preguntas y evidencias esperadas antes de buscar (punto 4) y medición de recuperación en desarrollo (punto 6)                       | Notebook, puntos 4 y 6; tablas de métricas por caso y por opción. Commit: [CONFIRMAR hash] |
| Andrés Galvis |   Sí    | Responsable de análisis de rankings y respuestas | Construcción de BM25 y RRF (punto 5), lectura de rankings de la consulta (punto 8), generación con Groq y contraste con las fuentes (puntos 9–10), redacción de la bitácora | Notebook, puntos 5, 8, 9 y 10; ZIP `Clase_09_Evidencia_Evaluacion_RAG.zip`                 |

## 3. Reto aplicado al proyecto

### Funcionalidad trabajada

El equipo añadió dos etapas de recuperación al RAG del Gestor de solicitudes y las comparó contra la línea base semántica, manteniendo corpus, preguntas, prompt y generador (`openai/gpt-oss-20b`). El corpus didáctico (manuales de acceso y constancias) tiene 7 fragmentos ya persistidos en Supabase; BM25 se construyó en memoria sobre esos 7. Se recuperaron hasta M = 10 candidatos y se entregaron K = 3 pasajes por opción.

Además, las 12 preguntas del notebook se reformularon desde el punto de vista del gestor (a qué módulo dirigir una constancia, qué hacer si falta un documento, si un error 403 permite clasificar un caso como cuenta suspendida, qué datos pedir, qué no se puede afirmar). Eso está en `Clase_09_Gestor_Solicitudes_Mejora_Evaluacion_RAG.ipynb`; **esa versión aún no se ejecutó**, por lo que las cifras de esta bitácora corresponden a la ejecución de clase con las 4 preguntas de desarrollo originales.

### Criterios de aceptación

- [x] Corpus recuperado de Supabase con sesión válida (7 fragmentos, corpus `soporte_didactico-304429a408f1`).
- [x] Índice BM25 construido sobre todos los fragmentos (7).
- [x] A, B y C evaluadas en 4 casos de desarrollo sin fallos técnicos (`fallos_tecnicos = 0` en las tres).
- [x] Trazas de semántica, BM25, RRF y reranking revisadas para una consulta con dos condiciones.
- [x] Dos respuestas generadas (A y C) con JSON validado y citas existentes.
- [x] Evidencia descargada (JSON + CSV en ZIP).
- [ ] Decisión A/B/C escrita en `DECISION_DESARROLLO` antes de abrir la reserva (en la ejecución quedó "Pendiente").
- [ ] Reserva abierta una sola vez (`ABRIR_RESERVA` quedó en `False`).
- [ ] Revisión humana completada en `REVISION_MANUAL` (todos los campos en `None`).
- [ ] Notebook con las 12 preguntas del Gestor de solicitudes ejecutado de principio a fin.

### Archivos o componentes modificados

- `Clase_09_Demo_Colab_Mejora_Evaluacion_RAG.ipynb`: ejecutado en Colab con CPU; sin cambios al código de la clase.
- `Clase_09_Gestor_Solicitudes_Mejora_Evaluacion_RAG.ipynb`: versión del equipo con portada del proyecto, 12 casos anotados (6 desarrollo, 3 reserva, 3 comportamiento, con familia), consulta por defecto D2 y salidas limpiadas. No se tocaron BM25, RRF, reranker, K, M ni prompt.
- `Clase_09_Evidencia_Evaluacion_RAG.json` y `Clase_09_Metricas_RAG.csv` (dentro del ZIP): generados por el punto 11.

## 4. Decisiones técnicas

| Decisión | Razón | Alternativa descartada |
|---|---|---|
| Mantener M = 10, K = 3, constante RRF = 60 y parámetros BM25 (k1 = 1,5; b = 0,75; ε = 0,25) | La clase exige no ajustar parámetros después de mirar la reserva; son valores didácticos, no óptimos | Afinar K o la constante RRF mirando los resultados |
| Generar solo A y C (`MEJORA_A_GENERAR = C`) | Limita a dos llamadas a Groq y compara la línea base con la mejora más costosa | Generar A y B, o las tres opciones |
| No abrir la reserva todavía | Primero debe registrarse la decisión con desarrollo | Abrirla para "confirmar" antes de decidir |
| **Propuesta (por confirmar):** conservar A, la búsqueda semántica, como configuración | Con desarrollo las tres opciones empatan en calidad y C cuesta ≈ 3,3 veces más tiempo de recuperación (mediana 1611 ms frente a 484 ms) | Adoptar B o C sin mejora medida |



## 5. Problemas y soluciones

| Problema encontrado | Causa identificada | Solución aplicada | ¿Cómo se verificó? |
|---|---|---|---|
| Las tres opciones empatan y no se puede decir si BM25/RRF o el reranker aportan | Corpus de 7 fragmentos y K = 3: el fragmento relevante siempre entra (cobertura de candidatos = 1,0 con los 7 candidatos). Cada pregunta tiene un solo fragmento relevante, por lo que 0,333 es el **techo** de Precision@3, no un fallo | Se registra el empate como resultado. Se prepara el corpus real del Gestor y 12–20 casos para que las métricas discriminen | Tabla de cobertura: `cobertura_candidatos = cobertura_union = 1,0` y `candidatos = 7` en todos los casos |
| B incluyó en el puesto 3 un fragmento de error 403 que no responde la pregunta sobre la constancia, y desplazó el fragmento de seguimiento por código que A y C sí conservaron | **Hipótesis por verificar:** la tokenización de BM25 conserva palabras comunes («la», «y», «si») y esos fragmentos puntúan por ellas; el fragmento 403 quedó 2.º en el ranking léxico (puntaje 3,07) | Se documenta. No se cambia la tokenización después de ver el resultado | Contextos impresos en el punto 8 y tabla RRF (posición semántica 6, posición BM25 2). Falta probar con otra tokenización en una nueva ronda |
| El reranking multiplica el tiempo de recuperación sin mejorar las métricas | El cross-encoder procesa cada pareja pregunta–pasaje en CPU (7 parejas por consulta) | Se toma como costo en la decisión | `recuperacion_ms` por caso: C entre 1213 y 1941 ms; A entre 270 y 676 ms |
| Advertencias de librerías (HF sin token, `max_length` y `get_sentence_embedding_dimension` obsoletos) | Versiones fijadas del laboratorio | Sin acción: no afectan los resultados | La celda terminó y los cálculos se completaron |

## 6. Evidencias

| Tipo    | Descripción                                                                                              | Enlace o ruta                                                                             |
| ------- | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Commit  | Notebook de la clase 09 y notebook adaptado al Gestor de solicitudes                                     |                                                                                           |
| Captura | Tarjeta del proyecto seleccionado: Gestor de solicitudes                                                 | `evidencias/proyecto_gestor_solicitudes.png` (archivo original `1792537615813_image.png`) |
| Captura | Tablas de métricas de desarrollo por caso y por opción (punto 6)                                         |                                                                                           |
| Captura | Rankings semántico, BM25, RRF y reranker para la consulta de constancia con documento faltante (punto 8) |                                                                                           |
| Código  | Índice BM25 y fusión RRF                                                                                 | Notebook, puntos 5.1 y 5.2                                                                |
| Código  | Anotación de las 12 preguntas con su evidencia                                                           | `Clase_09_Gestor_Solicitudes_Mejora_Evaluacion_RAG.ipynb`, punto 4                        |
| Archivo | Métricas por caso y trazas completas, sin credenciales                                                   | `Clase_09_Evidencia_Evaluacion_RAG.zip` (JSON + CSV)                                      |

## 7. Uso de inteligencia artificial

> [!important] Registrar la IA no reemplaza la explicación técnica. El equipo debe verificar, adaptar y comprender cualquier resultado utilizado.

| Herramienta | Objetivo o pregunta | Qué se utilizó | Cómo se verificó | Qué se modificó |
|---|---|---|---|---|
| Claude (Anthropic) | Adaptar las preguntas del notebook al Gestor de solicitudes y redactar un borrador de esta bitácora con las salidas de la ejecución | 12 casos con evidencia esperada; texto de las secciones de esta nota | Las frases de evidencia se probaron con la función `evidencia()` contra los textos del corpus; las cifras se copiaron de las tablas de salida del notebook | [CONFIRMAR: ajustes del equipo al reparto de tareas, la decisión y las hipótesis] |
| Groq `openai/gpt-oss-20b` (dentro del notebook) | Generar la respuesta a la consulta de constancia con documento faltante (opciones A y C) | Dos respuestas JSON validadas con Pydantic | Se contrastó cada afirmación con el fragmento citado `[F1]`; ambas respuestas coinciden y no prometen emisión inmediata | Nada: la revisión manual formal sigue pendiente |

## 8. Defensa técnica y retroalimentación

| Campo                     | Registro |
| ------------------------- | -------- |
| Integrante que defendió   |          |
| Pregunta recibida         |          |
| Respuesta resumida        |          |
| Retroalimentación docente |          |
| Mejora acordada           |          |

## 9. Aprendizajes

- **Concepto comprendido:** RRF une rankings por posición (1/(60 + posición) por lista) sin sumar coseno con BM25; un reranker solo reordena los candidatos que recibe; y un empate se registra y se resuelve conservando la opción más sencilla. Con un solo fragmento relevante por pregunta, Precision@3 tiene un techo de 0,333.
- **Algo que aún genera duda:** si la tokenización de BM25 sin eliminar palabras comunes explica que B haya traído un fragmento irrelevante, y cómo cambiarían las métricas con el corpus real del Gestor (prioridades y responsables).
- **Qué haríamos diferente:** ampliar el corpus y llegar a 12–20 casos antes de comparar, registrar la decisión de desarrollo antes de abrir la reserva y completar la revisión humana el mismo día.

## 10. Revisión antes de entregar

- [x] Todos los integrantes registraron un aporte verificable.
- [x] Los enlaces y rutas de evidencia funcionan.
- [x] Los criterios de aceptación están actualizados.
- [x] El uso de IA fue declarado y verificado.
- [x] El equipo puede explicar las decisiones registradas.
