zona_prop_url = "https://www.zonaprop.com.ar/"
max_number_pages_zonaprop = 1_000_000  # symbolic max para capturar la ultima pagina real
ZONAPROP_RESOLVE_DETAIL_COORDINATES = True
LOCALITY_SLUG = "entre-rios"  # slug base; Properati agrega -argentina automaticamente
PROVIDER = "batch"  # recomendado para cierre de version
# Orden recomendado para produccion: primero los mas estables, luego ML/Zonaprop.
PROVIDERS_TO_RUN =  [ "zonaprop" ]# ["argenprop", "properati", "inmobusqueda", "mercadolibre", "zonaprop"]
TYPE_OPERATION = "venta"   # opciones: "alquiler" | "venta"
TYPE_BUILDING  = "inmuebles"  # opciones: "inmuebles" | "locales-comerciales"
default_locality_slug_zonaprop = LOCALITY_SLUG

# ── Properati ─────────────────────────────────────────────────────────────────
PROPERATI_BASE_URL = "https://www.properati.com.ar"
PROPERATI_RESOLVE_DETAIL_COORDINATES = True

# ── MercadoLibre ──────────────────────────────────────────────────────────────
# La URL base debe ser inmuebles.mercadolibre.com.ar (no listado.) para evitar
# la protección anti-bot del dominio general.
MERCADOLIBRE_BASE_URL = "https://inmuebles.mercadolibre.com.ar"
# Ruta de búsqueda: /tipo-operacion/localidad/  (sin _NoIndex_True, se agrega auto)
MERCADOLIBRE_SOURCE_PATH = f"/{TYPE_OPERATION}/{LOCALITY_SLUG}/"
# Para priorizar volumen total en ML, evitar requests al detalle (anti-bot).
MERCADOLIBRE_RESOLVE_DETAIL_COORDINATES = False

# ── Argenprop ─────────────────────────────────────────────────────────────────
ARGENPROP_BASE_URL = "https://www.argenprop.com"
# La ruta efectiva se arma en main_scrap.py usando operación y localidad.
# Ejemplo venta en Entre Ríos: /inmuebles/venta/entre-rios-arg
ARGENPROP_MAX_PAGES = 20
ARGENPROP_RESOLVE_DETAIL_COORDINATES = True

# ── InmoBusqueda ──────────────────────────────────────────────────────────────
INMOBUSQUEDA_BASE_URL = "https://www.inmobusqueda.com.ar"
# Ruta de búsqueda: /tipo-operacion-localidad.html (sin -pagina-N, se agrega auto)
INMOBUSQUEDA_SOURCE_PATH = f"/departamento-alquiler-{LOCALITY_SLUG}.html"
INMOBUSQUEDA_RESOLVE_DETAIL_COORDINATES = True