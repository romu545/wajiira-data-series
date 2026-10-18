"""
Parte 2 (avanzado): ejercicios con DuckDB en Python sobre datos ficticios.
Wajiira Analytics

Antes: python generar_datos.py
Ejecutar desde la carpeta 02_duckdb_grandes_volumenes.
"""
import os
import time
from pathlib import Path
import duckdb

DATA = Path() / "data"
d = lambda ruta: (DATA / ruta).as_posix()          # ruta con '/' (DuckDB la prefiere en Windows)

# --- Conexion persistente con limites de recursos --------------------------------
con = duckdb.connect(d("database/ventas_avanzado.duckdb"))
con.execute("SET memory_limit = '1GB'")             # DuckDB no usara mas RAM que esto
con.execute(f"SET temp_directory = '{d('tmp')}'")   # y volcara a disco lo que no quepa


def correr(titulo, sql, filas=12):
    """Ejecuta una consulta, imprime las primeras filas y el tiempo."""
    print(f"\n=== {titulo} ===")
    t0 = time.time()
    df = con.execute(sql).df()
    print(df.head(filas).to_string(index=False))
    print(f"-> {len(df)} filas en {time.time() - t0:.2f} s")


# 1. INGESTA: todos los CSV a una tabla, guardando de que archivo vino cada fila ----
con.execute(f"""
CREATE OR REPLACE TABLE ventas_raw AS
SELECT * FROM read_csv_auto('{d("raw/*.csv")}', filename = true)
""")

# 2. CALIDAD DE DATOS: diagnostico antes de limpiar ---------------------------------
correr("2. Diagnostico de calidad", """
SELECT count(*)                                            AS filas,
       count(DISTINCT "ID Transaccion")                    AS ids_unicos,
       count(*) - count(DISTINCT "ID Transaccion")         AS duplicados,
       count(*) FILTER (WHERE Ciudad IS NULL)              AS ciudad_nula,
       count(*) FILTER (WHERE "Monto Total" < 0)           AS devoluciones
FROM ventas_raw
""")

# Tabla limpia: QUALIFY elimina duplicados sin subconsultas anidadas
con.execute("""
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
""")

# 3. FUNCIONES VENTANA: crecimiento mensual y media movil por categoria -------------
correr("3. Crecimiento mensual y media movil (3 meses)", """
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
""", filas=14)

# 4. TOP-N POR GRUPO: las 3 mejores ciudades de cada categoria ----------------------
correr("4. Top 3 ciudades por categoria", """
SELECT categoria, ciudad, sum(monto) AS total,
       rank() OVER (PARTITION BY categoria ORDER BY sum(monto) DESC) AS posicion
FROM ventas WHERE monto > 0
GROUP BY categoria, ciudad
QUALIFY posicion <= 3
ORDER BY categoria, posicion
""", filas=18)

# 5. ASOF JOIN: convertir a USD con la TRM vigente (fines de semana usan el ultimo dia habil)
con.execute(f"CREATE OR REPLACE TABLE tasas AS SELECT * FROM read_csv_auto('{d('ref/tasas_cambio.csv')}')")
correr("5. Ventas mensuales en USD (ASOF JOIN con la TRM)", """
SELECT date_trunc('month', v.fecha) AS mes,
       round(sum(v.monto))          AS total_cop,
       round(sum(v.monto / t.trm_cop_usd)) AS total_usd
FROM ventas v
ASOF JOIN tasas t ON v.fecha >= t.fecha
WHERE v.monto > 0
GROUP BY 1 ORDER BY 1
""")

# 6. PIVOT: categorias como columnas -------------------------------------------------
correr("6. PIVOT: ventas por mes y categoria", """
PIVOT (SELECT strftime(fecha, '%Y-%m') AS mes, categoria, monto FROM ventas WHERE monto > 0)
ON categoria USING sum(monto)
GROUP BY mes ORDER BY mes
""")

# 7. COHORTES: retencion de clientes segun su primer mes de compra ------------------
correr("7. Retencion por cohorte (% de clientes activos)", """
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
""", filas=14)

