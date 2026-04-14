from bs4 import BeautifulSoup
import logging
import re
from urllib.parse import quote_plus
from providers.base_provider import BaseProvider


class Properati(BaseProvider):
    def __init__(self, provider_name, provider_data):
        super().__init__(provider_name, provider_data)
        self._geo_cache = {}
        self.resolve_detail_coordinates = bool(provider_data.get('resolve_detail_coordinates', False))

    def _extract_price(self, prop):
        price_node = prop.find(class_=re.compile(r'price', re.IGNORECASE))
        if price_node is not None:
            return price_node.get_text(" ", strip=True)
        text = prop.get_text(" ", strip=True)
        match = re.search(r'(USD|\$)\s?[\d\.,]+', text)
        return match.group(0) if match else ""

    def _extract_location(self, prop):
        location_node = prop.find(class_=re.compile(r'location', re.IGNORECASE))
        if location_node is not None:
            return location_node.get_text(" ", strip=True)
        text = prop.get_text(" ", strip=True)
        # Fallback simple: toma hasta dos segmentos separados por coma.
        match = re.search(r'([A-Za-zÁÉÍÓÚÑáéíóúñ/ ]+,\s*[A-Za-zÁÉÍÓÚÑáéíóúñ/ ]+)', text)
        return match.group(1).strip() if match else ""

    def _extract_features(self, prop):
        feature_nodes = prop.select('div.properties span')
        features = [node.get_text(' ', strip=True) for node in feature_nodes if node.get_text(strip=True)]

        bedrooms = None
        bathrooms = None
        area_m2 = None

        bedrooms_node = prop.select_one('span.properties__bedrooms')
        bathrooms_node = prop.select_one('span.properties__bathrooms')
        area_node = prop.select_one('span.properties__area')

        if bedrooms_node is not None:
            match = re.search(r'(\d+)', bedrooms_node.get_text(' ', strip=True))
            if match:
                bedrooms = int(match.group(1))

        if bathrooms_node is not None:
            match = re.search(r'(\d+(?:[\.,]\d+)?)', bathrooms_node.get_text(' ', strip=True))
            if match:
                bathrooms = float(match.group(1).replace(',', '.'))

        if area_node is not None:
            match = re.search(r'(\d+(?:[\.,]\d+)?)', area_node.get_text(' ', strip=True))
            if match:
                area_m2 = float(match.group(1).replace(',', '.'))

        return features, bedrooms, bathrooms, area_m2

    def _extract_coordinates_from_detail(self, detail_url):
        page_response = self.request(detail_url)
        if page_response.status_code != 200:
            return None, None

        html = page_response.text
        # Coordenadas en JSON embebido: "latitude": -34.x / "longitude": -58.x
        lat_match = re.search(r'"latitude"\s*:\s*(-?\d+\.\d+)', html, re.IGNORECASE)
        lon_match = re.search(r'"longitude"\s*:\s*(-?\d+\.\d+)', html, re.IGNORECASE)
        if lat_match and lon_match:
            return float(lat_match.group(1)), float(lon_match.group(1))

        # Coordenadas en links de mapa: @-34.x,-58.x
        at_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', html)
        if at_match:
            return float(at_match.group(1)), float(at_match.group(2))

        return None, None

    def _geocode_location(self, location_text):
        if not location_text:
            return None, None

        query = f"{location_text}, Argentina"
        if query in self._geo_cache:
            return self._geo_cache[query]

        url = f"https://nominatim.openstreetmap.org/search?q={quote_plus(query)}&format=json&limit=1"
        response = self.request(url)
        if response.status_code != 200:
            self._geo_cache[query] = (None, None)
            return None, None

        try:
            payload = response.json()
            if payload:
                lat = float(payload[0]["lat"])
                lon = float(payload[0]["lon"])
                self._geo_cache[query] = (lat, lon)
                return lat, lon
        except Exception:
            pass

        self._geo_cache[query] = (None, None)
        return None, None

    def props_in_source(self, source):
        page_link = self.provider_data['base_url'] + source

        while True:
            logging.info("Requesting %s" % page_link)
            page_response = self.request(page_link)

            if page_response.status_code != 200:
                logging.warning(
                    "Properati devolvio status %s para %s",
                    page_response.status_code,
                    page_link,
                )
                break

            page_content = BeautifulSoup(page_response.content, 'lxml')
            properties = page_content.find_all('article', class_='snippet')

            if len(properties) == 0:
                logging.warning(
                    "Properati no devolvio cards en %s",
                    page_link,
                )
                break

            for prop in properties:
                link = prop.find('a', class_='title', href=True)
                if link is None:
                    link = prop.find('a', href=True)
                if link is None:
                    continue

                href = link['href']
                title = link.get('title', '').strip() or link.get_text(strip=True)
                price = self._extract_price(prop)
                location = self._extract_location(prop)
                features, bedrooms, bathrooms, area_m2 = self._extract_features(prop)
                internal_id = prop.get('data-idanuncio')
                if not internal_id:
                    internal_id = href.rstrip('/').split('/')[-1]

                if price:
                    title = f"{title} {price}".strip()

                type_match = re.match(r'^(.+?) en (?:Venta|Alquiler)', title, re.IGNORECASE)
                property_type = type_match.group(1).strip().lower() if type_match else ''

                lat, lon = (None, None)
                if self.resolve_detail_coordinates:
                    lat, lon = self._extract_coordinates_from_detail(href)
                if lat is None or lon is None:
                    lat, lon = self._geocode_location(location)

                yield {
                    'title': title,
                    'url': href,
                    'internal_id': internal_id,
                    'provider': self.provider_name,
                    'property_type': property_type,
                    'location': location,
                    'features': features,
                    'bedrooms': bedrooms,
                    'bathrooms': bathrooms,
                    'area_m2': area_m2,
                    'latitude': lat,
                    'longitude': lon,
                }

            next_link = page_content.select_one('a.next, a[rel="next"], a.pagination__link[aria-label="Siguiente"]')
            if next_link is None:
                for candidate in page_content.select('a.pagination__link[href]'):
                    label = candidate.get_text(' ', strip=True).lower()
                    if label in ('siguiente', 'next'):
                        next_link = candidate
                        break
            if next_link is None or not next_link.get('href'):
                break

            href = next_link['href']
            if href.startswith('http'):
                page_link = href
            else:
                page_link = self.provider_data['base_url'] + href
