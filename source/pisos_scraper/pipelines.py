"""
Pipeline d'escriptura CSV per al scraper de pisos.com.

Escriu els items al fitxer CSV incrementalment amb delimitador ';'
(per evitar conflictes amb comes dins dels camps de text lliure)
i encoding UTF-8 amb BOM (per compatibilitat amb Excel).

La neteja de dades es fa al spider (funcions to_float, to_int, clean),
no al pipeline, per minimitzar el processament redundant.
"""

import csv
import logging
import os

logger = logging.getLogger(__name__)

# Ordre dels camps al CSV final
CSV_FIELDS = [
    "listing_id", "title", "property_type", "operation",
    "price_eur", "price_per_m2", "area_m2", "rooms", "bathrooms",
    "floor", "has_elevator", "district", "neighborhood", "full_address",
    "locality", "latitude", "longitude",
    "description", "has_terrace", "has_balcony", "has_parking",
    "has_air_conditioning", "has_swimming_pool", "has_garden",
    "energy_cert", "construction_year", "condition",
    "advertiser_name", "advertiser_type",
    "photo_count", "is_new_development",
    "url", "scrape_date", "scrape_timestamp",
]


class CsvPipeline:
    """Escriu items al CSV amb flush periodic cada 50 items."""

    def __init__(self):
        self.file = None
        self.writer = None
        self.count = 0

    @classmethod
    def from_crawler(cls, crawler):
        """Inicialitza el pipeline amb acces als settings de Scrapy."""
        p = cls()
        p.settings = crawler.settings
        return p

    def open_spider(self):
        """Obre el fitxer CSV i escriu la capcelera."""
        output_dir = self.settings.get("CSV_OUTPUT_DIR", "../../dataset")
        filename = self.settings.get("CSV_FILENAME", "pisos_barcelona.csv")
        base = os.path.dirname(os.path.abspath(__file__))
        full_dir = os.path.normpath(os.path.join(base, output_dir))
        os.makedirs(full_dir, exist_ok=True)
        self.filepath = os.path.join(full_dir, filename)
        self.file = open(self.filepath, "w", newline="", encoding="utf-8-sig")
        self.writer = csv.DictWriter(
            self.file, fieldnames=CSV_FIELDS, extrasaction="ignore", delimiter=";"
        )
        self.writer.writeheader()
        logger.info(f"CSV: {self.filepath}")

    def process_item(self, item):
        """Escriu un item al CSV, convertint booleans a text."""
        self.writer.writerow({
            f: ("" if item.get(f) is None else
                str(item[f]) if isinstance(item[f], bool) else
                item[f])
            for f in CSV_FIELDS
        })
        self.count += 1
        # Flush periodic per no perdre dades si s'interromp el proces
        if self.count % 50 == 0:
            self.file.flush()
            logger.info(f"[CSV] {self.count} escrits")
        return item

    def close_spider(self):
        """Tanca el fitxer CSV i mostra el resum."""
        if self.file:
            self.file.flush()
            self.file.close()
        logger.info(f"[CSV] Completat: {self.count} anuncis -> {self.filepath}")
