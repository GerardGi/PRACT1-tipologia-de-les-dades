#!/usr/bin/env python
"""
Scraper de pisos.com.

Exemples:
    # Barcelona ciutat
    poetry run python source/run_scraper.py

    # Tota Catalunya
    poetry run python source/run_scraper.py --location catalunya

    # Amb filtres
    poetry run python source/run_scraper.py --location catalunya --min-price 100000 --max-price 300000

    # Amb detalls complets (mes lent)
    poetry run python source/run_scraper.py --location barcelona_capital --with-details

    # Limitar a 100 anuncis
    poetry run python source/run_scraper.py --location girona --max-items 100
"""

import argparse
import logging
import os
import sys
from datetime import datetime

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


def main():
    p = argparse.ArgumentParser(
        description="Scraper de pisos.com",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Presets d'ubicacio:
  catalunya                Barcelona + Girona + Tarragona + Lleida
  pais_valencia            Valencia + Alicante + Castellon
  espanya                  Totes les provincies principals

Ubicacions individuals:
  barcelona_capital, barcelona, girona, madrid, hospitalet_de_llobregat...

Combinables amb comes: barcelona_capital,girona,tarragona
""",
    )
    p.add_argument("--location", default="barcelona_capital",
                   help="Ubicacio, preset o llista separada per comes")
    p.add_argument("--max-pages", type=int, default=0,
                   help="Max pagines per ubicacio (0=totes, default: 0)")
    p.add_argument("--max-items", type=int, default=0,
                   help="Limit total d'anuncis (0=sense limit, default: 0)")
    p.add_argument("--with-details", action="store_true",
                   help="Visitar fitxa de detall per camps extra")
    p.add_argument("--min-price", type=float, help="Preu minim (EUR)")
    p.add_argument("--max-price", type=float, help="Preu maxim (EUR)")
    p.add_argument("--min-area", type=float, help="Superficie minima (m2)")
    p.add_argument("--min-rooms", type=int, help="Habitacions minimes")
    p.add_argument("--output", help="Path del CSV (default: auto amb timestamp)")
    args = p.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    settings = get_project_settings()

    # Nom del CSV: pisos_{location}_{YYYYMMDD}_{HHMMSS}.csv
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    loc_slug = args.location.replace(",", "_")

    if args.output:
        settings.set("CSV_OUTPUT_DIR", os.path.dirname(os.path.abspath(args.output)))
        settings.set("CSV_FILENAME", os.path.basename(args.output))
    else:
        settings.set("CSV_FILENAME", f"pisos_{loc_slug}_{ts}.csv")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    log = logging.getLogger("run_scraper")
    log.info("=" * 50)
    log.info("Scraper pisos.com")
    log.info(f"  Ubicacio:  {args.location}")
    log.info(f"  Mode:      {'detall' if args.with_details else 'rapid'}")
    log.info(f"  Max pag:   {'sense limit' if args.max_pages == 0 else args.max_pages}")
    log.info(f"  Max items: {'sense limit' if args.max_items == 0 else args.max_items}")
    log.info(f"  CSV:       {settings.get('CSV_FILENAME')}")
    log.info("=" * 50)

    kw = {
        "location": args.location,
        "max_pages": args.max_pages,
        "max_items": args.max_items,
        "with_details": "true" if args.with_details else "false",
    }
    if args.min_price: kw["min_price"] = args.min_price
    if args.max_price: kw["max_price"] = args.max_price
    if args.min_area: kw["min_area"] = args.min_area
    if args.min_rooms: kw["min_rooms"] = args.min_rooms

    process = CrawlerProcess(settings)
    try:
        process.crawl("pisos", **kw)
        process.start()
    except KeyboardInterrupt:
        log.info("Aturat.")
        sys.exit(0)


if __name__ == "__main__":
    main()
