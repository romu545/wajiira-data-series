"""
Parte 2: Procesamiento masivo y consolidación con DuckDB en Python.
Wajiira Analytics
"""
import duckdb
from pathlib import Path

# 1. Crear directorios necesarios
Path("../data/database").mkdir(parents=True, exist_ok=True)

# 2. Conectar a una base de datos persistente en disco
ruta_db = "../data/database/ventas_consolidadas.duckdb"
con = duckdb.connect(ruta_db)

# 3. Ingesta masiva y consolidación directa
# read_csv_auto lee todos los archivos y filename=true agrega una columna con la ruta de origen
query_ingesta = """
CREATE OR REPLACE TABLE ventas_raw AS 
SELECT * 
FROM read_csv_auto('../data/raw/*.csv', filename=true);
"""
con.execute(query_ingesta)
print("Tabla 'ventas_raw' creada exitosamente en disco.")

# 4. Crear una vista para limpieza e inspeccion (no ocupa espacio extra)
query_vista = """
CREATE OR REPLACE VIEW vista_ventas_limpias AS 
SELECT 
    "ID Transaccion" AS id_transaccion,
    "Fecha Venta" AS fecha_venta,
    "Monto Total" AS monto_total,
    Categoria AS categoria,
    regexp_extract(filename, '([^/]+)$') AS archivo_origen
FROM ventas_raw;
"""
con.execute(query_vista)
print("Vista 'vista_ventas_limpias' creada exitosamente.")

# 5. Consulta de interés: Agrupación sin cargar el dataset completo en el IDE
query_analisis = """
SELECT 
    archivo_origen, 
    categoria, 
    SUM(monto_total) as total_ventas 
FROM vista_ventas_limpias 
GROUP BY archivo_origen, categoria
ORDER BY total_ventas DESC;
"""
resultado_df = con.execute(query_analisis).df()

print("\nResumen consolidado de ventas:")
print(resultado_df)

# Cerrar la conexión
con.close()