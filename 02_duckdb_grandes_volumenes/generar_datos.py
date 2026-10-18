"""
Generador de datos FICTICIOS para practicar DuckDB.
Wajiira Analytics

Crea, dentro de ../data/:
  raw/          12 CSV mensuales de 2025 (mismo esquema, con duplicados y nulos a proposito)
  incoming/     nuevo_mes.csv (enero 2026; incluye filas ya cargadas en diciembre)
  raw_drift/    2 CSV con el esquema cambiado (columnas en otro orden, extra o faltantes)
  dim/          clientes.parquet (tabla de dimension)
  ref/          tasas_cambio.csv (TRM diaria, solo dias habiles)

Uso (desde la carpeta 02_duckdb_grandes_volumenes):
  python generar_datos.py                  # 250.000 filas por mes (~3 millones)
  python generar_datos.py --filas 50000    # prueba rapida
  python generar_datos.py --filas 2000000  # ~24 millones de filas (necesita disco)
"""
import argparse
from pathlib import Path
import duckdb

ap = argparse.ArgumentParser()
ap.add_argument("--filas", type=int, default=250_000, help="filas por mes")
n = ap.parse_args().filas
n_clientes = max(300_000 // 2, 1_000)
n=300_000
DATA = Path() / "data"
for d in ["raw", "incoming", "raw_drift", "dim", "ref", "database", "parquet", "tmp"]:
    (DATA / d).mkdir(parents=True, exist_ok=True)

con = duckdb.connect()                     # en memoria: solo se usa para generar
con.execute("SET threads TO 1")            # con un hilo, setseed da resultados repetibles
con.execute("SELECT setseed(0.42)")


def crear_ventas(tabla, anio, mes_ini, mes_fin, filas):
    """Crea una tabla de ventas ficticias con las mismas columnas que los CSV."""
    con.execute(f"""
    CREATE OR REPLACE TABLE {tabla} AS
    WITH b AS (
        SELECT mes, i,
               1 + CAST(floor(pow(random(), 1.5) * 6) AS INT) AS cat,
               1 + CAST(floor(random() * 8) AS INT)           AS ci,
               1 + CAST(floor(random() * 4) AS INT)           AS ca,
               CAST(floor(pow(random(), 2) * {n_clientes}) AS BIGINT) + 1 AS cli,
               random() AS r_monto, random() AS r_null, random() AS r_neg
        FROM range({mes_ini}, {mes_fin} + 1) AS m(mes), range({filas}) AS r(i)
    )
    SELECT
        mes,
        'TX-{anio}' || lpad(CAST(mes AS VARCHAR), 2, '0') || '-' || lpad(CAST(i AS VARCHAR), 7, '0')
            AS "ID Transaccion",
        make_date({anio}, mes, 1)
            + CAST(floor(random() * day(last_day(make_date({anio}, mes, 1)))) AS INT)
            AS "Fecha Venta",
        CAST(round((15000 + pow(r_monto, 3) * 900000)
              * list_extract([1.8, 1.0, 0.6, 0.3, 0.7, 0.5], cat)
              * (CASE WHEN mes = 12 THEN 1.35 WHEN mes = 11 THEN 1.15 ELSE 1 END) / 50) * 50
              AS BIGINT) * (CASE WHEN r_neg < 0.002 THEN -1 ELSE 1 END)   AS "Monto Total",
        list_extract(['Tecnologia','Hogar','Moda','Alimentos','Deportes','Salud'], cat) AS Categoria,
        'C' || lpad(CAST(cli AS VARCHAR), 6, '0')                                        AS "ID Cliente",
        CASE WHEN r_null < 0.01 THEN NULL
             ELSE list_extract(['Bogota','Medellin','Cali','Barranquilla','Santa Marta',
                                'Cartagena','Bucaramanga','Pereira'], ci) END           AS Ciudad,
        list_extract(['Web','App','Tienda','Marketplace'], ca)                           AS Canal
    FROM b
    """)


COLS = '"ID Transaccion","Fecha Venta","Monto Total",Categoria,"ID Cliente",Ciudad,Canal'

# 1. raw: 12 meses de 2025 + duplicados accidentales (~0.05 %)
crear_ventas("todo", 2025, 1, 12, n)
con.execute("INSERT INTO todo SELECT * FROM todo WHERE random() < 0.0005")
for m in range(1, 13):
    ruta = (DATA / "raw" / f"ventas_2025_{m:02d}.csv").as_posix()
    con.execute(f"COPY (SELECT {COLS} FROM todo WHERE mes = {m}) TO '{ruta}' (HEADER, DELIMITER ',')")
    print(f"  raw/ventas_2025_{m:02d}.csv")

# 2. incoming: enero 2026 + filas de diciembre reenviadas (para practicar el INSERT sin duplicar)
crear_ventas("nuevo", 2026, 1, 1, max(n // 10, 1_000))
con.execute("INSERT INTO nuevo SELECT * FROM todo WHERE mes = 12 AND random() < 0.005")
ruta = (DATA / "incoming" / "nuevo_mes.csv").as_posix()
con.execute(f"COPY (SELECT {COLS} FROM nuevo) TO '{ruta}' (HEADER, DELIMITER ',')")
print("  incoming/nuevo_mes.csv")

# 3. raw_drift: esquemas que cambian entre archivos
crear_ventas("drift", 2026, 2, 3, 20_000)
r1 = (DATA / "raw_drift" / "ventas_2026_02.csv").as_posix()
r2 = (DATA / "raw_drift" / "ventas_2026_03.csv").as_posix()
con.execute(f"""COPY (SELECT "Fecha Venta","ID Transaccion","ID Cliente",Categoria,"Monto Total",
                              Ciudad,Canal, round(random() * 0.2, 2) AS Descuento
                       FROM drift WHERE mes = 2) TO '{r1}' (HEADER, DELIMITER ',')""")
con.execute(f"""COPY (SELECT "ID Transaccion","Fecha Venta","Monto Total",Categoria,"ID Cliente",Ciudad,
                              CASE WHEN random() < 0.3 THEN 'PROMO10' END AS Cupon
                       FROM drift WHERE mes = 3) TO '{r2}' (HEADER, DELIMITER ',')""")
print("  raw_drift/ (2 archivos)")

# 4. dimension de clientes (Parquet)
ruta = (DATA / "dim" / "clientes.parquet").as_posix()
con.execute(f"""
COPY (SELECT 'C' || lpad(CAST(i + 1 AS VARCHAR), 6, '0') AS id_cliente,
             list_extract(['Retail','Pyme','Corporativo'], 1 + CAST(floor(pow(random(), 2) * 3) AS INT)) AS segmento,
             make_date(2023, 1, 1) + CAST(floor(random() * 900) AS INT) AS fecha_registro
      FROM range({n_clientes}) t(i)) TO '{ruta}' (FORMAT parquet)""")
print("  dim/clientes.parquet")

# 5. tasa de cambio diaria, solo dias habiles (los fines de semana no tienen dato a proposito)
ruta = (DATA / "ref" / "tasas_cambio.csv").as_posix()
con.execute(f"""
COPY (SELECT CAST(d AS DATE) AS fecha,
             round(4100 + 220 * sin(epoch(d) / 86400.0 / 35.0) + random() * 40, 2) AS trm_cop_usd
      FROM generate_series(TIMESTAMP '2025-01-01', TIMESTAMP '2026-03-31', INTERVAL 1 DAY) t(d)
      WHERE isodow(d) < 6) TO '{ruta}' (HEADER, DELIMITER ',')""")
print("  ref/tasas_cambio.csv")
print(f"\nListo. {12 * n:,} filas en raw/ (mas duplicados) -> {DATA}")
