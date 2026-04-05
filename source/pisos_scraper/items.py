"""
Definicio de l'estructura de dades (Item) per al scraper de pisos.com.

Cada PropertyItem representa un anunci immobiliari amb 34 camps que
cobreixen informacio basica (preu, superficie, habitacions), ubicacio
(coordenades GPS, barri, districte), caracteristiques de l'immoble
(ascensor, terrassa, certificat energetic) i metadades del scraping.

Els camps es divideixen en dos grups:
- Camps del llistat: s'omplen sempre (mode rapid i mode detall)
- Camps de detall: nomes s'omplen en mode --with-details
"""

import scrapy


class PropertyItem(scrapy.Item):
    """Item que representa un anunci immobiliari de pisos.com."""

    # --- Identificacio ---
    listing_id = scrapy.Field()          # ID unic de l'anunci a pisos.com
    url = scrapy.Field()                 # URL completa de la fitxa de detall

    # --- Informacio basica (del llistat) ---
    title = scrapy.Field()               # Titol complet de l'anunci
    property_type = scrapy.Field()       # Piso, Atico, Casa, Duplex, Chalet...
    operation = scrapy.Field()           # Sempre "venta"
    price_eur = scrapy.Field()           # Preu en EUR (float)
    price_per_m2 = scrapy.Field()        # EUR/m2 (del llistat o calculat)
    area_m2 = scrapy.Field()             # Superficie en m2 (float)
    rooms = scrapy.Field()               # Nombre d'habitacions (int)
    bathrooms = scrapy.Field()           # Nombre de banys (int)
    floor = scrapy.Field()               # Planta (text: "3a planta", "Bajo")

    # --- Caracteristiques booleanes (nomes en mode detall) ---
    has_elevator = scrapy.Field()
    has_terrace = scrapy.Field()
    has_balcony = scrapy.Field()
    has_parking = scrapy.Field()
    has_air_conditioning = scrapy.Field()
    has_swimming_pool = scrapy.Field()
    has_garden = scrapy.Field()

    # --- Ubicacio (del llistat + JSON-LD) ---
    district = scrapy.Field()            # Districte (si aplica)
    neighborhood = scrapy.Field()        # Barri
    full_address = scrapy.Field()        # Adreca completa tal com apareix
    locality = scrapy.Field()            # Municipi (del JSON-LD)
    latitude = scrapy.Field()            # Coordenada GPS (float, del JSON-LD)
    longitude = scrapy.Field()           # Coordenada GPS (float, del JSON-LD)

    # --- Descripcio ---
    description = scrapy.Field()         # Text descriptiu (max 500 chars)

    # --- Detalls addicionals (nomes en mode detall) ---
    energy_cert = scrapy.Field()         # Certificat energetic: A-G
    construction_year = scrapy.Field()   # Any de construccio o antiguitat
    condition = scrapy.Field()           # Estat de conservacio

    # --- Anunciant ---
    advertiser_name = scrapy.Field()     # Nom de l'agencia o "Particular"
    advertiser_type = scrapy.Field()     # "Agencia" o "Particular"

    # --- Metadades del llistat ---
    photo_count = scrapy.Field()         # Nombre de fotos de l'anunci
    is_new_development = scrapy.Field()  # True si es obra nova

    # --- Metadades del scraping ---
    scrape_date = scrapy.Field()         # Data d'extraccio (YYYY-MM-DD)
    scrape_timestamp = scrapy.Field()    # Timestamp complet ISO
