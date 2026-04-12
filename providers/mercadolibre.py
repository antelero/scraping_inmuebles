from bs4 import BeautifulSoup
import cloudscraper
import logging
import re
from urllib.parse import quote_plus
from providers.base_provider import BaseProvider


class Mercadolibre(BaseProvider):
    # MercadoLibre requiere un User-Agent de escritorio; el UA móvil que usa
    # cloudscraper por defecto provoca redirección a verificación de cuenta.
    _BROWSER_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, provider_name, provider_data):
        super().__init__(provider_name, provider_data)
        self._geo_cache = {}
        self.resolve_detail_coordinates = bool(provider_data.get('resolve_detail_coordinates', False))
        # Scraper propio con UA de escritorio para evitar el redirect de ML.
        self._scraper = cloudscraper.create_scraper()
        self._scraper.headers.update({
            'User-Agent': self._BROWSER_UA,
            'Accept-Language': 'es-AR,es;q=0.9',
        })

    def request(self, url):
        return self._scraper.get(url)

    # ------------------------------------------------------------------ helpers

    def _extract_features(self, card):
        """Devuelve (features_list, bedrooms, bathrooms, area_m2)."""
        items = card.select('li.poly-attributes_list__item')
        features = [li.get_text(strip=True) for li in items if li.get_text(strip=True)]

        bedrooms = None
        bathrooms = None
        area_m2 = None

        for text in features:
            t = text.lower()
            if 'dorm' in t:
                m = re.search(r'(\d+)', text)
                if m:
                    bedrooms = int(m.group(1))
            elif 'baño' in t or 'bano' in t:
                m = re.search(r'(\d+)', text)
                if m:
                    bathrooms = int(m.group(1))
            elif 'm²' in text or 'm2' in t:
                m = re.search(r'(\d+(?:[\.,]\d+)?)', text)
                if m:
                    area_m2 = float(m.group(1).replace(',', '.'))

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
        # None = primera página sin offset; luego 49, 97, 145…
        from_ = None

        while True:
            if from_ is None:
                page_link = base_url + source
            else:
                page_link = base_url + source + f"_Desde_{from_}_NoIndex_True"

            logging.info("Requesting %s", page_link)
            page_response = self.request(page_link)

            if 'account-verification' in page_response.url:
                logging.warning(
                    "MercadoLibre activo verificacion de cuenta en %s. Se corta paginacion para evitar datos incompletos.",
                    page_link,
                )
                break

            if page_response.status_code != 200:
                logging.warning(
                    "MercadoLibre devolvio status %s para %s",
                    page_response.status_code, page_link,
                )
                break

            page_content = BeautifulSoup(page_response.content, 'lxml')
            properties = page_content.find_all('li', class_='ui-search-layout__item')

            if not properties:
                logging.warning("MercadoLibre no devolvio cards en %s", page_link)
                break

            for prop in properties:
                title_link = prop.find('a', class_='poly-component__title')
                if title_link is None:
                    continue

                href = title_link.get('href', '')
                title = title_link.get_text(strip=True)

                matches = re.search(r'(MLA-\d+)', href)
                if matches is None:
                    continue
                internal_id = matches.group(1).replace('-', '')

                # Precio
                currency_node = prop.find('span', class_='andes-money-amount__currency-symbol')
                fraction_node = prop.find('span', class_='andes-money-amount__fraction')
                if currency_node and fraction_node:
                    price = f"{currency_node.get_text(strip=True)}{fraction_node.get_text(strip=True)}"
                elif fraction_node:
                    price = fraction_node.get_text(strip=True)
                else:
                    price = ''
                if price:
                    title = f"{title} {price}".strip()

                # Localización
                location_node = prop.find('span', class_='poly-component__location')
                location = location_node.get_text(' ', strip=True) if location_node else ''

                # Features
                features, bedrooms, bathrooms, area_m2 = self._extract_features(prop)

                # Coordenadas
                lat, lon = None, None
                # Primero geocoding por ubicación para minimizar requests al detalle
                # y reducir el riesgo de bloqueo anti-bot.
                lat, lon = self._geocode_location(location)
                if (lat is None or lon is None) and self.resolve_detail_coordinates:
                    lat, lon = self._extract_coordinates_from_detail(href)

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

            # Avanzar paginación: primera vez offset = n_cards + 1 (ej. 49),
            # luego += n_cards (49 → 97 → 145…)
            if from_ is None:
                from_ = len(properties) + 1
            else:
                from_ += len(properties)
    