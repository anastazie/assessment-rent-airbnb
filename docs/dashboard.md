# Building the Databricks Dashboard (optional)

The static map in the README is produced by the pipeline itself (`notebooks/04_report.ipynb`). This guide adds an **interactive** version as a Databricks AI/BI Dashboard on top of the same gold table. The dashboard adds no logic of its own: the tiers, income figures and geometry all come from `revenue_per_postcode`, so it always matches the pipeline output.

## What the dashboard answers

We have no real-estate sale prices, so investment potential is approximated by **how much an apartment in a postcode earns per month**. `03_gold` splits postcodes into thirds (High / Medium / Low potential) by their highest achievable monthly income (`best_monthly_eur`). Postcodes with fewer than 5 listings in total get `potential_score = 0` (*Not enough data*).

In the data, Airbnb out-earns long-term rental in every postcode where both exist, so the ranking is in practice driven by expected Airbnb income. Long-term rent is kept in the tooltip for comparison.

## Prerequisites

Run the pipeline once (`databricks bundle run amsterdam_rental_pipeline`, see the README). The gold task registers these tables in `<catalog>.<schema>`, which defaults to your workspace's default catalog and the `amsterdam_rental` schema:

- `revenue_per_postcode`: one row per PC4, including `investment_potential`, `potential_score` and the PC4 polygon as `geom_geojson`
- `revenue_per_listing`
- `pc4_geometry`: all 474 PC4 polygons

To find the catalog the job used, open the job run and check the `catalog` parameter, or the first output line of the bronze task (`tables : <catalog>.<schema>.*`).

## 1. Create the dashboard

**Dashboards** (left sidebar) → **Create dashboard** → name it e.g. *Amsterdam Rental Revenue*.

The dashboard has two tabs:
- **Canvas**: where widgets are placed
- **Data**: where SQL datasets are defined

## 2. Add the dataset

Switch to the **Data** tab → **Create from SQL** → paste, replacing `<catalog>.<schema>`:

```sql
SELECT
  pc4,
  investment_potential,
  potential_score,
  ROUND(best_monthly_eur, 0)       AS potential_monthly_income_eur,
  ROUND(rental_avg_monthly_eur, 0) AS rental_monthly_income_eur,
  COALESCE(airbnb_listing_count, 0) AS airbnb_listing_count,
  COALESCE(rental_listing_count, 0) AS rental_listing_count,
  st_geomfromgeojson(geom_geojson) AS geometry
FROM <catalog>.<schema>.revenue_per_postcode
WHERE geom_geojson IS NOT NULL
```

Name the dataset `investment_potential_by_pc4`. Save.

`st_geomfromgeojson` turns the stored GeoJSON text into a `GEOMETRY` column, which the choropleth needs. It requires a serverless or recent SQL warehouse.

## 3. Add widgets

Switch back to **Canvas**. For each widget: click **+ Add a visualization** → select the `investment_potential_by_pc4` dataset.

### Widget 1: Headline text
Use the **T** (text) icon in the bottom toolbar and place it above the map:

> **Short-term rental (Airbnb) out-earns long-term rental in every Amsterdam postcode.** Investment potential is therefore ranked by expected Airbnb income: the top third of postcodes = High potential.
> *Assumes 66% occupancy and excludes costs and Amsterdam's 30-night limit on renting out a whole home to tourists.*

### Widget 2: Choropleth map
- **Visualization**: *Choropleth map*
- **Region**: *Custom geometry* (the built-in *Postal* regions only cover the US)
- **Geometry**: `geometry`
- **Color**: `AVG(potential_score)` with a **sequential** scheme (light → dark). Avoid diverging schemes, which fade the middle values to white.
- **Tooltip**: `pc4`, `investment_potential`, `AVG(potential_monthly_income_eur)`, `AVG(rental_monthly_income_eur)`, `SUM(airbnb_listing_count)`, `SUM(rental_listing_count)`
- **Title**: *Investment potential by postcode*

There is one row per postcode, so every aggregation returns the postcode's own value. Use **AVG** for income fields and **SUM** for listing counts.

### Widget 3: Investor shortlist
- **Visualization**: *Table*
- **Columns**: `pc4`, `investment_potential`, `potential_monthly_income_eur`, `rental_monthly_income_eur`, `airbnb_listing_count`, `rental_listing_count`
- **Sort**: `potential_monthly_income_eur` descending
- Optional widget filter: `investment_potential = 'High potential'`

### Widget 4: Potential split
- **Visualization**: *Bar*
- **Group by**: `investment_potential`
- **Value**: `COUNT(pc4)`

## 4. Share

Top-right **Share** button: add viewers, or **Publish** a view-only link (if workspace permissions allow).

## Caveats

- **No purchase prices**: income alone ignores how expensive a postcode is to buy into.
- **Income per apartment, not per m²**: postcodes with larger apartments rank higher.
- **Optimistic Airbnb figures**: 66% occupancy (~240 nights/year), gross of platform fees, tourist tax and cleaning, and above Amsterdam's 30-night annual cap for whole-home holiday rentals.
