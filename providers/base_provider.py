import logging
import cloudscraper
from abc import ABC, abstractmethod
import os
import requests
from requests.exceptions import SSLError
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from urllib.parse import urlparse
import yaml

# configuration
try:
    with open("configuration.yml", "r") as ymlfile:
        print("loading config")
        cfg = yaml.safe_load(ymlfile) or {}
except FileNotFoundError:
    logging.warning("configuration.yml no encontrado, se usara configuracion por defecto.")
    cfg = {}

disable_ssl = False
allow_insecure_ssl_fallback = True
suppress_insecure_request_warning = True
log_insecure_ssl_every_request = False

if 'disable_ssl' in cfg:
    disable_ssl = cfg['disable_ssl']
if 'allow_insecure_ssl_fallback' in cfg:
    allow_insecure_ssl_fallback = cfg['allow_insecure_ssl_fallback']
if 'suppress_insecure_request_warning' in cfg:
    suppress_insecure_request_warning = cfg['suppress_insecure_request_warning']
if 'log_insecure_ssl_every_request' in cfg:
    log_insecure_ssl_every_request = cfg['log_insecure_ssl_every_request']

if suppress_insecure_request_warning and (disable_ssl or allow_insecure_ssl_fallback):
    urllib3.disable_warnings(InsecureRequestWarning)

HostNameIgnoringAdapter = None
if disable_ssl:
    try:
        from lib.hostname_ignoring_adapter import HostNameIgnoringAdapter
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "disable_ssl=true requiere lib/hostname_ignoring_adapter.py, pero no existe en este proyecto."
        ) from exc


class BaseProvider(ABC):
    _warned_insecure_hosts = set()

    def __init__(self, provider_name, provider_data):
        self.provider_name = provider_name
        self.provider_data = provider_data
        self.__scraper = cloudscraper.create_scraper()
        self._insecure_session = requests.Session()
        self._insecure_session.headers.update(self.__scraper.headers)
        if disable_ssl and HostNameIgnoringAdapter is not None:
            self.__scraper.mount('https://', HostNameIgnoringAdapter())
    
    @abstractmethod
    def props_in_source(self, source):
        pass

    def _insecure_request(self, url):
        return self._insecure_session.get(url, verify=False)

    def _log_ssl_warning(self, url, message):
        if log_insecure_ssl_every_request:
            logging.warning(message, url)
            return

        host = urlparse(url).netloc or url
        warning_key = (self.provider_name, host)
        if warning_key in BaseProvider._warned_insecure_hosts:
            return

        BaseProvider._warned_insecure_hosts.add(warning_key)
        logging.warning(message + " [solo una vez por host/proveedor]", url)

    def request(self, url):
        verify = not disable_ssl
        if verify:
            cert_bundle = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")
            if cert_bundle:
                verify = cert_bundle

        if verify is False:
            self._log_ssl_warning(
                url,
                "Request HTTPS sin verificacion SSL para %s (disable_ssl=true).",
            )
            return self._insecure_request(url)

        try:
            return self.__scraper.get(url, verify=verify)
        except SSLError as exc:
            cert_error = "CERTIFICATE_VERIFY_FAILED" in str(exc)
            if verify and allow_insecure_ssl_fallback and cert_error:
                self._log_ssl_warning(
                    url,
                    "Fallo validacion SSL para %s. Reintentando con verify=False "
                    "(allow_insecure_ssl_fallback=true).",
                )
                return self._insecure_request(url)
            raise

    def next_prop(self):
        for source in self.provider_data['sources']:
            logging.info(f'Processing source {source}')
            yield from self.props_in_source(source)