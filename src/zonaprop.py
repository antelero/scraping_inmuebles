import pandas as pd
import numpy as np
from botasaurus import *
import time
import re
import requests
from urllib.parse import quote_plus
from sqlalchemy import create_engine, exc
from typing import Literal
from datetime import datetime
from sqlalchemy import create_engine
from src.constants import (
    zona_prop_url,
    max_number_pages_zonaprop,
    default_locality_slug_zonaprop,
    ZONAPROP_RESOLVE_DETAIL_COORDINATES,
)

_GEO_CACHE = {}


def _extract_coordinates_from_detail(detail_url: str) -> tuple[float | None, float | None]:
    try:
        response = requests.get(
            detail_url,
            timeout=20,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        )
        if response.status_code != 200:
            return None, None
        html = response.text
        lat_match = re.search(r'"latitude"\s*:\s*(-?\d+\.\d+)', html, re.IGNORECASE)
        lon_match = re.search(r'"longitude"\s*:\s*(-?\d+\.\d+)', html, re.IGNORECASE)
        if lat_match and lon_match:
            return float(lat_match.group(1)), float(lon_match.group(1))

        at_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', html)
        if at_match:
            return float(at_match.group(1)), float(at_match.group(2))
    except Exception:
        return None, None

    return None, None


def _geocode_location(location_text: str) -> tuple[float | None, float | None]:
    if not location_text:
        return None, None

    query = f"{location_text}, Argentina"
    if query in _GEO_CACHE:
        return _GEO_CACHE[query]

    try:
        url = (
            "https://nominatim.openstreetmap.org/search"
            f"?q={quote_plus(query)}&format=json&limit=1"
        )
        response = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "scraping-inmuebles/1.0"},
        )
        if response.status_code != 200:
            _GEO_CACHE[query] = (None, None)
            return None, None
        payload = response.json()
        if payload:
            lat = float(payload[0]["lat"])
            lon = float(payload[0]["lon"])
            _GEO_CACHE[query] = (lat, lon)
            return lat, lon
    except Exception:
        pass

    _GEO_CACHE[query] = (None, None)
    return None, None

def _get_page_number_url(number:int, type_building:str, type_operation:str, locality_slug:str) -> str:
    url = zona_prop_url + type_building + f"-{type_operation}-{locality_slug}-pagina-{number}.html"
    return url

def _get_url_list(max_number:int, type_building:str, type_operation:str, locality_slug:str) -> list[str]:
    request = AntiDetectRequests()
    response = request.get(
        _get_page_number_url(max_number, type_building, type_operation, locality_slug),
        allow_redirects=True,
    )
    last_page_url = response.url
    match = re.search(r'(\d+)\.html$', last_page_url)
    if match:
        last_page_number = (match.group(1))
        page_list = [
            _get_page_number_url(i, type_building, type_operation, locality_slug)
            for i in range(1, int(last_page_number) + 1)
        ]
        return page_list
    else:
        print("Could not find last webpage, try again in a few minutes")

def _parse_property_listings(soup, posting_container_class:str) -> list:
    """Parses property listings from a BeautifulSoup object.

    Args:
        soup (BeautifulSoup): A BeautifulSoup object containing the HTML content.

    Returns:
        list: A list of dictionaries, each representing a property listing.
    """
    property_elements = soup.find_all(class_ = posting_container_class) #this should be a list with each posting_container class element
    properties = []
    # print("Propiedad dentro de _parse", property_elements)
    for property_element in property_elements:
        try:
            properties.append(_parse_property(property_element))
            # print("Se appendio la propiedad", properties)
            if len(properties == 0):
                print("be aware of the div selected in the soup, it usually changes.") #this should already be solved
                break
        except Exception:
            #There are 'Developing' buildings with a range of prices. 
            pass
    # print("Propiedades final de _parse", properties)
    return properties

