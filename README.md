# Serie: Patrones de Procesamiento de Datos

Repositorio complementario a la serie de publicaciones de Wajiira Analytics sobre optimización y automatización de flujos de trabajo en Data Science.

## Parte 1: Estructuras Iterables en Memoria

**¿Cómo manejar decenas de archivos sin crear decenas de variables?**

En esta sección exploramos cómo cargar, limpiar y exportar múltiples archivos simultáneamente utilizando estructuras nativas:

* **Python:** Diccionarios + `pathlib` + `pandas`
* **R:** Listas + `lapply` + R Base

**Código:** [Ir a la Parte 1](./01_estructuras_en_memoria/)

## Parte 2: Grandes Volúmenes con DuckDB (Proximamente)

Cuando los archivos superan la memoria RAM disponible, las listas y diccionarios ya no son suficientes. En la segunda parte de esta serie, exploraremos cómo utilizar DuckDB para consultar y procesar múltiples archivos pesados directamente desde el disco, sin colapsar el entorno.

---

### Cómo usar este repositorio

1. Clona el repositorio: `git clone https://github.com/romu545/wajiira-data-series.git`
2. Coloca los archivos de prueba (`.csv`) en la carpeta `data/raw/`.
3. Ejecuta los scripts de la carpeta `01_estructuras_en_memoria`.
4. Revisa los archivos procesados en `data/clean/`.

*Desarrollado por Wajiira Analytics*