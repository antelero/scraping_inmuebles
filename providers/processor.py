import logging
import sqlite3
from providers.zonaprop import Zonaprop
from providers.argenprop import Argenprop
from providers.mercadolibre import Mercadolibre
from providers.properati import Properati
from providers.inmobusqueda import Inmobusqueda


def ensure_properties_table(conn):
    stmt = '''
    CREATE TABLE IF NOT EXISTS properties (
        internal_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        url TEXT,
        location TEXT,
        latitude REAL,
        longitude REAL,
        PRIMARY KEY (internal_id, provider)
    )
    '''
    conn.execute(stmt)

    # Migra tablas existentes creadas con versiones anteriores.
    required_columns = {
        'location': 'TEXT',
        'latitude': 'REAL',
        'longitude': 'REAL',
    }
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(properties)")
    existing_columns = {row[1] for row in cur.fetchall()}
    cur.close()

    for column_name, column_type in required_columns.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE properties ADD COLUMN {column_name} {column_type}")


def register_property(conn, prop):
    stmt = '''
    INSERT INTO properties (
        internal_id,
        provider,
        url,
        location,
        latitude,
        longitude
    ) VALUES (
        :internal_id,
        :provider,
        :url,
        :location,
        :latitude,
        :longitude
    )
    '''
    try:
        conn.execute(stmt, prop)
    except Exception as e:
        print(e)

def process_properties(provider_name, provider_data, include_all=False):
    provider = get_instance(provider_name, provider_data)

    new_properties = []
    all_properties = []
    processed = 0

    # db connection
    conn = sqlite3.connect('properties.db')
    ensure_properties_table(conn)

    # Check to see if we know it
    stmt = 'SELECT * FROM properties WHERE internal_id=:internal_id AND provider=:provider'

    with conn:
        for prop in provider.next_prop():
            processed += 1
            if include_all:
                all_properties.append(prop)
            cur = conn.cursor()
            logging.info(f"Processing property {prop['internal_id']}")
            cur.execute(stmt, {'internal_id': prop['internal_id'], 'provider': prop['provider']})
            result = cur.fetchone()
            cur.close()
            if result == None:
                # Insert and save for notification
                logging.info('It is a new one')
                register_property(conn, prop)
                new_properties.append(prop)

            if processed % 100 == 0:
                logging.info(
                    "Progreso %s: procesadas=%s | nuevas=%s",
                    provider_name,
                    processed,
                    len(new_properties),
                )

    if include_all:
        return new_properties, all_properties

    return new_properties

def get_instance(provider_name, provider_data):
    if provider_name == 'zonaprop':
        return Zonaprop(provider_name, provider_data)
    elif provider_name == 'argenprop':
        return Argenprop(provider_name, provider_data)
    elif provider_name == 'mercadolibre':
        return Mercadolibre(provider_name, provider_data)
    elif provider_name == 'properati':
        return Properati(provider_name, provider_data)
    elif provider_name == 'inmobusqueda':
        return Inmobusqueda(provider_name, provider_data)
    else:
        raise Exception('Unrecognized provider')
