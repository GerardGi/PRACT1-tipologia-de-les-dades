# Scraper de pisos.com — Mercat immobiliari 2026

**Autors:** Gerard Gines Perez, Guillem Maluenda  
**Assignatura:** Tipologia i cicle de vida de les dades — UOC, MSc Data Science  
**DOI Zenodo:** `[19429081](https://doi.org/10.5281/zenodo.19429081)`

## Descripcio

Scraper de [pisos.com](https://www.pisos.com) que extreu anuncis de venda d'habitatges amb dades estructurades: preu, superficie, habitacions, coordenades GPS, ubicacio, anunciant i mes. Suporta qualsevol ubicacio d'Espanya i filtres per preu, superficie i habitacions.

**Dos modes d'operacio:**
- **Mode rapid** (per defecte): extreu dades de les cards del llistat. 30 anuncis per request, ~300 anuncis en <30 segons.
- **Mode detall** (`--with-details`): visita cada anunci per obtenir camps addicionals (certificat energetic, descripcio completa, caracteristiques com ascensor/terrassa).

## Installacio

```bash
poetry install
```

No requereix Playwright ni navegador — pisos.com serveix HTML complet.

## Mètode d'us

```bash
# Barcelona ciutat, 300 anuncis (~30 seg)
poetry run python source/run_scraper.py

# Amb filtres de preu i habitacions
poetry run python source/run_scraper.py --min-price 150000 --max-price 400000 --min-rooms 2

# Qualsevol ubicacio d'Espanya
poetry run python source/run_scraper.py --location girona
poetry run python source/run_scraper.py --location madrid --max-items 500
poetry run python source/run_scraper.py --location hospitalet_de_llobregat

# Barcelona provincia (inclou municipis del voltant)
poetry run python source/run_scraper.py --location barcelona --max-pages 20 --max-items 500

# Amb detalls complets (mes lent: visita cada anunci)
poetry run python source/run_scraper.py --with-details --max-items 50

# Pisos grans i cars a Sarria
poetry run python source/run_scraper.py --min-area 120 --min-price 500000
```

## Parametres

| Parametre | Descripcio | Default |
|---|---|---|
| `--location` | Slug de pisos.com: `barcelona_capital`, `girona`, `madrid`... | `barcelona_capital` |
| `--max-pages` | Pagines de llistat (30 anuncis/pag) | 10 |
| `--max-items` | Limit total d'anuncis | 300 |
| `--with-details` | Visitar detall per camps extra | No |
| `--min-price` | Preu minim (EUR) | - |
| `--max-price` | Preu maxim (EUR) | - |
| `--min-area` | Superficie minima (m2) | - |
| `--min-rooms` | Habitacions minimes | - |
| `--output` | Path CSV de sortida | `dataset/pisos_barcelona.csv` |

## Dataset

31 camps per anunci:

| Camp | Font | Descripcio |
|---|---|---|
| `listing_id` | llistat | ID unic |
| `title` | llistat | Titol |
| `property_type` | llistat | Piso, Atico, Casa, Duplex... |
| `price_eur` | llistat | Preu (EUR) |
| `price_per_m2` | llistat | Preu per m2 |
| `area_m2` | llistat | Superficie |
| `rooms` | llistat | Habitacions |
| `bathrooms` | llistat | Banys |
| `floor` | llistat/detall | Planta |
| `locality` | llistat (JSON-LD) | Municipi |
| `neighborhood` | llistat | Barri |
| `district` | llistat | Districte |
| `latitude` | llistat (JSON-LD) | Coordenada GPS |
| `longitude` | llistat (JSON-LD) | Coordenada GPS |
| `description` | llistat/detall | Descripcio |
| `advertiser_name` | llistat/detall | Anunciant |
| `has_elevator` | detall | Ascensor |
| `has_terrace` | detall | Terrassa |
| `has_parking` | detall | Garatge |
| `energy_cert` | detall | Certificat energetic |
| `condition` | detall | Estat conservacio |
| ... | | (31 camps total) |

## Consideracions etiques

- Delays de 1.5-3s entre requests, 2 concurrents maxim.
- Rotacio d'user-agents.
- Volum limitat: centenars d'anuncis, no extraccio massiva.
- Nomes dades publiques visibles a qualsevol visitant.
- Us exclusivament academic.

## Llicencies

- **Codi**: MIT — **Dataset**: CC BY-NC-SA 4.0
