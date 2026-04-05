"""
Spider optimitzat per a pisos.com — portal immobiliari espanyol.

Implementa dos modes d'extraccio:
- Mode rapid (per defecte): extreu dades de les cards del llistat sense
  visitar les pagines de detall. Rendiment: ~30 anuncis per request HTTP.
- Mode detall (--with-details): a mes, visita cada fitxa individual per
  obtenir camps addicionals (ascensor, terrassa, certificat energetic, etc.)

Suporta multiples ubicacions en una sola execucio mitjancant presets
(e.g. 'catalunya' = Barcelona + Girona + Tarragona + Lleida) o llistes
separades per comes (e.g. 'barcelona_capital,girona').

Les dades s'extreuen de:
- Selectors CSS de les cards del llistat (preu, habs, m2, ubicacio)
- JSON-LD embegut a cada card (coordenades GPS, localitat, tipus)
- Atributs data-* dels elements HTML (preu numeric, fotos, obra nova)
- Pagines de detall (en mode --with-details): features, certificat energetic
"""

import html
import json
import logging
import re
from datetime import date, datetime

import scrapy
from pisos_scraper.items import PropertyItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex precompilats a nivell de modul per evitar recompilacio per cada item
# ---------------------------------------------------------------------------
RE_DIGITS = re.compile(r"\d+")
RE_FLOAT = re.compile(r"[\d,.]+")
RE_MILERS = re.compile(r"^\d{1,3}(\.\d{3})+$")  # detecta "4.487" (format milers ES)
RE_LOCATION = re.compile(r"^(.+?)\s*\((?:Distrito\s+)?(.+?)(?:\.\s*(.+?))?\)$")
RE_AGENCY_PREFIX = re.compile(r"^(inmobiliaria|corp|agencia)[_-]")
RE_AGENCY_SUFFIX = re.compile(r"[_\s]+\d+[_\s]*\d*$")
RE_WHITESPACE = re.compile(r"\s+")

# Mapa de paraules clau per detectar el tipus de propietat del titol.
# L'ordre importa: "atico" va abans de "piso" perque es mes especific.
PROPERTY_KEYWORDS = [
    ("Atico", ("\u00e1tico", "atico")),
    ("Duplex", ("d\u00faplex", "duplex")),
    ("Estudio", ("estudio",)),
    ("Chalet", ("chalet",)),
    ("Loft", ("loft",)),
    ("Apartamento", ("apartamento",)),
    ("Casa", ("casa",)),
    ("Piso", ("piso",)),
]

# Mapeja el @type del JSON-LD (schema.org) al nostre tipus de propietat
LDTYPE_MAP = {"Apartment": "Piso", "House": "Casa", "SingleFamilyResidence": "Casa"}

# Presets d'ubicacions: agrupen multiples provincies/ciutats
LOCATION_PRESETS = {
    "catalunya": ["barcelona", "girona", "tarragona", "lleida"],
    "pais_valencia": ["valencia", "alicante", "castellon"],
    "espanya": [
        "madrid", "barcelona", "valencia", "sevilla", "zaragoza", "malaga",
        "murcia", "palma_de_mallorca", "las_palmas", "bilbao", "alicante",
        "cordoba", "valladolid", "vigo", "gijon", "hospitalet_de_llobregat",
        "vitoria", "a_coruna", "granada", "elche", "oviedo", "santa_cruz_de_tenerife",
        "pamplona", "almeria", "san_sebastian", "santander", "burgos",
        "albacete", "castellon", "logrono", "badajoz", "salamanca",
        "huelva", "lleida", "tarragona", "leon", "cadiz", "jaen",
        "ourense", "girona", "lugo", "caceres", "melilla", "ceuta",
    ],
}

# Data d'avui calculada un sol cop (no per cada item)
TODAY = date.today().isoformat()


# ---------------------------------------------------------------------------
# Funcions auxiliars de parsing i neteja
# ---------------------------------------------------------------------------

def clean(text):
    """Neteja un camp de text: decodifica entitats HTML, elimina salts
    de linia, i normalitza espais multiples a un sol espai.
    Exemples: 'L&#x27;Hospitalet' -> "L'Hospitalet"
              'text\\n\\nsegon' -> 'text segon'
    """
    if not text:
        return text
    text = html.unescape(str(text))
    text = RE_WHITESPACE.sub(" ", text)
    return text.strip()


