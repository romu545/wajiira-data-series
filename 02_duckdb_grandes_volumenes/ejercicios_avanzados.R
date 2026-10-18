# Parte 2 (avanzado): ejercicios con DuckDB en R sobre datos ficticios.
# Wajiira Analytics
#
# Antes: Rscript generar_datos.R   (requiere R >= 4.0)
# Ejecutar desde la carpeta 02_duckdb_grandes_volumenes.

library(DBI)
library(duckdb)

# dbExecute() imprime '[1] 0' en cada paso; esta version lo silencia
ejecutar <- function(con, sql) invisible(dbExecute(con, sql))

options(scipen = 999, width = 140)          # evita notacion cientifica en los totales
DATA <- normalizePath("../data", winslash = "/", mustWork = FALSE)
d <- function(ruta) file.path(DATA, ruta)    # ruta con '/' (DuckDB la prefiere en Windows)

# Reemplaza {nombre} por su valor dentro de un texto SQL (para insertar rutas)
plantilla <- function(txt, ...) {
  v <- list(...)
  for (k in names(v)) txt <- gsub(paste0("{", k, "}"), v[[k]], txt, fixed = TRUE)
  txt
}

# --- Conexion persistente con limites de recursos ---------------------------------
con <- dbConnect(duckdb::duckdb(), dbdir = d("database/ventas_avanzado.duckdb"))
ejecutar(con, "SET memory_limit = '1GB'")                       # tope de RAM
ejecutar(con, paste0("SET temp_directory = '", d("tmp"), "'"))  # lo que no quepa va a disco

# Ejecuta una consulta, imprime las primeras filas y el tiempo
correr <- function(titulo, sql, filas = 12) {
  cat("\n===", titulo, "===\n")
  t <- system.time(df <- dbGetQuery(con, sql))[["elapsed"]]
  print(head(df, filas))
  cat("->", nrow(df), "filas en", round(t, 2), "s\n")
}

