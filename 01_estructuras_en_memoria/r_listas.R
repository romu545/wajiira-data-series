# Parte 1: Manejo de múltiples datasets en memoria usando Listas en R.
# Wajiira Analytics

# 1. Definir rutas
ruta_datos <- "../data/raw"
ruta_salida <- "../data/clean"
if(!dir.exists(ruta_salida)) dir.create(ruta_salida, recursive = TRUE)

# 2. Carga Masiva y Nombres
rutas_csv <- list.files(path = ruta_datos, pattern = "\\.csv$", full.names = TRUE)
nombres_archivos <- tools::file_path_sans_ext(basename(rutas_csv))

# Cargar en una lista y asignar nombres
datasets <- lapply(rutas_csv, read.csv)
names(datasets) <- nombres_archivos

cat("Se cargaron", length(datasets), "archivos:", names(datasets), "\n")

# 3. Operaciones de Limpieza
limpiar_dataset <- function(df) {
  # Estandarizar nombres de columnas a minúsculas y reemplazar espacios
  names(df) <- gsub(" ", "_", tolower(names(df)))
  # Aquí puedes agregar na.omit(), unique(), etc.
  return(df)
}

# Aplicar la limpieza a toda la lista
datasets_limpios <- lapply(datasets, limpiar_dataset)

# 4. Guardar Resultados
invisible(lapply(names(datasets_limpios), function(nombre) {
  archivo_salida <- file.path(ruta_salida, paste0(nombre, "_limpio.csv"))
  write.csv(datasets_limpios[[nombre]], archivo_salida, row.names = FALSE)
  cat("Guardado:", basename(archivo_salida), "\n")
}))