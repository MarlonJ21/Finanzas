# Proyecto RIAL -> Python -> Power BI ETL

ETL local y liviano que transforma el CSV exportado de RIAL en datasets financieros limpios y optimizados (Parquet) listos para consumir desde Power BI.

## Estructura del Proyecto

```
DWH/
├── raw/                      # Almacena el CSV exportado de RIAL (ej: rial-movimientos_*.csv)
├── config/                   # Configuración del motor de reglas y overrides manuales
│   ├── category_rules.csv          # Reglas por patrones regex, categorías y prioridades
│   └── transaction_overrides.csv   # Overrides manuales específicos por MovimientoId o descripción
├── src/                      # Código fuente del ETL en Python
│   ├── main.py                     # Script principal / CLI de orquestación
│   ├── normalize.py                # Parseo seguro de CSV, hashing de ID y cálculo FX
│   ├── classify.py                 # Motor de taxonomía analítica y flags financieros
│   └── quality.py                  # Validaciones de calidad y generación de reportes
├── output/                   # Datasets generados para Power BI y control
│   ├── movimientos.parquet         # Tabla de hechos transaccional principal
│   ├── categorias.parquet          # Catálogo único de dimensiones de categoría
│   ├── presupuesto.parquet         # Tabla de referencia presupuestaria por escenarios
│   ├── pendientes_clasificacion.csv# Transacciones ambiguas que requieren revisión manual
│   └── calidad_datos.json          # Resumen de métricas de calidad y totales de control
├── archive/                  # Respaldos y CSVs de ejecuciones históricas
└── logs/                     # Archivos de log del proceso
```

## Instrucciones de Uso

### 1. Reemplazar o Actualizar el CSV
Coloca el nuevo archivo CSV exportado de RIAL en la carpeta `raw/` (ej: `raw/rial-movimientos_2000-01-01_a_2100-12-31.csv`).

### 2. Ejecutar el ETL
Ejecuta el pipeline desde la raíz del proyecto usando `uv`:

```bash
uv run python src/main.py
```

### 3. Modificar / Agregar Reglas de Clasificación
Edita el archivo `config/category_rules.csv`. Las columnas principales son:
- `Priority`: Menor número = mayor prioridad (10 = regla específica/HIGH, 30 = regla general/MEDIUM).
- `PatternDescripcion`: Patrón Expresión Regular (regex, case-insensitive) para coincidir con la descripción.
- `Dominio`, `Categoria`, `Subcategoria`, `TitularGasto`, `NaturalezaFinanciera`: Taxonomía analítica asignada.

### 4. Overrides Manuales
Si una transacción específica no puede clasificarse dinámicamente por regla general, agrega una fila en `config/transaction_overrides.csv` especificando su `MovimientoId` o `DescripcionExacta`.

### 5. Revisar Pendientes de Clasificación
Si tras una ejecución la métrica `UNCLASSIFIED` es mayor a 0:
1. Revisa `output/pendientes_clasificacion.csv`.
2. Identifica el patrón recurrente y agrégalo en `config/category_rules.csv`.
3. Vuelve a ejecutar `uv run python src/main.py`.
