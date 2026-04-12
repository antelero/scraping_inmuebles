import time
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from src.zonaprop import main_scrap_zonaprop
from src.constants import (
    LOCALITY_SLUG,
    PROVIDER,
    PROVIDERS_TO_RUN,
    TYPE_OPERATION,
    TYPE_BUILDING,
    PROPERATI_BASE_URL,
    PROPERATI_RESOLVE_DETAIL_COORDINATES,
    MERCADOLIBRE_BASE_URL,
    MERCADOLIBRE_SOURCE_PATH,
    MERCADOLIBRE_RESOLVE_DETAIL_COORDINATES,
    ARGENPROP_BASE_URL,
    ARGENPROP_MAX_PAGES,
    ARGENPROP_RESOLVE_DETAIL_COORDINATES,
    INMOBUSQUEDA_BASE_URL,
    INMOBUSQUEDA_SOURCE_PATH,
    INMOBUSQUEDA_RESOLVE_DETAIL_COORDINATES,
)


def _build_properati_source(type_operation: str, type_building: str, locality_slug: str) -> str:
    # Properati actual suele resolver como /s/<localidad>/<operacion> para busquedas generales.
    if type_building == "inmuebles":
        return f"/s/{locality_slug}/{type_operation}"
    return f"/s/{locality_slug}/{type_building}/{type_operation}"


def _build_argenprop_source(type_operation: str, type_building: str, locality_slug: str) -> str:
    if type_building == "inmuebles":
        return f"/inmuebles/{type_operation}/{locality_slug}-arg"
    return f"/{type_building}/{type_operation}/{locality_slug}-arg"


PROPERATI_SOURCES = [
    _build_properati_source(TYPE_OPERATION, TYPE_BUILDING, LOCALITY_SLUG)
]


ARGENPROP_SOURCES = [
    _build_argenprop_source(TYPE_OPERATION, TYPE_BUILDING, LOCALITY_SLUG)
]


def _validate_coordinate_quality(rows: list[dict], provider_name: str) -> None:
    """Muestra un resumen simple de calidad de coordenadas del resultado exportado."""
    if not rows:
        return

    df = pd.DataFrame(rows)
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        print(f"[{provider_name}] Sin columnas de coordenadas para validar.")
        return

    total = len(df)
    missing = int((df['latitude'].isna() | df['longitude'].isna()).sum())
    valid_mask = df['latitude'].notna() & df['longitude'].notna()
    valid = df[valid_mask]

    # Caja aproximada de Argentina continental.
    arg_outliers = valid[
        (valid['latitude'] < -56) |
        (valid['latitude'] > -21) |
        (valid['longitude'] < -74) |
        (valid['longitude'] > -53)
    ]

    print(
        f"[{provider_name}] Coordenadas: total={total} | completas={len(valid)} | "
        f"faltantes={missing} | fuera_ARG={len(arg_outliers)}"
    )

    # Si se trabaja en Entre Ríos, chequeo adicional de desvíos groseros.
    if LOCALITY_SLUG == 'entre-rios' and not valid.empty:
        er_outliers = valid[
            (valid['latitude'] < -34.95) |
            (valid['latitude'] > -29.0) |
            (valid['longitude'] < -60.95) |
            (valid['longitude'] > -57.7)
        ]
        print(f"[{provider_name}] Coordenadas fuera de caja Entre Ríos: {len(er_outliers)}")


def _export_results(rows: list[dict], provider_name: str, suffix: str = "") -> None:
    """Exporta una lista de dicts a CSV y PKL bajo output/."""
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    parts = [provider_name]
    if suffix:
        parts.append(suffix)
    parts.append(timestamp)
    base_name = "_".join(parts)

    df = pd.DataFrame(rows)
    expected_columns = [
        'title', 'url', 'internal_id', 'provider', 'location',
        'features', 'bedrooms', 'bathrooms', 'area_m2',
        'latitude', 'longitude'
    ]
    for col in expected_columns:
        if col not in df.columns:
            df[col] = None
    df = df.reindex(columns=expected_columns + [c for c in df.columns if c not in expected_columns])
    if not df.empty:
        df["scrap_date"] = datetime.now()

    csv_path = output_dir / f"{base_name}.csv"
    pkl_path = output_dir / f"{base_name}.pkl"

    df.to_csv(csv_path, index=False, encoding="utf-8")
    df.to_pickle(pkl_path)

    print(f"Export CSV {provider_name}: {csv_path}")
    print(f"Export PKL {provider_name}: {pkl_path}")
    _validate_coordinate_quality(rows, provider_name)


def _export_properati_results(rows: list[dict]) -> None:
    suffix = f"{TYPE_OPERATION}_{TYPE_BUILDING}_{LOCALITY_SLUG}"
    _export_results(rows, "properati", suffix)


def run_zonaprop() -> None:
    main_scrap_zonaprop(
        type_operation=TYPE_OPERATION,
        type_building=TYPE_BUILDING,
        locality_slug=LOCALITY_SLUG,
        export_final_results=True,
    )


