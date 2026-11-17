# AI Session Export — 2026-11-17

Tool: Claude Code (claude-opus-5-5)
Focus: Making the project run out of the box after reviewer feedback on reproducibility.

---

## Context

Reviewer feedback on the submission named four gaps:
1. Workspace, catalog and schema values were hardcoded, so the code couldn't run as delivered.
2. The data wasn't included in the bundle sync and had to be added manually.
3. The visual in the README wasn't produced by the notebooks.
4. The AI tooling export wasn't in the repository.

---

## Conversation summary

**User:** Help me understand the feedback.

**Assistant:** Checked each point against the repo:
- `databricks.yml` hardcoded the workspace host. The notebooks hardcoded `/Volumes/workspace/default/amsterdam_rental` and `workspace.amsterdam_rental.*`, and the volume was never created by the bundle.
- `docs/dashboard.md` step 1 read a geojson from a volume path that nothing populated. The bronze and silver notebooks staged sources into two different volume folders.
- The README map was a screenshot of a hand-built AI/BI dashboard, and its tiering SQL lived only in the docs.
- The session export existed locally but was excluded from git via `.git/info/exclude`.

---

**User:** Is this critical for a Technical Instructor role?

**Assistant:** Mostly yes. Course materials get cloned into many different workspaces by people who can't debug them, so reproducibility is the core of the job. But the gaps are packaging habits that take hours to fix, not flaws in the analysis.

---

**User:** Please make the fixes.

**Assistant:**
- **Configuration**: added `src/amsterdam_rental/config.py` (`PipelineConfig`, `resolve_catalog`, `stage_sources`).
  - Bundle variables `catalog` / `schema` / `volume` are passed to every task as job parameters and appear as notebook widgets when run interactively.
  - A blank catalog uses the workspace's default catalog. `hive_metastore` fails with an actionable message.
  - No host in `databricks.yml`; the workspace comes from the CLI profile.
- **Setup**: bronze creates the schema and volume (`CREATE ... IF NOT EXISTS`) and stages all sources into one `source/` folder in the volume.
- **Visual**:
  - Investment-potential tiers (NTILE(3) over best monthly income, minimum 5 listings) moved from the dashboard SQL into `03_gold`.
  - New `04_report.ipynb` job task renders the map with plain matplotlib (`src/amsterdam_rental/plotting.py`).
  - The README image is now that task's output, copied from the volume. The dashboard guide became an optional SELECT on the gold table.
- **AI export**: moved into `docs/ai-sessions/` and linked from the README.
- Rewrote the README around a copy-paste quickstart; added `requirements-dev.txt` and 17 tests.

---

**User:** (re-authenticated the CLI)

**Assistant:** Deployed to a brand-new schema to imitate a reviewer. Bronze failed: `data/airbnb.zip not found` in the deployed bundle, which reproduced the reviewer's second point exactly.
- Root cause: **Databricks workspace import unpacks `.zip` archives on upload**. The zips never existed in the deployment. The earlier runs only worked because of leftover unzipped files from older deploys.
- A probe upload confirmed that `.zip` gets unpacked while `.gz` is stored byte for byte.
- Fix: the source data now ships as `.csv.gz` / `.json.gz` / `.geojson.gz`, decompressed with `gzip` during staging. `sync.include` lists the `.gz` files explicitly.

Clean-room re-test: deleted the deployed files and the local sync cache, then deployed to another new schema and ran the job. All four tasks succeeded. The schema, volume and the three Unity Catalog tables were created automatically, and the map PNG was written to the volume and copied into `docs/images/`.

---

## Decision log

| Decision | Rationale |
|---|---|
| Catalog defaults to the workspace's default catalog | Runs with zero flags on most workspaces; any value can be overridden with `--var` |
| Schema and volume created by the pipeline, not as bundle resources | Bundle resources need the catalog at deploy time; creating them at runtime lets a blank catalog resolve to the workspace default |
| One shared setup cell + `config.py` | All paths derive from three parameters, unit-testable without Spark |
| Gzip instead of zip for source data | Workspace import unpacks zips on upload, so they never reach the deployment |
| Tiers computed in gold, map rendered by a job task | Every output, including the README image, traces back to the pipeline |
| Matplotlib, no geopandas | Available on serverless without extra dependencies |
| Single-hue blue ramp for tiers | Ordered tiers read as magnitude; grey for unscored postcodes |
| Verified by a clean-room deploy to a new schema | The only reliable way to catch "works on my workspace" problems |
