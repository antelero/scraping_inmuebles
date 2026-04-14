from bs4 import BeautifulSoup
import logging
import re
from urllib.parse import quote_plus
from providers.base_provider import BaseProvider


class Argenprop(BaseProvider):
    def __init__(self, provider_name, provider_data):
        super().__init__(provider_name, provider_data)
        self._geo_cache = {}
        self.max_pages = provider_data.get('max_pages')
        self.resolve_detail_coordinates = bool(provider_data.get('resolve_detail_coordinates', False))

    # ------------------------------------------------------------------ helpers

    def _extract_features(self, card):
        """Devuelve (features_list, bedrooms, bathrooms, area_m2).

        Los íconos conocidos en ul.card__main-features:
          basico1-icon-superficie_cubierta  → area en m²
          basico1-icon-cantidad_dormitorios → dormitorios
          basico1-icon-cantidad_ambientes   → ambientes (no se mapea a bedrooms)
        """
        feat_ul = card.find('ul', class_='card__main-features')
        if feat_ul is None:
            return [], None, None, None

        features = []
        bedrooms = None
        bathrooms = None
        area_m2 = None

        for li in feat_ul.find_all('li'):
            icon = li.find('i')
            span = li.find('span')
            text = span.get_text(' ', strip=True) if span else li.get_text(' ', strip=True)
            if not text:
                continue
            features.append(text)

            if icon is None:
                continue
            icon_classes = ' '.join(icon.get('class', []))

            if 'superficie_cubierta' in icon_classes or 'superficie_total' in icon_classes:
                m = re.search(r'(\d+(?:[\.,]\d+)?)', text)
                if m:
                    area_m2 = float(m.group(1).replace(',', '.'))
            elif 'cantidad_dormitorios' in icon_classes:
                m = re.search(r'(\d+)', text)
                if m:
                    bedrooms = int(m.group(1))
            elif 'banio' in icon_classes or 'bano' in icon_classes or 'toilet' in icon_classes:
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
        page = 1

        while True:
            if self.max_pages is not None and page > self.max_pages:
                break

            # Página 1 usa la URL base; páginas siguientes agregan /pagina-N.
            if page == 1:
                page_link = base_url + source
            else:
                page_link = base_url + source + f"/pagina-{page}"

            logging.info("Requesting %s", page_link)
            page_response = self.request(page_link)

            if page_response.status_code != 200:
                break

            page_content = BeautifulSoup(page_response.content, 'lxml')
            properties = page_content.find_all('div', class_='listing__item')

            if not properties:
                break

            for prop in properties:
                card_link = prop.find('a', class_='card')
                if card_link is None:
                    continue
                href = card_link.get('href', '')
                internal_id = prop.get('id') or card_link.get('idaviso', '')

                # Título: preferir card__title--primary, fallback h2.card__title
                title_node = prop.find('p', class_='card__title--primary')
                if title_node is None:
                    title_node = prop.find(class_=re.compile(r'card__title'))
                title = title_node.get_text(' ', strip=True) if title_node else ''

                # Dirección usada como location para geocoding
                addr_node = prop.find('p', class_='card__address')
                address = addr_node.get_text(' ', strip=True) if addr_node else ''
                location = address or title

                # Precio
                price_node = prop.find('p', class_='card__price')
                if price_node:
                    price = price_node.get_text(' ', strip=True)
                    title = f"{title} {price}".strip()

                # Features
                features, bedrooms, bathrooms, area_m2 = self._extract_features(prop)

                # URL absoluta
                full_url = href if href.startswith('http') else base_url + href

                type_match = re.match(r'^/([\w-]+?)-en-(?:venta|alquiler)-en-', href)
                property_type = type_match.group(1).lower() if type_match else ''

                # Coordenadas
                lat, lon = None, None
                if self.resolve_detail_coordinates:
                    lat, lon = self._extract_coordinates_from_detail(full_url)
                if lat is None or lon is None:
                    lat, lon = self._geocode_location(location)

                yield {
                    'title': title,
                    'url': full_url,
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

            page += 1
