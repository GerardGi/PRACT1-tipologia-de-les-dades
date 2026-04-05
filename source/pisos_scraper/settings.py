"""Configuracio Scrapy optimitzada per pisos.com."""

BOT_NAME = "pisos_scraper"
SPIDER_MODULES = ["pisos_scraper.spiders"]
NEWSPIDER_MODULE = "pisos_scraper.spiders"

# pisos.com no te anti-bot — delays minims, concurrencia moderada
DOWNLOAD_DELAY = 0.5
RANDOMIZE_DOWNLOAD_DELAY = 1   # 0.5-1.5s efectiu
CONCURRENT_REQUESTS = 4
CONCURRENT_REQUESTS_PER_DOMAIN = 4
ROBOTSTXT_OBEY = False

# User-Agent fix (un sol agent realista, sense overhead de middleware)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# Sense middlewares custom — Scrapy gestiona delays i UA nativament
DOWNLOADER_MIDDLEWARES = {}

# Pipeline unic: escriptura CSV directa (la neteja es fa al spider)
ITEM_PIPELINES = {
    "pisos_scraper.pipelines.CsvPipeline": 300,
}

CSV_OUTPUT_DIR = "../../dataset"
CSV_FILENAME = "pisos_barcelona.csv"

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

RETRY_TIMES = 2
RETRY_HTTP_CODES = [500, 502, 503, 504, 429]

TELNETCONSOLE_ENABLED = False
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,ca;q=0.8,en;q=0.7",
}
