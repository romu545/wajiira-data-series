"""
Parte 1: Manejo de múltiples datasets en memoria usando Diccionarios en Python.
Wajiira Analytics
"""
from pathlib import Path
import pandas as pd

# 1. Definir rutas
ruta_datos = Path("../data/raw")
ruta_salida = Path("../data/clean")
ruta_salida.mkdir(parents=True, exist_ok=True) # Crea la carpeta si no existe

# 2. Carga Masiva y Nombres (Diccionario por comprensión)
# rglob("*.csv") busca todos los CSV, iteramos y asignamos el nombre del archivo (stem) como llave
rutas_csv = list(ruta_datos.rglob("*.csv"))
datasets = {archivo.stem: pd.read_csv(archivo) for archivo in rutas_csv}

print(f"Se cargaron {len(datasets)} archivos: {list(datasets.keys())}")

# 3. Operaciones de Limpieza (Ejemplo: estandarizar nombres de columnas)
def limpiar_dataset(df):
    df.columns = df.columns.str.lower().str.replace(' ', '_')
    # Aquí puedes agregar fillna(), drop_duplicates(), etc.
    return df

# Aplicamos la limpieza a cada dataset usando dict comprehension
datasets_limpios = {nombre: limpiar_dataset(df) for nombre, df in datasets.items()}

# 4. Guardar Resultados
for nombre, df in datasets_limpios.items():
    archivo_salida = ruta_salida / f"{nombre}_limpio.csv"
    df.to_csv(archivo_salida, index=False)
    print(f"Guardado: {archivo_salida.name}")