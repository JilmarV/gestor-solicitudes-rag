# Gestor de solicitudes

Asistente que clasifica solicitudes institucionales, responde con fuentes verificables (RAG sobre 5 manuales ficticios) y consulta el estado de una solicitud mediante un servidor MCP propio. Interfaz Gradio, usuarios e historial en Supabase (con RLS), modelo en Groq.

Proyecto final de *Inteligencia Artificial Generativa y Sistemas Inteligentes* (EAM 2026-II). Equipo: Jilmar Said Veloza Páez y Andrés Felipe Galvis Téllez.

## Qué hay en este repositorio

| Ruta | Contenido |   p
|---|---|
| `app/` | Aplicación (código, corpus, pruebas) y su **README** con la plantilla de la Clase 12 completa |
| `app/presentacion_proyecto.pdf` | Presentación de 16 diapositivas |
| `supabase/setup.sql` | Script SQL de tablas, RLS y función de búsqueda |
| `BITACORA_PROYECTO.md` | Bitácora unificada de los tres cortes |
| `docs/GUIA_PASO_A_PASO.md` | **Empieza aquí**: qué hacer, en orden, para que funcione |
| `docs/GUIA_QUE_SE_HIZO.md` | Cómo funciona y qué se hizo respecto a los notebooks |
| `docs/REVISION_COHERENCIA.md` | Revisión de coherencia entre guías y notebooks |
| `evidencias/` | Resultados de Colab y de la aplicación |
| `notebooks/` | Notebooks de las clases 06–09 y el consolidado |

## Inicio rápido

```bash
cd app
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.ejemplo .env                                   # completa tus claves (nunca se suben a Git)
python -m pytest tests                                 # 64 pruebas sin red
python app.py                                          # http://127.0.0.1:7860
```

Antes de la primera ejecución real hay que ejecutar `supabase/setup.sql`, crear usuarios en Supabase Auth y cargar el corpus con `python preparar_corpus.py`. El detalle está en `docs/GUIA_PASO_A_PASO.md`.

## Seguridad

- `.env` está en `.gitignore`; solo se sube `app/.env.ejemplo`.
- Solo se usa la clave *publishable* de Supabase; jamás `secret` ni `service_role`.
- Si una clave se expone, se rota de inmediato.

## Pendientes que solo el equipo puede completar

Buscar `COMPLETAR` en `app/README.md` y `BITACORA_PROYECTO.md` (URL del repositorio y de Render, fechas, aportes individuales, conclusiones, revisión humana). Los datos del proyecto son ficticios.
