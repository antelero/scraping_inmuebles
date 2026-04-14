import os
import re
import pandas as pd
from datetime import datetime

OUTPUT_DIR = "output"
PROVIDERS = ["argenprop", "properati", "mercadolibre", "zonaprop", "inmobusqueda"]
DATE_REGEX = re.compile(r"(\d{4}_\d{2}_\d{2}(?:_\d{2}_\d{2}_\d{2})?)\.pkl$")


def extract_scrap_date(filename):
    match = DATE_REGEX.search(filename)
    return match.group(1).replace("_", "-") if match else None


def _parse_zonaprop_features(features_list):
    """Parsea la lista Features de zonaprop → (area_m2, bedrooms, bathrooms, ambientes, cocheras)."""
    area_m2, bedrooms, bathrooms, ambientes, cocheras = None, None, None, None, None
    for item in features_list:
        s = str(item)
        if "m²" in s:
            try:
                area_m2 = float(s.split()[0].replace(",", "."))
            except (ValueError, IndexError):
                pass
        elif "dorm." in s:
            try:
                bedrooms = int(s.split()[0])
            except (ValueError, IndexError):
                pass
        elif "baños" in s:
            try:
                bathrooms = int(s.split()[0])
            except (ValueError, IndexError):
                pass
        elif "amb." in s:
            try:
                ambientes = int(s.split()[0])
            except (ValueError, IndexError):
                pass
        elif "coch." in s:
            try:
                cocheras = int(s.split()[0])
            except (ValueError, IndexError):
                pass
    return area_m2, bedrooms, bathrooms, ambientes, cocheras


def _normalize_features(df, prov):
    """Convierte columnas features de listas a strings; en zonaprop extrae columnas estructuradas."""
    # Zonaprop: renombrar columnas al esquema estándar
    if prov == "zonaprop":
        rename_map = {}
        if "Description" in df.columns and "title" not in df.columns:
            rename_map["Description"] = "title"
        if "Link" in df.columns and "url" not in df.columns:
            rename_map["Link"] = "url"
        if "id" in df.columns and "internal_id" not in df.columns:
            rename_map["id"] = "internal_id"
        if "Location" in df.columns and "location" not in df.columns:
            rename_map["Location"] = "location"
        elif "Address" in df.columns and "location" not in df.columns:
            rename_map["Address"] = "location"
        if rename_map:
            df = df.rename(columns=rename_map)

    # Zonaprop: parsear Features → columnas individuales + string legible
    if prov == "zonaprop" and "Features" in df.columns:
        parsed = df["Features"].apply(
            lambda x: _parse_zonaprop_features(x) if isinstance(x, list) else (None, None, None, None, None)
        )
        parsed_df = pd.DataFrame(
            list(parsed),
            columns=["area_m2", "bedrooms", "bathrooms", "ambientes", "cocheras"],
            index=df.index,
        )
        for col in parsed_df.columns:
            if col not in df.columns:
                df[col] = parsed_df[col]
        df["features"] = df["Features"].apply(
            lambda x: " | ".join(str(v).strip() for v in x) if isinstance(x, list) else (str(x) if pd.notna(x) else "")
        )
        df = df.drop(columns=["Features"])

    # Todos los providers: convertir lista features → string " | "
    if "features" in df.columns:
        df["features"] = df["features"].apply(
            lambda x: " | ".join(str(v).strip() for v in x) if isinstance(x, list) else x
        )

    return df


def _ensure_columns(df, filename, provider):
    if "provider" not in df.columns:
        df["provider"] = provider
    if "scrap_date" not in df.columns:
        df["scrap_date"] = extract_scrap_date(filename)
    if "property_type" not in df.columns:
        df["property_type"] = ""
    return df


def _cleanup_old_consolidated():
    """Elimina archivos consolidados de ejecuciones anteriores."""
    for f in os.listdir(OUTPUT_DIR):
        if "_consolidado_" in f and (f.endswith(".pkl") or f.endswith(".csv")):
            os.remove(os.path.join(OUTPUT_DIR, f))
            print(f"[cleanup] {f}")


def main():
    _cleanup_old_consolidated()

    files = [
        f
        for f in os.listdir(OUTPUT_DIR)
        if f.endswith(".pkl") and "_consolidado" not in f
    ]
    grouped = {prov: [] for prov in PROVIDERS}
    for f in files:
        for prov in PROVIDERS:
            if f.startswith(prov):
                grouped[prov].append(f)
                break

    all_dfs = []
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

    for prov, file_list in grouped.items():
        if not file_list:
            print(f"[{prov}] Sin archivos PKL, se omite.")
            continue
        dfs = []
        for fname in sorted(file_list):
            try:
                df = pd.read_pickle(os.path.join(OUTPUT_DIR, fname))
                df = _ensure_columns(df, fname, prov)
                df = _normalize_features(df, prov)
                dfs.append(df)
            except Exception as e:
                print(f"[{prov}] Error leyendo {fname}: {e}")
        if not dfs:
            continue
        df_prov = pd.concat(dfs, ignore_index=True)
        id_cols = [c for c in ["internal_id", "id", "url"] if c in df_prov.columns]
        if id_cols:
            df_prov = df_prov.drop_duplicates(subset=id_cols, keep="last")
        base = os.path.join(OUTPUT_DIR, f"{prov}_consolidado_{timestamp}")
        df_prov.to_pickle(f"{base}.pkl")
        df_prov.to_csv(f"{base}.csv", index=False, encoding="utf-8")
        print(f"[{prov}] {len(df_prov)} registros → {base}.csv")
        all_dfs.append(df_prov)

    if all_dfs:
        df_all = pd.concat(all_dfs, ignore_index=True)
        base = os.path.join(OUTPUT_DIR, f"todos_providers_consolidado_{timestamp}")
        df_all.to_pickle(f"{base}.pkl")
        df_all.to_csv(f"{base}.csv", index=False, encoding="utf-8")
        print(f"\n[TOTAL] {len(df_all)} registros → {base}.csv")
    else:
        print("No se encontraron PKLs para consolidar.")


if __name__ == "__main__":
    main()
