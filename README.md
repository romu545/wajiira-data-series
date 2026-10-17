# Serie: Patrones de Procesamiento de Datos

Repositorio complementario a la serie de publicaciones de Wajiira Analytics sobre optimización y automatización de flujos de trabajo en Data Science.

## Parte 1: Estructuras Iterables en Memoria

**¿Cómo manejar decenas de archivos sin crear decenas de variables?**

En esta sección exploramos cómo cargar, limpiar y exportar múltiples archivos simultáneamente utilizando estructuras nativas:

* **Python:** Diccionarios + `pathlib` + `pandas`
* **R:** Listas + `lapply` + R Base

**Código:** [Ir a la Parte 1](./01_estructuras_en_memoria/)

## Parte 2: Consolidación y Grandes Volúmenes con DuckDB

Cuando los archivos de datos superan la memoria RAM disponible o se requiere una gestión más centralizada, el uso de listas y diccionarios deja de ser óptimo. 

En esta sección implementamos un flujo de trabajo basado en **DuckDB**. Este enfoque permite:
* Leer masivamente múltiples archivos directamente desde el disco.
* Consolidar la información en una única base de datos persistente (`.duckdb`).
* Crear vistas analíticas (`VIEWS`) para la limpieza y estandarización de columnas sin duplicar datos.
* Ejecutar consultas complejas (agrupaciones, filtros) delegando el esfuerzo computacional al motor de base de datos, evitando mantener variables pesadas dentro de la memoria del IDE.

**Código:** [Ir a la Parte 2](./02_duckdb_grandes_volumenes/)


---

### Cómo usar este repositorio

1. Clona el repositorio: `git clone https://github.com/romu545/wajiira-data-series.git`
2. Coloca los archivos de prueba (`.csv`) en la carpeta `data/raw/`.
3. Ejecuta los scripts de la carpeta `01_estructuras_en_memoria`.
4. Revisa los archivos procesados en `data/clean/`.

*Desarrollado por Wajiira Analytics*