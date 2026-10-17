# Parte 2: Procesamiento masivo y consolidación con DuckDB en R.
# Wajiira Analytics

library(DBI)
library(duckdb)

# 1. Crear directorios necesarios
if(!dir.exists("../data/database")) dir.create("../data/database", recursive = TRUE)

# 2. Conectar a una base de datos persistente en disco
ruta_db <- "../data/database/ventas_consolidadas.duckdb"
con <- dbConnect(duckdb::duckdb(), dbdir = ruta_db)

# 3. Ingesta masiva y consolidación directa
query_ingesta <- "
CREATE OR REPLACE TABLE ventas_raw AS 
SELECT * 
FROM read_csv_auto('../data/raw/*.csv', filename=true);
"
dbExecute(con, query_ingesta)
cat("Tabla 'ventas_raw' creada exitosamente en disco.\n")

# 4. Crear una vista para limpieza e inspección
query_vista <- "
CREATE OR REPLACE VIEW vista_ventas_limpias AS 
SELECT 
    \"ID Transaccion\" AS id_transaccion,
    \"Fecha Venta\" AS fecha_venta,
    \"Monto Total\" AS monto_total,
    Categoria AS categoria,
    regexp_extract(filename, '([^/]+)$') AS archivo_origen
FROM ventas_raw;
"
dbExecute(con, query_vista)
cat("Vista 'vista_ventas_limpias' creada exitosamente.\n")

# 5. Consulta de interés directamente al motor de base de datos
query_analisis <- "
SELECT 
    archivo_origen, 
    categoria, 
    SUM(monto_total) as total_ventas 
FROM vista_ventas_limpias 
GROUP BY archivo_origen, categoria
ORDER BY total_ventas DESC;
"
resultado_df <- dbGetQuery(con, query_analisis)

cat("\nResumen consolidado de ventas:\n")
print(resultado_df)

# Cerrar la conexión
dbDisconnect(con, shutdown = TRUE)