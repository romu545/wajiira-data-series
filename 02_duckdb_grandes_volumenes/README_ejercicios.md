# Parte 2 (avanzado): ejercicios con DuckDB

Ejercicios de nivel intermedio-avanzado sobre **datos ficticios** de ventas. Cada ejercicio existe en Python y en R con el mismo SQL, para que puedas comparar.

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `generar_datos.py` / `generar_datos.R` | Crea los datos ficticios en `../data/` |
| `ejercicios_avanzados.py` / `ejercicios_avanzados.R` | Corre los 12 ejercicios |

## Cómo ejecutarlo

Desde esta carpeta (`02_duckdb_grandes_volumenes`):

```bash
# Python (requiere: pip install duckdb pandas)
python generar_datos.py                 # 250.000 filas/mes (~3 millones, ~200 MB)
python ejercicios_avanzados.py

# R (requiere R >= 4.0 e install.packages(c("DBI", "duckdb")))
Rscript generar_datos.R
Rscript ejercicios_avanzados.R
```

Para probar con otro volumen: `python generar_datos.py --filas 50000` (rápido) o `--filas 2000000` (~24 millones de filas; revisa tu espacio en disco). En R: `Rscript generar_datos.R 50000`.

## Datos que se generan

| Carpeta | Contenido | Se usa en |
|---|---|---|
| `data/raw/` | 12 CSV de 2025, con duplicados (~0,05 %), ciudades nulas (~1 %) y devoluciones (montos negativos) | 1 a 9, 12 |
| `data/incoming/nuevo_mes.csv` | Enero 2026, con filas de diciembre reenviadas | 10 |
| `data/raw_drift/` | 2 CSV con columnas en otro orden, extra o faltantes | 11 |
| `data/dim/clientes.parquet` | Segmento y fecha de registro de cada cliente | 8 |
| `data/ref/tasas_cambio.csv` | TRM diaria solo de días hábiles | 5 |

## Ejercicios

| # | Tema | Qué se practica |
|---|---|---|
| 1 | Ingesta | `read_csv_auto` con comodín y `filename = true` |
| 2 | Calidad de datos | Diagnóstico con `FILTER` y deduplicación con `QUALIFY` |
| 3 | Funciones ventana | `LAG`, media móvil, ventana con nombre (`WINDOW w AS`) |
| 4 | Top-N por grupo | `rank()` + `QUALIFY` |
| 5 | `ASOF JOIN` | Convertir a USD con la TRM vigente; fines de semana usan el último día hábil |
| 6 | `PIVOT` | Categorías como columnas |
| 7 | Cohortes | Retención de clientes según su primer mes de compra |
| 8 | Join con Parquet | Cruzar la base `.duckdb` con una dimensión externa |
| 9 | Parquet particionado | `PARTITION_BY`, lectura de una sola partición, comparación de peso |
| 10 | Carga incremental | `INSERT ... BY NAME` omitiendo lo que ya existe |
| 11 | Deriva de esquema | `union_by_name = true` |
| 12 | Límite de memoria | `memory_limit` + `temp_directory`: consulta pesada con 1 GB de RAM |

## Referencia de tiempos

Medidos con el volumen por defecto (3 millones de filas) en un entorno de pruebas: generar los datos tarda unos 5 s y correr los 12 ejercicios unos 20 s. Tus tiempos dependerán de tu equipo.

## Recomendaciones para el repositorio

Agrega al `.gitignore` los datos generados, porque pesan cientos de MB y se pueden recrear:

```
data/raw/
data/raw_drift/
data/incoming/
data/parquet/
data/database/
data/tmp/
```

Los datos son completamente ficticios y no contienen información real. Los valores de texto no llevan tildes a propósito, para evitar problemas de codificación en Windows.
