# Building the Databricks Dashboard

Step-by-step guide for visualising `revenue_per_postcode` as a Databricks AI/BI Dashboard.

## Prerequisites

Run `03_gold.ipynb` end-to-end first. The final cell registers two Unity Catalog tables that the dashboard will query:

- `workspace.amsterdam_rental.revenue_per_postcode`
- `workspace.amsterdam_rental.revenue_per_listing`

## 1. Create the dashboard

**Dashboards** (left sidebar) → **Create dashboard** → name it e.g. *Amsterdam Rental Revenue*.

The dashboard has two tabs:
- **Canvas** — where widgets are placed
- **Data** — where SQL datasets are defined

## 2. Add a dataset

Switch to the **Data** tab → **Create from SQL** → paste:

```sql
SELECT
  pc4,
  airbnb_avg_monthly_eur,
  rental_avg_monthly_eur,
  airbnb_premium_eur,
  recommendation,
  airbnb_listing_count,
  rental_listing_count
FROM workspace.amsterdam_rental.revenue_per_postcode
WHERE airbnb_avg_monthly_eur IS NOT NULL
  AND rental_avg_monthly_eur IS NOT NULL
```

Name the dataset `revenue_by_pc4`. Save.

## 3. Add widgets

Switch back to **Canvas**. For each widget: click **+ Add a visualization** → select the `revenue_by_pc4` dataset.

### Widget 1 — Choropleth map (the headliner)
- **Visualization type**: *Symbol map* or *Choropleth map*
- **Region key**: `pc4`
- **Colour**: `airbnb_premium_eur` (green = Airbnb wins, red = rental wins)

Databricks' built-in geo library may not recognise Dutch PC4. Two fallbacks:
- **Symbol map with lat/lon** — add centroid coordinates to the SQL query (`AVG(latitude)`, `AVG(longitude)` grouped by `pc4` from `revenue_per_listing`)
- **Custom GeoJSON** — upload `data/geo/post_codes.geojson` via the map widget's advanced config

### Widget 2 — Top 10 bar chart
- **Visualization**: *Bar*
- Add dataset filter: `ORDER BY airbnb_premium_eur DESC LIMIT 10`
- **X**: `pc4`, **Y**: `airbnb_premium_eur`
- **Colour by**: `recommendation`

### Widget 3 — KPI tiles
- **Visualization**: *Counter*
- Add multiple counters for: total postcodes, average premium, total Airbnb listings, total rental listings

### Widget 4 — Recommendation split
- **Visualization**: *Pie chart*
- **Slice by**: `recommendation`
- **Value**: `COUNT(*)`

## 4. Share

Top-right **Share** button:
- Add viewer emails for direct access, or
- **Publish** to generate a view-only link that doesn't require a Databricks login (if workspace permissions allow)

## Troubleshooting

| Symptom | Fix |
|---|---|
| Table not found in SQL editor | Re-run the final cell of `03_gold.ipynb` to register the UC tables |
| Choropleth greyed-out postcodes | The `pc4` type or format doesn't match the geo library — try casting (`CAST(pc4 AS STRING)`) or use the custom GeoJSON fallback |
| Map renders tiny | Drag the widget edges to resize on the Canvas |
