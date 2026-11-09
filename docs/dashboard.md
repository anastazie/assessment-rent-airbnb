# Building the Databricks Dashboard

Step-by-step guide for visualising **investment potential per Amsterdam postcode** as a Databricks AI/BI Dashboard.

## What the dashboard answers

We have no real-estate sale prices, so investment potential is approximated by **how much an apartment in a postcode earns per month**. Postcodes are split into thirds (High / Medium / Low potential) by their highest achievable monthly rental income.

In the data, Airbnb out-earns long-term rental in every postcode, so the ranking is in practice driven by expected Airbnb income. Long-term rent is kept in the tooltip for comparison.

## Prerequisites

Run `03_gold.ipynb` end-to-end first. The final cell registers the Unity Catalog tables the dashboard queries:

- `workspace.amsterdam_rental.revenue_per_postcode`
- `workspace.amsterdam_rental.revenue_per_listing`

## 1. Register postcode polygons (one-time)

The choropleth's built-in **Postal** regions only cover the US, so the map uses **Custom geometry**. Load the PC4 polygons from `data/geo/post_codes.geojson` (474 postcodes, WGS84, keyed by `pc4_code`) into a table by running this in a Databricks notebook:

```python
import json
from pyspark.sql import Row

path = "/Volumes/workspace/default/amsterdam_rental/data/geo/post_codes.geojson"
with open(path) as f:
    features = json.load(f)["features"]

rows = [Row(pc4=feat["properties"]["pc4_code"],
            geom_geojson=json.dumps(feat["geometry"]))
        for feat in features]

(spark.createDataFrame(rows)
      .write.mode("overwrite")
      .saveAsTable("workspace.amsterdam_rental.pc4_geometry"))
```

## 2. Create the dashboard

**Dashboards** (left sidebar) → **Create dashboard** → name it e.g. *Amsterdam Rental Revenue*.

The dashboard has two tabs:
- **Canvas**: where widgets are placed
- **Data**: where SQL datasets are defined

## 3. Add the dataset

Switch to the **Data** tab → **Create from SQL** → paste:

```sql
WITH base AS (
  SELECT
    r.pc4,
    r.airbnb_avg_monthly_eur,
    r.rental_avg_monthly_eur,
    COALESCE(r.airbnb_listing_count, 0) AS airbnb_listing_count,
    COALESCE(r.rental_listing_count, 0) AS rental_listing_count,
    GREATEST(r.airbnb_avg_monthly_eur, r.rental_avg_monthly_eur) AS best_monthly_eur,
    (COALESCE(r.airbnb_listing_count, 0) + COALESCE(r.rental_listing_count, 0)) >= 5 AS enough_data,
    g.geom_geojson
  FROM workspace.amsterdam_rental.revenue_per_postcode r
  JOIN workspace.amsterdam_rental.pc4_geometry g
    ON CAST(r.pc4 AS STRING) = g.pc4
),
ranked AS (
  SELECT *,
    CASE WHEN enough_data
         THEN NTILE(3) OVER (PARTITION BY enough_data ORDER BY best_monthly_eur)
         ELSE 0 END AS potential_score
  FROM base
)
SELECT
  pc4,
  ROUND(best_monthly_eur, 0)       AS potential_monthly_income_eur,
  ROUND(rental_avg_monthly_eur, 0) AS rental_monthly_income_eur,
  airbnb_listing_count,
  rental_listing_count,
  potential_score,
  CASE potential_score
    WHEN 3 THEN 'High potential'
    WHEN 2 THEN 'Medium potential'
    WHEN 1 THEN 'Low potential'
    ELSE 'Not enough data'
  END AS investment_potential,
  st_geomfromgeojson(geom_geojson) AS geometry
FROM ranked
```

Name the dataset `investment_potential_by_pc4`. Save.

