# Taller de Navidad · Lakebase para aplicaciones agénticas

Construye desde cero, **solo con un workspace**, el «Taller de Navidad»: Papá Noel y los Reyes Magos como una flota de reparto en 21 ciudades españolas. Incluye:

- datos en **Unity Catalog**;
- una base operacional en **Lakebase** (Postgres serverless) con *synced tables*;
- un **Databricks App**;
- una pista de **incidencias** (borrasca tipo Filomena en Madrid, DANA en Valencia, cortes de calle en Barcelona). Las incidencias se simulan en **ramas de Lakebase** con **PostGIS + pgRouting**.

## Requisitos

- Workspace de Databricks (AWS o Azure) con **Lakebase** y **Databricks Apps** habilitados y **cómputo serverless**.
- Permiso para crear un esquema en un catálogo existente (`USE CATALOG` + `CREATE SCHEMA`).
- Nada más: ni CLI ni instalación local.

## Presentación

`workshop/deck/lakebase-agentes-es.html`: ábrela en el navegador (funciona sin conexión).
- **Teclas:** ← → pasos · 1–5 pestañas · N notas · T fondo blanco/oscuro · G Grinch · F pantalla completa.
- **Botones:** «❄ Efectos» (nieve, Papá Noel y renos; apagado por defecto) y «Arquitectura» (paso a paso por iteraciones).

## Camino A · notebooks (recomendado)

1. Trae el contenido al workspace, de una de estas dos formas:
   - **Git folder:** *Workspace → Create → Git folder* con la URL del repo.
   - **Zip:** *Workspace → (tu carpeta) → Import → File*. Sube `navidad-workshop.zip`, que se reparte en la sesión, y mantén su estructura de carpetas.
2. Abre `workshop/notebooks/00_workbench`, escribe tu catálogo en el widget `catalog` y pulsa **Run all**. Unos **5 minutos** a escala 0,1 (medido: datos 77 s, Lakebase 31 s, app 143 s, incidencias 9 s).
3. Al terminar, la última celda muestra el enlace al app y a `/planner`.

| Notebook | Qué hace |
|---|---|
| `00_workbench` | Datos → Lakebase (synced tables) → app (con Incidencias) → red de carreteras y escenarios |
| `01_rama_whatif` | Branching paso a paso sin app: crea una rama, simula, compara con producción y la borra |
| `02_instalar_skills` | Copia las skills a Genie Code (`.assistant/skills`) para el desarrollo agéntico |
| `03_grinch` | **Opcional.** El Grinch borra el 80 % de las cartas a los Reyes: snapshot, rama desde el momento seguro (PITR) y recuperación sin parar el app; restauración completa opcional (~1 min) |
| `04_tiempo_real_stream` | **Centro de control (facilitador).** Prepara `navidad_live` (Lakebase), la tabla bronze y la identidad de Zerobus, y corre Spark Structured Streaming en **serverless** (`AvailableNow` en bucle) → **Lakebase sink** (`format("postgresql")` + `upsertkey`). Arráncalo primero |
| `05_tiempo_real_productor` | **Centro de control (facilitador).** Reproduce la noche de toda España a cámara rápida (duendes / pajes, ~1,5 % excepciones) y la envía por **Zerobus**; `destino = lakebase_directo` escribe directo en Lakebase (ensayo). Abre el app en `/control` |
| `06_tiempo_real_sin_broker` | **Comparativa (facilitador).** Spark serverless sin Zerobus ni Delta: fuente `rate` (~350 eventos/s) → join con el plan → Lakebase sink en bucle `AvailableNow`; mide la latencia (≈ 5,7 s p50) |
| `07_replica_lectura` | **Bonus · Réplica de lectura.** Crea un endpoint `READ_ONLY` (`replica`) en la rama `production` (~2 s, mismo almacenamiento, sin copiar datos), comprueba que rechaza escrituras y mide el retraso (p50 ≈ 3 ms en el workspace de referencia). `/control` lo detecta solo y lee de él («Lecturas: réplica»); ingesta, agente y ▶/■ siguen escribiendo en la primaria. `accion = borrar` lo elimina |
| `08_busqueda` | **Bonus · Búsqueda.** Requiere **Lakebase Search** activado en el proyecto (Settings → Lakebase Search; irreversible, reinicia los cómputos). Indexa 500.000 familias y 364 equipos de duendes/pajes en `navidad_search.doc` (BM25 + GIN para prefijos, ~1 min) y prueba consultas (BM25 ≈ 3 ms). En el app: barra de búsqueda arriba («/»), resultados en «Mapa de rutas» |
| `99_limpieza` | Borra el app, el proyecto Lakebase (**purgado**, sin papelera de 7 días, para poder recrearlo con el mismo nombre) y el esquema. Escribe `BORRAR` para confirmar |

## Centro de control en tiempo real (bloque 3)

Los asistentes **revisan la arquitectura y cómo se escribe en Lakebase** (pestaña «Detalle técnico» del bloque 3); el facilitador lanza la noche con **▶ Iniciar noche / ■ Parar** en `/control` (job `navidad-live-<slug>` = `04` + `05` en paralelo, creado al ejecutar `04` una vez) o ejecuta `04` y `05` a mano.