def run_properati() -> None:
    from providers.processor import process_properties

    provider_data = {
        "base_url": PROPERATI_BASE_URL,
        "sources": PROPERATI_SOURCES,
        "resolve_detail_coordinates": PROPERATI_RESOLVE_DETAIL_COORDINATES,
    }
    nuevas, todas = process_properties("properati", provider_data, include_all=True)
    print(f"Propiedades scrapeadas Properati: {len(todas)}")
    print(f"Nuevas propiedades Properati: {len(nuevas)}")
    _export_properati_results(todas)


def run_mercadolibre() -> None:
    from providers.processor import process_properties

    provider_data = {
        "base_url": MERCADOLIBRE_BASE_URL,
        "sources": [MERCADOLIBRE_SOURCE_PATH],
        "resolve_detail_coordinates": MERCADOLIBRE_RESOLVE_DETAIL_COORDINATES,
    }
    nuevas, todas = process_properties("mercadolibre", provider_data, include_all=True)
    print(f"Propiedades scrapeadas MercadoLibre: {len(todas)}")
    print(f"Nuevas propiedades MercadoLibre: {len(nuevas)}")
    _export_results(todas, "mercadolibre")


def run_argenprop() -> None:
    from providers.processor import process_properties

    provider_data = {
        "base_url": ARGENPROP_BASE_URL,
        "sources": ARGENPROP_SOURCES,
        "max_pages": ARGENPROP_MAX_PAGES,
        "resolve_detail_coordinates": ARGENPROP_RESOLVE_DETAIL_COORDINATES,
    }
    nuevas, todas = process_properties("argenprop", provider_data, include_all=True)
    print(f"Propiedades scrapeadas Argenprop: {len(todas)}")
    print(f"Nuevas propiedades Argenprop: {len(nuevas)}")
    _export_results(todas, "argenprop")


def run_inmobusqueda() -> None:
    from providers.processor import process_properties

    provider_data = {
        "base_url": INMOBUSQUEDA_BASE_URL,
        "sources": [INMOBUSQUEDA_SOURCE_PATH],
        "resolve_detail_coordinates": INMOBUSQUEDA_RESOLVE_DETAIL_COORDINATES,
    }
    nuevas, todas = process_properties("inmobusqueda", provider_data, include_all=True)
    print(f"Propiedades scrapeadas InmoBusqueda: {len(todas)}")
    print(f"Nuevas propiedades InmoBusqueda: {len(nuevas)}")
    _export_results(todas, "inmobusqueda")


PROVIDER_RUNNERS = {
    "zonaprop": run_zonaprop,
    "properati": run_properati,
    "mercadolibre": run_mercadolibre,
    "argenprop": run_argenprop,
    "inmobusqueda": run_inmobusqueda,
}


def run_batch() -> None:
    seen = set()
    ordered = []
    for name in PROVIDERS_TO_RUN:
        if name not in seen:
            ordered.append(name)
            seen.add(name)

    if not ordered:
        raise ValueError("PROVIDERS_TO_RUN esta vacio. Configuralo en src/constants.py")

    logging.info("Inicio batch providers: %s", ", ".join(ordered))
    for provider_name in ordered:
        runner = PROVIDER_RUNNERS.get(provider_name)
        if runner is None:
            raise ValueError(f"Provider no soportado en PROVIDERS_TO_RUN: {provider_name}")
        logging.info("Batch ejecutando provider: %s", provider_name)
        runner()
    logging.info("Batch finalizado")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    inicio = time.time()
    if PROVIDER == "batch":
        run_batch()
    else:
        runner = PROVIDER_RUNNERS.get(PROVIDER)
        if runner is None:
            raise ValueError(f"Proveedor no soportado: {PROVIDER}")
        runner()

    final = time.time()
    tiempo_total = final - inicio
    # Convertir el tiempo a formato horas: minutos: segundos
    horas, resto = divmod(tiempo_total, 3600)
    minutos, segundos = divmod(resto, 60)
    
    # Guardar el tiempo de ejecución en un archivo .txt
    with open("tiempo_ejecucion.txt", "w") as file:
        file.write(f"Tiempo total de ejecución: {int(horas)}:{int(minutos)}:{int(segundos)}\n")
"""
    main_scrap_zonaprop(
        type_operation="venta",
        type_building="departamentos",
        locality_slug=LOCALITY_SLUG,
        export_final_results=True
        )
    
    main_scrap_zonaprop(
        type_operation="alquiler",
        type_building="locales-comerciales",
        locality_slug=LOCALITY_SLUG,
        export_final_results=True
        )
    
    main_scrap_zonaprop(
        type_operation="venta",
        type_building="locales-comerciales",
        locality_slug=LOCALITY_SLUG,
        export_final_results=True
        )
    
    
    main_scrap_zonaprop(
        type_operation="alquiler",
        type_building="oficinas-comerciales",
        locality_slug=LOCALITY_SLUG,
        export_final_results=True
        )
    
    main_scrap_zonaprop(
        type_operation="venta",
        type_building="oficinas-comerciales",
        locality_slug=LOCALITY_SLUG,
        export_final_results=True
        )
"""  