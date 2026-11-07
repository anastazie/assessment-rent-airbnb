# Amsterdam Rental Revenue Pipeline

A Medallion Architecture data pipeline comparing short-term Airbnb and long-term Kamernet rental revenue per Amsterdam postcode, to identify postcodes with the highest investment potential.

## Business question

> For each Amsterdam postcode, is listing a property on Airbnb or renting it long-term through Kamernet more profitable?

---

## Architecture

The pipeline follows the [Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture) (Bronze → Silver → Gold) and is designed to run on Databricks.

```
data/airbnb.csv          ─┐
data/rentals.json         ├─► Bronze (raw Delta) ─► Silver (clean Delta) ─► Gold (revenue Delta + Parquet)
data/geo/*.geojson        ─┘ (geo: raw files only, see below)
```

### Bronze
Ingests `airbnb.csv` and `rentals.json` as-is into Delta tables with an ingestion timestamp. No transformation — bronze preserves raw fidelity so the Silver cleaning logic can be changed without data loss.

Geographic reference files (`post_codes.geojson`, `amsterdam_areas.geojson`) are intentionally excluded from Bronze. They are already clean, versioned in the repo alongside the zip originals, and consumed directly as raw assets in the Silver zipcode backfill. Routing them through Delta would add ingestion cost without adding value.

### Silver
Applies business rules and produces clean, typed, Amsterdam-scoped tables:

- **Rentals**: filtered to `city == 'Amsterdam'` (the source dataset covers all of the Netherlands). Filtering here rather than Bronze preserves raw fidelity and keeps the business rule in the transformation layer where it belongs.
- **Airbnb**: price outliers capped at the IQR upper fence; **22.7% of rows had no zipcode** — backfilled via point-in-polygon lookup against `post_codes.geojson` using a broadcast UDF, recovering all rows that had valid coordinates.
- Raw string fields (`rent`, `deposit`, `areaSqm`) parsed to numeric types; single-element list fields in the Kamernet JSON flattened to scalars.

Zipcodes were transformed to PC4 (the 4-digit prefix of a Dutch `NNNNAA` postcode) because:
- Airbnb's `zipcode` field is already truncated to PC4 in the source CSV (`1053`, not `1053AB`), so joining on the full PC6 would match nothing.
- The `post_codes.geojson` used for lat/lon backfill contains PC4 polygons only, so recovered zipcodes can't be more granular than PC4 anyway.
- PC6 is street-segment scale (~20 addresses); aggregating revenue at that grain would produce many postcodes with 1–2 listings and unstable medians. PC4 is neighbourhood-scale and gives statistically meaningful per-postcode comparisons.

### Gold
Calculates estimated monthly revenue per listing and aggregates by postcode:

- **Airbnb monthly revenue** = `nightly_price × 365 × 0.66 / 12`
  — 66% occupancy rate per [AirDNA Amsterdam market data](https://www.airdna.co/vacation-rental-data/app/nl/default/amsterdam/overview), applied as a city-wide average. Actual occupancy varies by neighbourhood, property type, and season.
- **Rental monthly revenue** = `rent + additional_costs`
- Output: `revenue_per_postcode` table with average revenue per source, listing counts, and a `recommendation` column (airbnb / rental / neutral).

---

## Repository structure

```
notebooks/          Pipeline notebooks (run in order: 01 → 02 → 03)
  01_bronze.ipynb   Raw ingestion
  02_silver.ipynb   Cleaning, filtering, zipcode backfill
  03_gold.ipynb     Revenue calculation and postcode aggregation

src/amsterdam_rental/
  transforms.py     Pure Python transform functions (no Spark dependency)
  geo.py            PostcodeIndex — point-in-polygon zipcode backfill

tests/
  test_transforms.py  Unit tests for all transform functions
  test_geo.py         Unit tests for PostcodeIndex with GeoJSON fixture

scratch/
  01_eda.ipynb      Exploratory analysis — data quality findings that informed Silver design

resources/
  pipeline_job.yml  Databricks Asset Bundle job configuration

data/
  airbnb.zip        Source: Airbnb listings (nightly price, location, room type)
  rentals.zip       Source: Kamernet rentals (monthly rent, Amsterdam + rest of NL)
  geo/
    post_codes.zip        474 PC4 postcode polygons (greater Amsterdam)
    amsterdam_areas.zip   99 neighbourhood polygons (Amsterdam only)
  output/           Pipeline output (Delta tables + Parquet exports) — gitignored
```

---

## Running the pipeline

### On Databricks (recommended)

1. Import this repository into a Databricks Repo.
2. Unzip the source files in `data/` — or let the notebooks handle it automatically (they detect and extract from zip if the unzipped file is absent).
3. Create a Unity Catalog volume at `/Volumes/workspace/default/amsterdam_rental` or update `OUTPUT_ROOT` in each notebook's setup cell.
4. Run notebooks in order: `01_bronze` → `02_silver` → `03_gold`.
5. (Optional) Build a dashboard to visualise the gold table — see [docs/dashboard.md](docs/dashboard.md).

To deploy as a scheduled job using the Databricks CLI:

```bash
databricks bundle deploy
databricks bundle run amsterdam_rental_pipeline
```

### Local (PySpark)

```bash
pip install pyspark delta-spark pytest
python -m pytest tests/        # run unit tests
# then open and run notebooks in order using Jupyter
```

---

## Known limitations

| Limitation | Detail |
|---|---|
| Rentals data age | Kamernet dataset was scraped in 2019 — revenue estimates reflect that market, not current prices |
| Uniform occupancy rate | 66% applied to all Airbnb listings; in reality varies significantly by neighbourhood and property type |
| No actual occupancy data | Airbnb dataset contains nightly prices only — occupancy is estimated, not measured |
| Geo backfill boundary | Point-in-polygon only covers postcodes in `post_codes.geojson`; listings outside greater Amsterdam return null |