def to_float(text):
    """Converteix text amb format numeric espanyol a float.
    Exemples: '231 m2' -> 231.0, '4.487 EUR/m2' -> 4487.0, '41,40' -> 41.4
    Gestiona separadors de milers (punt) i decimals (coma) del format ES.
    """
    if not text or not isinstance(text, str):
        return None
    m = RE_FLOAT.search(text)
    if not m:
        return None
    s = m.group()
    # Heuristica: "4.487" es milers (punt seguit de 3 digits), no decimal
    if RE_MILERS.match(s):
        s = s.replace(".", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def to_int(text):
    """Extreu el primer enter d'un text. Ex: '3 habs.' -> 3, '2 banos' -> 2"""
    if isinstance(text, (int, float)):
        return int(text)
    if not text:
        return None
    m = RE_DIGITS.search(str(text))
    return int(m.group()) if m else None


# ---------------------------------------------------------------------------
# Spider principal
# ---------------------------------------------------------------------------

class PisosSpider(scrapy.Spider):
    """
    Spider per extreure anuncis de venda de pisos.com.

    Parametres CLI (passats via -a o des de run_scraper.py):
        location:     Ubicacio o preset ('catalunya', 'barcelona_capital', etc.)
        max_pages:    Max pagines per ubicacio (0 = sense limit)
        max_items:    Max items totals (0 = sense limit)
        with_details: 'true' per visitar fitxes de detall
        min_price:    Filtre preu minim en EUR
        max_price:    Filtre preu maxim en EUR
        min_area:     Filtre superficie minima en m2
        min_rooms:    Filtre nombre minim d'habitacions
    """

    name = "pisos"
    allowed_domains = ["pisos.com"]

    def __init__(self, location="barcelona_capital", max_pages=0, max_items=0,
                 with_details="false", min_price=None, max_price=None,
                 min_area=None, min_rooms=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Resoldre la ubicacio: pot ser un preset o una llista de slugs
        loc = location.lower().strip()
        if loc in LOCATION_PRESETS:
            self.locations = LOCATION_PRESETS[loc]
        else:
            self.locations = [l.strip() for l in loc.split(",") if l.strip()]

        # 0 = sense limit (scrapar fins que s'acabin les pagines)
        self.max_pages_per_loc = int(max_pages) if int(max_pages) > 0 else float("inf")
        self.max_items = int(max_items) if int(max_items) > 0 else float("inf")
        self.with_details = with_details.lower() in ("true", "1", "yes")

        # Filtres opcionals (aplicats en codi, no via URL — pisos.com no ho suporta)
        self.min_price = float(min_price) if min_price else None
        self.max_price = float(max_price) if max_price else None
        self.min_area = float(min_area) if min_area else None
        self.min_rooms = int(min_rooms) if min_rooms else None

        # Comptadors globals
        self.count = 0        # items extrets amb exit
        self.filtered = 0     # items descartats pels filtres
        self.dupes = 0        # items duplicats ignorats
        self.seen = set()     # conjunt de listing_ids ja processats
        self.pages = {}       # comptador de pagines per ubicacio

        mode = "detall" if self.with_details else "rapid"
        logger.info(f"pisos.com [{mode}] {len(self.locations)} ubicacio(ns)")
        logger.info(f"  Ubicacions: {', '.join(self.locations)}")
        logger.info(f"  Max pag/ubicacio: {self.max_pages_per_loc}")
        if self.max_items != float("inf"):
            logger.info(f"  Max items total: {int(self.max_items)}")
        parts = []
        if self.min_price: parts.append(f"preu>={self.min_price}")
        if self.max_price: parts.append(f"preu<={self.max_price}")
        if self.min_area: parts.append(f"m2>={self.min_area}")
        if self.min_rooms: parts.append(f"habs>={self.min_rooms}")
        if parts:
            logger.info(f"  Filtres: {' '.join(parts)}")

    async def start(self):
        """Genera un request inicial per cada ubicacio configurada.
        Totes es llancen en paral·lel gracies a la concurrencia de Scrapy.
        """
        for loc in self.locations:
            self.pages[loc] = 0
            yield scrapy.Request(
                f"https://www.pisos.com/venta/pisos-{loc}/",
                callback=self.parse_listing,
                cb_kwargs={"loc": loc},
                priority=10,  # prioritat alta per llistats (paginacio no es bloqueja)
            )

    def parse_listing(self, response, loc):
        """Processa una pagina de llistat d'anuncis.

        Per cada card (div.ad-preview) de la pagina:
        1. Extreu les dades basiques de la card (preu, m2, GPS, etc.)
        2. Aplica deduplicacio (per listing_id) i filtres de l'usuari
        3. En mode rapid: yield l'item directament
           En mode detall: yield un request a la fitxa per enriquir l'item

        Al final, segueix la paginacio si no s'han assolit els limits.
        """
        self.pages[loc] = self.pages.get(loc, 0) + 1
        page = self.pages[loc]

        if response.status != 200:
            logger.error(f"HTTP {response.status} [{loc}] {response.url}")
            return

        # Parsejar tots els blocs JSON-LD de la pagina d'un sol cop.
        # Cada card te un <script type="application/ld+json"> amb dades
        # estructurades (schema.org): coordenades GPS, localitat, tipus.
        ld_map = {}
        for raw in response.css("div.ad-preview script[type='application/ld+json']::text").getall():
            try:
                d = json.loads(raw)
                ld_map[d.get("@id", "")] = d
            except (json.JSONDecodeError, KeyError):
                pass

        cards = response.css("div.ad-preview")
        logger.info(f"[{loc}] P{page}: {len(cards)} cards "
                     f"(total={self.count} filt={self.filtered} dup={self.dupes})")

        for card in cards:
            if self.count >= self.max_items:
                return

            # Deduplicacio: ignorem cards ja vistes (pot passar entre pagines)
            lid = card.attrib.get("id", "")
            if not lid or lid in self.seen:
                self.dupes += 1
                continue
            self.seen.add(lid)

            # Extraccio de dades de la card
            item = self._card(card, lid, ld_map.get(lid, {}), response)

            # Aplicar filtres configurats per l'usuari
            if not self._ok(item):
                self.filtered += 1
                continue

            if self.with_details:
                # Mode detall: visitem la fitxa per omplir camps extra
                yield scrapy.Request(
                    item["url"], callback=self._detail,
                    cb_kwargs={"item": item}, priority=1,
                )
            else:
                # Mode rapid: yieldem l'item directament
                self.count += 1
                if self.count % 500 == 0:
                    logger.info(f"[Progres] {self.count} anuncis extrets")
                yield item

        # Paginacio: seguir a la pagina seguent si existeix
        if page < self.max_pages_per_loc and self.count < self.max_items:
            nxt = response.css("div.pagination__next a::attr(href)").get()
            if nxt:
                yield scrapy.Request(
                    response.urljoin(nxt), callback=self.parse_listing,
                    cb_kwargs={"loc": loc}, priority=10,
                )

    def _card(self, card, lid, ld, response):
        """Extreu totes les dades disponibles d'una card del llistat.

        Fonts de dades per card:
        - CSS selectors: titol, preu text, ubicacio, habs, m2, descripcio
        - Atributs data-*: preu numeric (data-ad-price), fotos (data-counter),
          obra nova (data-is-new-development)
        - JSON-LD (schema.org): coordenades GPS, localitat, tipus de propietat

        Args:
            card: Selector de la card (div.ad-preview)
            lid: Listing ID (atribut id de la card)
            ld: Dades JSON-LD de la card (dict)
            response: Response HTTP de la pagina de llistat

        Returns:
            PropertyItem amb totes les dades disponibles al llistat
        """
        i = PropertyItem()
        i["listing_id"] = lid
        i["operation"] = "venta"
        i["scrape_date"] = TODAY
        i["scrape_timestamp"] = datetime.now().isoformat()

        # URL de detall (de l'enllac del titol o de l'atribut data-lnk-href)
        href = card.css("a.ad-preview__title::attr(href)").get() or card.attrib.get("data-lnk-href", "")
        i["url"] = response.urljoin(href) if href else ""

        # Titol i tipus de propietat (detectat per paraules clau al titol)
        title = clean(card.css("a.ad-preview__title::text").get(""))
        i["title"] = title
        i["property_type"] = self._prop_type(title, ld.get("@type", ""))

        # Preu: extraiem el valor numeric directament de data-ad-price
        # (mes fiable que parsejar el text "598.000 EUR")
        i["price_eur"] = to_float(card.css("div.contact-box::attr(data-ad-price)").get(""))

        # Ubicacio: el subtitol te format "Barri (Distrito X. Municipi)"
        sub = clean(card.css("p.ad-preview__subtitle::text").get(""))
        i["full_address"] = sub
        m = RE_LOCATION.match(sub)
        if m:
            i["neighborhood"] = m.group(1).strip()
            i["district"] = m.group(2).strip()
        else:
            i["neighborhood"] = sub
            i["district"] = None

        # Caracteristiques del resum: cada <p class="ad-preview__char">
        # conte un valor com "3 habs.", "2 banos", "78 m2", "3a planta"
        i["rooms"] = i["bathrooms"] = i["area_m2"] = i["floor"] = i["price_per_m2"] = None
        for c in card.css("p.ad-preview__char::text").getall():
            c = c.strip()
            cl = c.lower()
            if "hab" in cl:
                i["rooms"] = to_int(c)
            elif "ba\u00f1o" in cl:
                i["bathrooms"] = to_int(c)
            elif "/m" in cl:
                i["price_per_m2"] = to_float(c)
            elif "m\u00b2" in cl or "m2" in cl:
                i["area_m2"] = to_float(c)
            elif "planta" in cl or cl.startswith("bajo") or "\u00e1tico" in cl:
                i["floor"] = c

        # Calcular preu/m2 si no apareix al resum pero tenim preu i area
        if not i["price_per_m2"] and i["price_eur"] and i["area_m2"]:
            i["price_per_m2"] = round(i["price_eur"] / i["area_m2"], 2)

        # Descripcio breu visible a la card
        i["description"] = clean(card.css("p.ad-preview__description::text").get(""))

        # JSON-LD: coordenades GPS i localitat (municipi)
        geo = ld.get("geo", {})
        i["latitude"] = to_float(geo.get("latitude"))
        i["longitude"] = to_float(geo.get("longitude"))
        i["locality"] = clean(ld.get("address", {}).get("addressLocality", ""))

        # Nombre de fotos i indicador d'obra nova (atributs data-*)
        i["photo_count"] = to_int(card.css("div.carousel__container::attr(data-counter)").get(""))
        i["is_new_development"] = card.css("div.favorite::attr(data-is-new-development)").get("") == "true"

        # Anunciant: extraiem del slug de l'enllac del logo de l'agencia
        ahref = card.css("div.ad-preview__logo span::attr(data-lnk-href)").get("")
        if ahref:
            slug = ahref.strip("/").split("/")[-1]
            slug = RE_AGENCY_PREFIX.sub("", slug)
            slug = RE_AGENCY_SUFFIX.sub("", slug)
            i["advertiser_name"] = slug.replace("_", " ").replace("-", " ").strip().title() or "Agencia"
            i["advertiser_type"] = "Agencia"
        else:
            i["advertiser_name"] = "Particular"
            i["advertiser_type"] = "Particular"

        # Camps que nomes s'omplen en mode detall (None en mode rapid)
        for f in ("has_elevator", "has_terrace", "has_balcony", "has_parking",
                   "has_air_conditioning", "has_swimming_pool", "has_garden",
                   "energy_cert", "construction_year", "condition"):
            i[f] = None
        return i

    def _detail(self, response, item):
        """Enriqueix un item amb dades de la pagina de detall individual.

        Afegeix camps que no estan disponibles al llistat:
        - Caracteristiques booleanes (ascensor, terrassa, parking, etc.)
        - Certificat energetic
        - Estat de conservacio i antiguitat
        - Descripcio completa (no truncada)
        - Nom precis de l'anunciant

        Les caracteristiques s'extreuen dels blocs div.features__feature,
        que contenen parells label/value com "Ascensor" (boolean) o
        "Planta: 3a" (amb valor).
        """
        if response.status != 200:
            self.count += 1
            yield item
            return
        if self.count >= self.max_items:
            return

        # Titol complet (pot ser mes llarg que el de la card)
        t = clean(response.css("div.details__block > h1::text").get(""))
        if t:
            item["title"] = t

        # Ubicacio completa amb barri i districte
        loc = clean(response.css("div.details__block > h1 + p::text").get(""))
        if loc:
            item["full_address"] = loc
            m = RE_LOCATION.match(loc)
            if m:
                item["neighborhood"] = m.group(1).strip()
                item["district"] = m.group(2).strip()

        # Descripcio completa (la del llistat esta truncada)
        parts = response.css("div.description__content *::text").getall()
        if parts:
            desc = clean(" ".join(p.strip() for p in parts if p.strip()))
            item["description"] = desc[:500] + "..." if len(desc) > 500 else desc

        # Features detallades: recollim totes les etiquetes per determinar
        # les caracteristiques booleanes i valors especifics
        feat_labels = set()
        for block in response.css("div.features__feature"):
            lab = block.css("span.features__label::text").get("").strip().rstrip(": ").lower()
            val = block.css("span.features__value::text").get("").strip()
            if not lab:
                continue
            feat_labels.add(lab)
            # Extreure valors especifics de les features
            if lab == "planta" and val:
                item["floor"] = val
            elif lab in ("conservaci\u00f3n", "conservacion") and val:
                item["condition"] = val
            elif lab in ("antig\u00fcedad", "antiguedad") and val:
                item["construction_year"] = val

        # Camps booleans: comprovem si la paraula clau apareix entre les etiquetes
        fl = " ".join(feat_labels)
        item["has_elevator"] = "ascensor" in fl
        item["has_terrace"] = "terraza" in fl
        item["has_balcony"] = "balc" in fl
        item["has_parking"] = "garaje" in fl or "parking" in fl
        item["has_air_conditioning"] = "aire acondicionado" in fl
        item["has_swimming_pool"] = "piscina" in fl
        item["has_garden"] = "jard" in fl

        # Certificat energetic (lletra A-G)
        e = response.css("span.energy-certificate__tag::text").get("").strip().upper()
        if len(e) == 1 and e in "ABCDEFG":
            item["energy_cert"] = e

        # Anunciant: el nom de la fitxa es mes precis que el del llistat
        adv = (response.css("p.owner-info__name a::text").get("") or
               response.css("p.owner-info__name::text").get("")).strip()
        if adv:
            item["advertiser_name"] = adv
            item["advertiser_type"] = "Particular" if "particular" in adv.lower() else "Agencia"

        # Fallback per planta: si no s'ha trobat a les features, buscar al summary
        if not item.get("floor"):
            for s in response.css("li.features-summary__item::text").getall():
                sl = s.strip().lower()
                if "planta" in sl or sl.startswith("bajo"):
                    item["floor"] = s.strip()
                    break

        item["scrape_timestamp"] = datetime.now().isoformat()
        self.count += 1
        if self.count % 500 == 0:
            logger.info(f"[Progres] {self.count} anuncis")
        yield item

    def _ok(self, item):
        """Verifica si un item passa els filtres configurats per l'usuari.
        Retorna False si algun filtre el descarta, True si passa tots.
        """
        p = item.get("price_eur")
        if p is not None:
            if self.min_price and p < self.min_price: return False
            if self.max_price and p > self.max_price: return False
        a = item.get("area_m2")
        if a is not None and self.min_area and a < self.min_area: return False
        r = item.get("rooms")
        if r is not None and self.min_rooms and r < self.min_rooms: return False
        return True

    @staticmethod
    def _prop_type(title, ld_type):
        """Detecta el tipus de propietat a partir del titol de l'anunci.
        Prioritza el titol sobre el JSON-LD perque es mes granular
        (distingeix atico, duplex, estudio, etc.)
        """
        tl = title.lower()
        for label, kws in PROPERTY_KEYWORDS:
            if any(k in tl for k in kws):
                return label
        return LDTYPE_MAP.get(ld_type, "Piso")