# 1. INGESTA: todos los CSV a una tabla, guardando de que archivo vino cada fila ----
ejecutar(con, plantilla(r"--(
CREATE OR REPLACE TABLE ventas_raw AS
SELECT * FROM read_csv_auto('{ruta}', filename = true)
)--", ruta = d("raw/*.csv")))

# 2. CALIDAD DE DATOS: diagnostico antes de limpiar ---------------------------------
correr("2. Diagnostico de calidad", r"--(
SELECT count(*)                                            AS filas,
       count(DISTINCT "ID Transaccion")                    AS ids_unicos,
       count(*) - count(DISTINCT "ID Transaccion")         AS duplicados,
       count(*) FILTER (WHERE Ciudad IS NULL)              AS ciudad_nula,
       count(*) FILTER (WHERE "Monto Total" < 0)           AS devoluciones
FROM ventas_raw
)--")

# Tabla limpia: QUALIFY elimina duplicados sin subconsultas anidadas
ejecutar(con, r"--(
CREATE OR REPLACE TABLE ventas AS
SELECT "ID Transaccion"            AS id_transaccion,
       "Fecha Venta"               AS fecha,
       "Monto Total"               AS monto,
       "ID Cliente"                AS id_cliente,
       Categoria                   AS categoria,
       coalesce(Ciudad, 'Sin dato') AS ciudad,
       Canal                       AS canal,
       parse_filename(filename)    AS archivo
FROM ventas_raw
QUALIFY row_number() OVER (PARTITION BY "ID Transaccion" ORDER BY filename) = 1
)--")

# 3. FUNCIONES VENTANA: crecimiento mensual y media movil por categoria -------------
correr("3. Crecimiento mensual y media movil (3 meses)", r"--(
WITH mensual AS (
    SELECT date_trunc('month', fecha) AS mes, categoria, sum(monto) AS total
    FROM ventas WHERE monto > 0
    GROUP BY ALL
)
SELECT mes, categoria, total,
       round(100.0 * (total / lag(total) OVER w - 1), 1)              AS crecimiento_pct,
       round(avg(total) OVER (w ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)) AS media_movil_3m
FROM mensual
WINDOW w AS (PARTITION BY categoria ORDER BY mes)
ORDER BY categoria, mes
)--", filas = 14)

# 4. TOP-N POR GRUPO: las 3 mejores ciudades de cada categoria ----------------------
correr("4. Top 3 ciudades por categoria", r"--(
SELECT categoria, ciudad, sum(monto) AS total,
       rank() OVER (PARTITION BY categoria ORDER BY sum(monto) DESC) AS posicion
FROM ventas WHERE monto > 0
GROUP BY categoria, ciudad
QUALIFY posicion <= 3
ORDER BY categoria, posicion
)--", filas = 18)

# 5. ASOF JOIN: convertir a USD con la TRM vigente (fines de semana usan el ultimo dia habil)
ejecutar(con, plantilla("CREATE OR REPLACE TABLE tasas AS SELECT * FROM read_csv_auto('{ruta}')",
                         ruta = d("ref/tasas_cambio.csv")))
correr("5. Ventas mensuales en USD (ASOF JOIN con la TRM)", r"--(
SELECT date_trunc('month', v.fecha) AS mes,
       round(sum(v.monto))          AS total_cop,
       round(sum(v.monto / t.trm_cop_usd)) AS total_usd
FROM ventas v
ASOF JOIN tasas t ON v.fecha >= t.fecha
WHERE v.monto > 0
GROUP BY 1 ORDER BY 1
)--")

# 6. PIVOT: categorias como columnas -------------------------------------------------
correr("6. PIVOT: ventas por mes y categoria", r"--(
PIVOT (SELECT strftime(fecha, '%Y-%m') AS mes, categoria, monto FROM ventas WHERE monto > 0)
ON categoria USING sum(monto)
GROUP BY mes ORDER BY mes
)--")

# 7. COHORTES: retencion de clientes segun su primer mes de compra ------------------
correr("7. Retencion por cohorte (% de clientes activos)", r"--(
WITH primera AS (
    SELECT id_cliente, date_trunc('month', min(fecha)) AS cohorte
    FROM ventas WHERE monto > 0 GROUP BY 1
), actividad AS (
    SELECT DISTINCT id_cliente, date_trunc('month', fecha) AS mes
    FROM ventas WHERE monto > 0
), conteo AS (
    SELECT p.cohorte, date_diff('month', p.cohorte, a.mes) AS mes_n, count(*) AS clientes
    FROM primera p JOIN actividad a USING (id_cliente)
    GROUP BY ALL
)
SELECT cohorte, mes_n, clientes,
       round(100.0 * clientes / first_value(clientes) OVER (PARTITION BY cohorte ORDER BY mes_n), 1) AS retencion_pct
FROM conteo ORDER BY cohorte, mes_n
)--", filas = 14)

# 8. JOIN CON PARQUET: cruzar la base .duckdb con una dimension externa --------------
correr("8. Ticket promedio por segmento (join con clientes.parquet)", plantilla(r"--(
SELECT c.segmento,
       count(DISTINCT v.id_cliente) AS clientes,
       round(avg(v.monto))          AS ticket_promedio,
       sum(v.monto)                 AS total
FROM ventas v
JOIN read_parquet('{ruta}') c ON c.id_cliente = v.id_cliente
WHERE v.monto > 0
GROUP BY c.segmento ORDER BY total DESC
)--", ruta = d("dim/clientes.parquet")))

# 9. PARQUET PARTICIONADO: escribir por mes y leer solo lo necesario -----------------
ejecutar(con, plantilla(r"--(
COPY (SELECT *, strftime(fecha, '%Y-%m') AS mes FROM ventas)
TO '{ruta}' (FORMAT parquet, PARTITION_BY (mes), OVERWRITE_OR_IGNORE)
)--", ruta = d("parquet/ventas")))
peso <- function(carpeta, patron) {
  sum(file.size(list.files(carpeta, pattern = patron, recursive = TRUE, full.names = TRUE))) / 1e6
}
cat(sprintf("\n=== 9. Peso en disco: CSV %.1f MB vs Parquet %.1f MB ===\n",
            peso(d("raw"), "\\.csv$"), peso(d("parquet/ventas"), "\\.parquet$")))
correr("9. Consulta sobre un solo mes (lee 1 particion, no las 12)", plantilla(r"--(
SELECT categoria, sum(monto) AS total
FROM read_parquet('{ruta}', hive_partitioning = true)
WHERE mes = '2025-06' AND monto > 0
GROUP BY categoria ORDER BY total DESC
)--", ruta = d("parquet/ventas/**/*.parquet")))

# 10. INCREMENTAL: insertar solo lo nuevo (el CSV trae filas ya cargadas) -------------
antes <- dbGetQuery(con, "SELECT count(*) AS n FROM ventas")$n
ejecutar(con, plantilla(r"--(
INSERT INTO ventas BY NAME
SELECT "ID Transaccion"             AS id_transaccion,
       "Fecha Venta"                AS fecha,
       "Monto Total"                AS monto,
       "ID Cliente"                 AS id_cliente,
       Categoria                    AS categoria,
       coalesce(Ciudad, 'Sin dato') AS ciudad,
       Canal                        AS canal,
       parse_filename(filename)     AS archivo
FROM read_csv_auto('{ruta}', filename = true)
WHERE "ID Transaccion" NOT IN (SELECT id_transaccion FROM ventas)
)--", ruta = d("incoming/nuevo_mes.csv")))
despues <- dbGetQuery(con, "SELECT count(*) AS n FROM ventas")$n
total_csv <- dbGetQuery(con, plantilla("SELECT count(*) AS n FROM read_csv_auto('{ruta}')",
                                       ruta = d("incoming/nuevo_mes.csv")))$n
cat(sprintf("\n=== 10. Carga incremental ===\nEn el CSV: %s | insertadas: %s | omitidas por ya existir: %s\n",
            format(total_csv, big.mark = ","), format(despues - antes, big.mark = ","),
            format(total_csv - (despues - antes), big.mark = ",")))

# 11. DERIVA DE ESQUEMA: archivos con columnas distintas -------------------------------
correr("11. union_by_name: columnas faltantes -> NULL, columnas extra -> se conservan", plantilla(r"--(
SELECT parse_filename(filename) AS archivo, count(*) AS filas,
       count(Canal) AS con_canal, count(Descuento) AS con_descuento, count(Cupon) AS con_cupon
FROM read_csv_auto('{ruta}', union_by_name = true, filename = true)
GROUP BY archivo ORDER BY archivo
)--", ruta = d("raw_drift/*.csv")))

# 12. LIMITE DE MEMORIA: consulta pesada con solo 1 GB de RAM -------------------------
cat("\n=== 12. Consulta pesada con memory_limit =",
    dbGetQuery(con, "SELECT current_setting('memory_limit') AS v")$v, "===\n")
t <- system.time(n_filas <- dbGetQuery(con, r"--(
SELECT count(*) AS n FROM (
    SELECT row_number() OVER (PARTITION BY id_cliente ORDER BY monto DESC, id_transaccion) AS rn
    FROM ventas
) WHERE rn = 1
)--")$n)[["elapsed"]]
cat(sprintf("Compra mas grande de cada cliente: %s clientes en %.2f s\n", format(n_filas, big.mark = ","), t))

dbDisconnect(con, shutdown = TRUE)
cat("\nListo. Base persistente:", d("database/ventas_avanzado.duckdb"), "\n")