How the query works:
- **`potential_monthly_income_eur`**: the higher of average Airbnb income and average long-term rent for the postcode. `GREATEST` skips a missing side, so postcodes with data on only one side stay on the map.
- **`NTILE(3)`**: splits the scored postcodes into three equal groups. The tiers are relative to the rest of Amsterdam, so no hand-picked euro thresholds are needed.
- **`enough_data`**: a postcode needs at least 5 listings in total (Airbnb + rental) to be scored. Postcodes below that get `potential_score = 0` and the label *Not enough data*, so one outlier listing can't make a postcode look "High". Lower the threshold to `>= 3` if too many postcodes go unscored.
- **`geometry`**: `st_geomfromgeojson` turns the stored GeoJSON text into a `GEOMETRY` column, which the choropleth needs. Requires a serverless or recent SQL warehouse.

The dataset has exactly one row per postcode: the gold table is grouped by `pc4`, and `post_codes.geojson` contains 474 unique postcodes.

## 4. Add widgets

Switch back to **Canvas**. For each widget: click **+ Add a visualization** → select the `investment_potential_by_pc4` dataset.

### Widget 1: Headline text
Use the **T** (text) icon in the bottom toolbar and place it above the map:

> **Short-term rental (Airbnb) out-earns long-term rental in every Amsterdam postcode.** Investment potential is therefore ranked by expected Airbnb income: the top third of postcodes = High potential.
> *Assumes 66% occupancy and excludes costs and Amsterdam's 30-night limit on renting out a whole home to tourists.*

### Widget 2: Choropleth map (the headliner)
- **Visualization**: *Choropleth map*
- **Region**: *Custom geometry*
- **Geometry**: `geometry`
- **Color**: `AVG(potential_score)` with a **sequential** scheme (light → dark green). With only four values (0–3) the shades stay clearly distinct. Avoid diverging schemes, which fade the middle values to white.
- **Tooltip**:
  - `pc4`
  - `investment_potential`
  - `AVG(potential_monthly_income_eur)`
  - `AVG(rental_monthly_income_eur)`
  - `SUM(airbnb_listing_count)`
  - `SUM(rental_listing_count)`
- **Title**: *Investment potential by postcode*
- **Description**: *Based on the highest achievable monthly rental income. Dark = top third of Amsterdam postcodes. Lightest = fewer than 5 listings, not scored.*

Aggregations: because there is one row per postcode, every aggregation returns the postcode's own value. Use **AVG** for income fields (reads correctly as "average income" and won't double-count if duplicates ever appear) and **SUM** for listing counts.

### Widget 3: Investor shortlist
- **Visualization**: *Table*
- **Columns**: `pc4`, `investment_potential`, `potential_monthly_income_eur`, `rental_monthly_income_eur`, `airbnb_listing_count`, `rental_listing_count`
- **Sort**: `potential_monthly_income_eur` descending
- Optional widget filter: `investment_potential = 'High potential'`

### Widget 4: Potential split
- **Visualization**: *Bar* or *Pie*
- **Group by**: `investment_potential`
- **Value**: `COUNT(pc4)`

## 5. Share

Top-right **Share** button:
- Add viewer emails for direct access, or
- **Publish** to generate a view-only link that doesn't require a Databricks login (if workspace permissions allow)

## Caveats

- **No purchase prices**: income alone ignores how expensive a postcode is to buy into. High-income postcodes may also be the most expensive.
- **Income per apartment, not per m²**: postcodes with larger apartments rank higher.
- **Optimistic Airbnb figures**: 66% occupancy (~240 nights/year), gross of platform fees, tourist tax and cleaning, and above Amsterdam's 30-night annual cap for whole-home holiday rentals.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Table not found | Re-run the final cell of `03_gold.ipynb`, and step 1 for `pc4_geometry` |
| *Postal* region option only lists the US | Expected. Use *Custom geometry* with the `geometry` column (steps 1 and 3) |
| `st_geomfromgeojson` not found | The SQL warehouse lacks spatial SQL. Switch to a serverless warehouse, or fall back to a *Point map* using the `geo_point_2d` centroids in `post_codes.geojson` |
| Postcodes missing from the map | They have no row in `revenue_per_postcode`, or the `pc4` values don't match. Check `CAST(pc4 AS STRING)` produces 4-digit codes |
| Colors look washed out | Switch to a sequential color scheme (see Widget 2) |
| Other widgets suddenly show one postcode | Clicking a map region adds a cross-filter chip under **Global filters**. Click **Reset all to default** |
| Map renders tiny | Drag the widget edges to resize on the Canvas |