```
05 productor ──Zerobus──► Delta bronze ──04 Spark (serverless)──► Lakebase navidad_live ──► app /control ──► agente (confirmar)
```

Tres formas de escribir en Lakebase, una tabla por escritor: **synced tables** (`*_sync`), **Lakebase sink** (estado en directo: `delivery_status`, `helper_position`, `exception_event`) y **escritura directa** del app y el agente (`exception_state`, `agent_review`, `agent_action`).

Medido en el workspace de referencia (Nochebuena completa, 318.170 paradas, 21 ciudades, 112 duendes): Zerobus confirma en ~0,2 s y escribe en Delta cada 5 s; el sink escribe cada lote en 0,1–0,2 s; **evento → Lakebase p50 ≈ 14 s, p95 ≈ 23 s**, todo en serverless (el coste fijo de cada ejecución `AvailableNow` es ~3–8 s; en cómputo clásico con `processingTime` sería menor). El agente (Haiku) revisa una incidencia en ~7–10 s.

Comparativa (workspace de referencia, serverless, 350 eventos/s): **escritura directa** en Lakebase p50 0,02 s · **Spark sin broker ni Delta** (`06_tiempo_real_sin_broker`, fuente `rate` → sink) p50 5,7 s / p95 8,0 s · **Zerobus → Delta → Spark** p50 ≈ 14 s / p95 ≈ 23 s. Pendiente (futuro): cómputo clásico con `processingTime` o Real-Time Mode (el workspace de referencia es solo serverless). Requisitos: Zerobus en la región del workspace y permiso para crear un service principal (lo hace `04`).

## Databricks Free Edition

Probado el 13-nov-2026 en un workspace Free Edition, desde cero y con limpieza intermedia: `00`, `01`, `03` y `99` funcionan; `00` tarda unos 4 min a escala 0,1.

- **Widget `edicion` = Free Edition:** aplica todo lo de abajo automáticamente (modelo, límites del proyecto Lakebase).
- **Catálogo:** `workspace`.
- **Escala:** `scale` = **0.1**. La cuota diaria de cómputo de Free Edition hace arriesgado 0,75.
- **Modelo:** `model` = **`databricks-gpt-oss-120b`** (o `databricks-meta-llama-3-3-70b-instruct`). En Free Edition no hay modelos `system.ai.*` en el AI Gateway; el app llama directamente al serving endpoint.
- **Lakebase:**
  - 1 proyecto por cuenta, así que no hay segundo workbench con sufijo;
  - el cómputo queda limitado a 1 CU;
  - scale-to-zero mínimo de 300 s (el notebook lo ajusta solo).
- **Ramas, snapshots y PITR:** funcionan igual (rama ~3 s, snapshot < 1 s, restauración ~3 s).
- **Apps:**
  - hasta 3 por cuenta;
  - se paran solas a las 24 h (reiniciar desde *Compute → Apps*);
  - el ping al modelo usa el endpoint indicado.
- **Internet saliente restringido:** la red de carreteras de Madrid, Valencia y Barcelona va precargada (no hace falta Overpass).

## Camino B · SQL

Editor SQL de Lakebase (proyecto `navidad-<tu_slug>`). Sustituye `navidad_<tu_slug>` por tu esquema.

- `sql/01_explorar.sql`: las dos noches, ciudades, los Reyes como flota.
- `sql/02_postgis_pgrouting.sql`: KNN, tiempo por carretera con `pgr_dijkstraCost`, escenarios.
- `sql/03_rama_whatif.sql`: **solo en una rama**. Activa la DANA, simula y sugiere. Luego compara con `production`.

## Camino C · DAB o Genie Code

- **DAB:** `databricks bundle deploy/run` con `workshop/databricks.yml`. Es el mismo notebook, como job serverless.
- **Genie Code:** ejecuta `02_instalar_skills` y pide en Genie Code: *«Ayúdame a construir sobre el Taller de Navidad»*. La skill `navidad-hack-build-assistant` propone pistas (rutas, segmentación, incidencias) y construye sobre Lakebase.

## Coste y limpieza

- Por defecto, las synced tables van en **SNAPSHOT**: una copia, sin pipeline continuo. Es la opción barata.
- El cómputo de Lakebase escala a cero tras 60 s sin uso.
- Las ramas de simulación caducan en 24 h, y el app conserva como mucho 3 a la vez.
- Al terminar, ejecuta `99_limpieza`.
- Precios: [página pública de Lakebase](https://www.databricks.com/product/pricing/lakebase).

## Avisos

- Datos **sintéticos**: nombres aleatorios, coordenadas difuminadas por ciudad.
- Escenarios **inspirados en** hechos reales (DANA 2024, cortes de calle). La geometría es ilustrativa.
- Red de carreteras © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), licencia ODbL (ficheros `navidad-hack-infra/data/*_osm.csv.gz`).
- Costas y tierra: Natural Earth (dominio público).
