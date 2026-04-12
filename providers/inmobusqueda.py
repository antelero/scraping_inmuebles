from bs4 import BeautifulSoup
import logging
import re
from urllib.parse import quote_plus
from providers.base_provider import BaseProvider


class Inmobusqueda(BaseProvider):
    def __init__(self, provider_name, provider_data):
        super().__init__(provider_name, provider_data)
        self._geo_cache = {}
        self.resolve_detail_coordinates = bool(provider_data.get('resolve_detail_coordinates', False))

    # ------------------------------------------------------------------ helpers

    def _extract_features(self, card):
        """Devuelve (features_list, bedrooms, bathrooms, area_m2).

        Íconos en div.rdBox:
          img[src*='ic_room'] → dormitorios  (texto: "1 Dorm")
          img[src*='ic_sup']  → área          (texto: "24.00 mts")
        """
        features = []
        bedrooms = None
        bathrooms = None
        area_m2 = None

        for box in card.select('div.rdBox'):
            img = box.find('img', src=True)
            text = box.get_text(' ', strip=True)
            if not text:
                continue
            features.append(text)

            if img is None:
                continue
            src = img.get('src', '')

            if 'ic_room' in src:
                m = re.search(r'(\d+)', text)
                if m:
                    bedrooms = int(m.group(1))
            elif 'ic_sup' in src:
                m = re.search(r'(\d+(?:[\.,]\d+)?)', text)
                if m:
                    area_m2 = float(m.group(1).replace(',', '.'))
            elif 'ic_bath' in src or 'banio' in src or 'toilet' in src:
                m = re.search(r'(\d+)', text)
                if m:
                    bathrooms = int(m.group(1))

        return features, bedrooms, bathrooms, area_m2

    def _extract_coordinates_from_detail(self, detail_url):
        page_response = self.request(detail_url)
        if page_response.status_code != 200:
            return None, None
        html = page_response.text
        lat_m = re.search(r'"latitude"\s*:\s*(-?\d+\.\d+)', html, re.IGNORECASE)
        lon_m = re.search(r'"longitude"\s*:\s*(-?\d+\.\d+)', html, re.IGNORECASE)
        if lat_m and lon_m:
            return float(lat_m.group(1)), float(lon_m.group(1))
        at_m = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', html)
        if at_m:
            return float(at_m.group(1)), float(at_m.group(2))
        return None, None

    def _geocode_location(self, location_text):
        if not location_text:
            return None, None
        query = f"{location_text}, Argentina"
        if query in self._geo_cache:
            return self._geo_cache[query]
        url = (
            f"https://nominatim.openstreetmap.org/search"
            f"?q={quote_plus(query)}&format=json&limit=1"
        )
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

    # ---------------------------------------------------------------- scraping

    def props_in_source(self, source):
        base_url = self.provider_data['base_url']
        page_link = base_url + source
        page = 1

        while True:
            logging.info("Requesting %s", page_link)
            page_response = self.request(page_link)

            if page_response.status_code != 200:
                break

            page_content = BeautifulSoup(page_response.content, 'lxml')
            properties = page_content.find_all('div', class_='ResultadoCaja')

            for prop in properties:
                tipo_div = prop.find('div', class_='resultadoTipo')
                if tipo_div is None:
                    continue
                link = tipo_div.find('a')
                if link is None:
                    continue
                href = link.get('href', '')

                # Señal de fin de resultados en InmoBusqueda
                if len(properties) == 1 and href == '#':
                    return

                title = link.get_text(' ', strip=True)

                # Precio
                price_node = prop.find('div', class_='resultadoPrecio')
                if price_node:
                    title = f"{title} {price_node.get_text(' ', strip=True)}".strip()

                # Internal ID (ej. "IB-491699")
                codigo_node = prop.find('div', class_='codigo')
                internal_id = codigo_node.get_text(strip=True) if codigo_node else href.rstrip('/').split('/')[-1]

                # Localización
                loc_node = prop.find('div', class_='resultadoLocalidad')
                location = loc_node.get_text(' ', strip=True) if loc_node else ''

                # Features
                features, bedrooms, bathrooms, area_m2 = self._extract_features(prop)

                # Coordenadas
                lat, lon = None, None
                if self.resolve_detail_coordinates:
                    lat, lon = self._extract_coordinates_from_detail(href)
                if lat is None or lon is None:
                    lat, lon = self._geocode_location(location)

                yield {
                    'title': title,
                    'url': href,
                    'internal_id': internal_id,
                    'provider': self.provider_name,
                    'location': location,
                    'features': features,
                    'bedrooms': bedrooms,
                    'bathrooms': bathrooms,
                    'area_m2': area_m2,
                    'latitude': lat,
                    'longitude': lon,
                }

            page += 1
            page_link = base_url + source.replace(".html", f"-pagina-{page}.html")