def _parse_property(property_element, resolve_detail_coordinates: bool = False) -> dict:
    """Parses an individual property from the property element.

    Args:
        property_element (Tag): A BeautifulSoup Tag representing a property element.

    Returns:
        dict: A dictionary containing property details.
    """
    # print(property_element)
    id_element = property_element.find(attrs={"data-id": True})['data-id']
    price_element = property_element.find(attrs={"data-qa":"POSTING_CARD_PRICE"}).text
    location_element = property_element.find(attrs={'data-qa': 'POSTING_CARD_LOCATION'}).text
    address_element = property_element.find(class_='postingLocations-module__location-address').text
    features_elements = [span.text for span in property_element.find(attrs={'data-qa': 'POSTING_CARD_FEATURES'}).find_all('span')]
    description_element = property_element.find(attrs={'data-qa': 'POSTING_CARD_DESCRIPTION'}).text
    expensas_element = property_element.find(attrs={'data-qa': 'expensas'}).text
    ap_link_element = property_element.find(attrs={"data-to-posting": True})['data-to-posting']
    full_url = zona_prop_url[:-1] + ap_link_element if ap_link_element else np.nan

    lat, lon = (None, None)
    if isinstance(full_url, str):
        if resolve_detail_coordinates:
            lat, lon = _extract_coordinates_from_detail(full_url)
        if lat is None or lon is None:
            lat, lon = _geocode_location(location_element or address_element)
    # print("price_element", price_element)
    data = {
        'id': id_element if id_element else np.nan,
        'Price': price_element if price_element else np.nan,
        'Location': location_element if location_element else np.nan,
        'Address': address_element if address_element else np.nan,
        # 'Has_photo': has_photo,
        'Features': [feature_element for feature_element in features_elements],
        # 'Summarize': summarize_element if summarize_element else np.nan,
        'Description': description_element if description_element else np.nan,
        'Expensas': expensas_element if expensas_element else np.nan,
        'Link': full_url,
        'latitude': lat,
        'longitude': lon,
    }
    
    # print(data)
    
    return data

def _get_posting_container_class(soup):
    posting_containers = soup.find_all(class_=lambda c: c and "postings-container" in c)
    if len(posting_containers) == 0:
        raise ValueError("No postings-container found in the soup.")
    # If more than one, use the second; otherwise, use the first
    posting_container = posting_containers[1] if len(posting_containers) > 1 else posting_containers[0]
    classes_inside_posting_container = []
    for child in posting_container.children:
        if child.name and child.get('class'):
            classes_inside_posting_container.extend(child['class'])
    return classes_inside_posting_container[0]
    
def _scrape_property_listings(request: AntiDetectRequests, 
                              url_list: list[str],
                              resolve_detail_coordinates: bool = False,
                              ) -> list:
    """Scrapes property listings from ZonaProp.

    Args:
        request (AntiDetectRequests): An instance of AntiDetectRequests.
        link (str): The URL of the property listings page.

    Returns:
        list: A list of dictionaries, each representing a property listing.
    """
    properties = []
    itereation_count = 0
    for link in url_list:
        itereation_count += 1
        print(link)
        try:
            soup = request.bs4(link)
            if itereation_count == 1:
                with open("soup.html", "w", encoding="utf-8") as f:
                    f.write(str(soup))
            posting_container_class = _get_posting_container_class(soup)
            # Pasamos la bandera de coordenadas al parser de cada propiedad.
            page_properties = []
            property_elements = soup.find_all(class_=posting_container_class)
            for property_element in property_elements:
                try:
                    page_properties.append(
                        _parse_property(
                            property_element,
                            resolve_detail_coordinates=resolve_detail_coordinates,
                        )
                    )
                except Exception:
                    pass
            properties += page_properties
            if itereation_count == 1:
                print("Test of properties:\n", properties)
        except requests.exceptions.HTTPError as e:
            print(f"HTTPError occurred: {e}. Retrying in 15 minutes.")
            time.sleep(15*60) # Sleep for 15 minutes
        except Exception as e:
            print(f"An unknown error occurred: {e}.")
            break
    return properties

def _export_scrap_zonaprop(df: pd.DataFrame, type_building, type_operation):
    df.to_pickle(
        f"./output/zonaprop_{type_operation}_{type_building}_{datetime.now().strftime('%Y_%m_%d')}.pkl"
    )

def main_scrap_zonaprop(
    type_operation: Literal["alquiler", "venta"] = "alquiler", 
    type_building:Literal["locales-comerciales", "departamentos","oficinas-comerciales"] = "departamentos",
    locality_slug: str = default_locality_slug_zonaprop,
    export_final_results:bool = True,
    resolve_detail_coordinates: bool = ZONAPROP_RESOLVE_DETAIL_COORDINATES,
    db_file: str = 'zonaprop.db'
                        ) -> list:
    """Runs the main process of scraping property listings from ZonaProp.

    Returns:
        list: A list of dictionaries, each representing a property listing.
    """
    url_list =  _get_url_list(max_number_pages_zonaprop, type_building, type_operation, locality_slug)
    print("Max html page:", url_list[-1])
    try:
        request = AntiDetectRequests()
        final_list = _scrape_property_listings(
            request,
            url_list,
            resolve_detail_coordinates=resolve_detail_coordinates,
        )
        
        if export_final_results:
            df = pd.DataFrame(final_list)
            df["scrap_date"] = datetime.now()
            df["type_building"] = type_building
            df["type_operation"] = type_operation
            df = df.drop_duplicates(subset="id")  # Evitar duplicados por id
            print(df)
            _export_scrap_zonaprop(df, type_building, type_operation)
            print("Resultados exportados correctamente.")
        return final_list
    except Exception as e:
        print(f"Ha ocurrido un error: {e}")