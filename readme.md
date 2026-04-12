# Scrap de Inmuebles Argentina

Proyecto de scraping inmobiliario multi-proveedor para Argentina.

Actualmente soporta:

- Zonaprop
- Properati
- MercadoLibre Inmuebles
- Argenprop
- InmoBusqueda

Los resultados se exportan en `output/` como CSV y PKL, y además se mantiene un registro incremental en `properties.db` para detectar publicaciones nuevas por proveedor.

## Estructura del repositorio

- `main_scrap.py`: entrypoint principal. Ejecuta el proveedor configurado y exporta resultados.
- `src/constants.py`: configuración central (proveedor, operación, tipo y rutas base).
- `providers/`: scrapers por proveedor + procesador común.
- `src/`: utilidades y scraper específico de Zonaprop.
- `database_consolidation.py`: consolida múltiples PKL por patrón en un único archivo.
- `output/`: archivos generados por corrida (CSV/PKL).
- `properties.db`: base SQLite local de publicaciones ya vistas.

## Requisitos

- Python 3.11+
- pip
- (Opcional) Docker

## Instalación local (Windows / PowerShell)

1. Clonar repositorio:

```bash
git clone <URL_DEL_REPO_ORIGINAL> scraping_inmuebles
cd scraping_inmuebles
```

2. Crear y activar entorno virtual:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

## Configuración de scraping

Editar `src/constants.py`:

- `PROVIDER`: `"zonaprop" | "properati" | "mercadolibre" | "argenprop" | "inmobusqueda" | "batch"`
- `PROVIDERS_TO_RUN`: lista de providers para corrida múltiple cuando `PROVIDER="batch"`
- `TYPE_OPERATION`: `"alquiler" | "venta"`
- `TYPE_BUILDING`: actualmente usado para Properati (`"inmuebles"` o `"locales-comerciales"`)
- `LOCALITY_SLUG`: slug de ubicación (ejemplo: `"entre-rios"`, `"parana"`)

Además, cada proveedor tiene sus constantes específicas de URL/path en el mismo archivo.

## Ejecución

### Opción 1: flujo principal

```bash
python main_scrap.py
```

Esto ejecuta el proveedor configurado en `PROVIDER` y exporta resultados en `output/`.

Si querés ejecutar todos los parsers configurados en una sola llamada:

1. En `src/constants.py` definir `PROVIDER = "batch"`.
2. Ajustar `PROVIDERS_TO_RUN` con el orden deseado.
3. Ejecutar igual:

```bash
python main_scrap.py
```

## Consolidación de datos

Para consolidar múltiples PKL en un archivo por patrón:

```bash
python database_consolidation.py
```

Genera archivos `*_consolidado.pkl` dentro de `output/`.

## Docker

1. Build de imagen:

```bash
docker build -t mi-scraper .
```

2. Ejecutar contenedor y persistir salida:

```bash
docker run -it --rm -v "${PWD}/output:/app/output" mi-scraper
```

Nota: el `Dockerfile` ejecuta `python main_scrap.py` por defecto.

## Llevar este proyecto a tu propio repositorio

Escenario típico: querés partir de este código y publicarlo en tu GitHub propio.

1. Clonar el repo original:

```bash
git clone <URL_DEL_REPO_ORIGINAL> scraping_inmuebles
cd scraping_inmuebles
```

2. Crear un repo vacío en tu cuenta (GitHub/GitLab), sin README inicial.

3. Cambiar el remoto `origin` al tuyo:

```bash
git remote remove origin
git remote add origin <URL_DE_TU_REPO>
```

4. Verificar remotos:

```bash
git remote -v
```

5. Subir rama principal:

```bash
git branch -M main
git push -u origin main
```

Si querés conservar también el remoto original, en vez de borrar `origin` podés hacer:

```bash
git remote rename origin upstream
git remote add origin <URL_DE_TU_REPO>
git push -u origin main
```

## Referencia al repositorio original

Si este proyecto parte de otro repositorio, es recomendable dejarlo explícito por trazabilidad.

1. Mantener el remoto original como `upstream`:

```bash
git remote rename origin upstream
git remote add origin <URL_DE_TU_REPO>
```

2. Verificar remotos:

```bash
git remote -v
```

3. Agregar una nota de crédito en este README (por ejemplo):

- Repositorio base: <URL_DEL_REPO_ORIGINAL>
- Este repositorio: fork/adaptación para scraping_inmuebles