# 8. JOIN CON PARQUET: cruzar la base .duckdb con una dimension externa --------------
correr("8. Ticket promedio por segmento (join con clientes.parquet)", f"""
SELECT c.segmento,
       count(DISTINCT v.id_cliente) AS clientes,
       round(avg(v.monto))          AS ticket_promedio,
       sum(v.monto)                 AS total
FROM ventas v
JOIN read_parquet('{d("dim/clientes.parquet")}') c ON c.id_cliente = v.id_cliente
WHERE v.monto > 0
GROUP BY c.segmento ORDER BY total DESC
""")

# 9. PARQUET PARTICIONADO: escribir por mes y leer solo lo necesario -----------------
con.execute(f"""
COPY (SELECT *, strftime(fecha, '%Y-%m') AS mes FROM ventas)
TO '{d("parquet/ventas")}' (FORMAT parquet, PARTITION_BY (mes), OVERWRITE_OR_IGNORE)
""")
peso = lambda patron: sum(p.stat().st_size for p in patron if p.is_file()) / 1e6
print(f"\n=== 9. Peso en disco: CSV {peso((DATA / 'raw').glob('*.csv')):.1f} MB "
      f"vs Parquet {peso((DATA / 'parquet' / 'ventas').rglob('*.parquet')):.1f} MB ===")
correr("9. Consulta sobre un solo mes (lee 1 particion, no las 12)", f"""
SELECT categoria, sum(monto) AS total
FROM read_parquet('{d("parquet/ventas/**/*.parquet")}', hive_partitioning = true)
WHERE mes = '2025-06' AND monto > 0
GROUP BY categoria ORDER BY total DESC
""")

# 10. INCREMENTAL: insertar solo lo nuevo (el CSV trae filas ya cargadas) -------------
antes = con.execute("SELECT count(*) FROM ventas").fetchone()[0]
con.execute(f"""
INSERT INTO ventas BY NAME
SELECT "ID Transaccion"             AS id_transaccion,
       "Fecha Venta"                AS fecha,
       "Monto Total"                AS monto,
       "ID Cliente"                 AS id_cliente,
       Categoria                    AS categoria,
       coalesce(Ciudad, 'Sin dato') AS ciudad,
       Canal                        AS canal,
       parse_filename(filename)     AS archivo
FROM read_csv_auto('{d("incoming/nuevo_mes.csv")}', filename = true)
WHERE "ID Transaccion" NOT IN (SELECT id_transaccion FROM ventas)
""")
despues = con.execute("SELECT count(*) FROM ventas").fetchone()[0]
total_csv = con.execute(f"SELECT count(*) FROM read_csv_auto('{d('incoming/nuevo_mes.csv')}')").fetchone()[0]
print(f"\n=== 10. Carga incremental ===\nEn el CSV: {total_csv:,} | insertadas: {despues - antes:,} "
      f"| omitidas por ya existir: {total_csv - (despues - antes):,}")

# 11. DERIVA DE ESQUEMA: archivos con columnas distintas -------------------------------
correr("11. union_by_name: columnas faltantes -> NULL, columnas extra -> se conservan", f"""
SELECT parse_filename(filename) AS archivo, count(*) AS filas,
       count(Canal) AS con_canal, count(Descuento) AS con_descuento, count(Cupon) AS con_cupon
FROM read_csv_auto('{d("raw_drift/*.csv")}', union_by_name = true, filename = true)
GROUP BY archivo ORDER BY archivo
""")

# 12. LIMITE DE MEMORIA: consulta pesada con solo 1 GB de RAM -------------------------
print("\n=== 12. Consulta pesada con memory_limit =",
      con.execute("SELECT current_setting('memory_limit')").fetchone()[0], "===")
t0 = time.time()
n_filas = con.execute("""
SELECT count(*) FROM (
    SELECT row_number() OVER (PARTITION BY id_cliente ORDER BY monto DESC, id_transaccion) AS rn
    FROM ventas
) WHERE rn = 1
""").fetchone()[0]
print(f"Compra mas grande de cada cliente: {n_filas:,} clientes en {time.time() - t0:.2f} s")

con.close()
print("\nListo. Base persistente:", d("database/ventas_avanzado.duckdb"))
