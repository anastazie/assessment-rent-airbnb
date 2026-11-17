"""
Runtime configuration shared by every pipeline notebook.

Nothing about the target workspace is hardcoded. On Databricks the catalog, schema
and volume arrive as job parameters (set from bundle variables in databricks.yml) or
notebook widgets; a blank catalog falls back to the workspace's default catalog.
Locally, everything lives under ``data/output/`` in the repository.
"""

import gzip
import os
import shutil
from dataclasses import dataclass
from typing import Optional

DEFAULT_SCHEMA = "amsterdam_rental"
DEFAULT_VOLUME = "pipeline"

# Catalogs that cannot hold Unity Catalog volumes
_NON_UC_CATALOGS = {"hive_metastore", "spark_catalog"}

# Raw inputs shipped in the repo, gzipped: {staged name: path under data/}.
# Gzip, not zip: Databricks workspace import unpacks .zip archives on upload, so zips
# never arrive in a bundle deployment; .gz files are uploaded byte-for-byte.
SOURCE_FILES = {
    "airbnb.csv": "airbnb.csv.gz",
    "rentals.json": "rentals.json.gz",
    "post_codes.geojson": "geo/post_codes.geojson.gz",
}


def resolve_catalog(requested: Optional[str], current: Optional[str]) -> str:
    """Return the catalog to use: the requested one, else the session's current catalog.

    Raises ValueError with an actionable message if neither is a Unity Catalog catalog.
    """
    catalog = (requested or "").strip() or (current or "").strip()
    if not catalog or catalog in _NON_UC_CATALOGS:
        raise ValueError(
            f"No Unity Catalog catalog available (got {catalog!r}). Pass one explicitly, "
            "e.g. `databricks bundle deploy --var catalog=<your_catalog>` or set the "
            "`catalog` widget at the top of the notebook."
        )
    return catalog


def workspace_repo_root(notebook_path: str, depth: int = 2) -> str:
    """Derive the repo root in /Workspace from a notebook path like /Users/u/repo/notebooks/nb."""
    parent = "/".join(notebook_path.rstrip("/").split("/")[:-depth])
    return ensure_workspace_prefix(parent)


def ensure_workspace_prefix(path: str) -> str:
    """Workspace paths are only readable via Python file APIs under the /Workspace mount."""
    path = path.rstrip("/")
    return path if path.startswith("/Workspace/") else f"/Workspace{path}"


@dataclass(frozen=True)
class PipelineConfig:
    """Where the pipeline reads and writes. Build it with ``for_databricks`` or ``for_local``."""

    repo_root: str
    root: str  # all pipeline files live under here (UC volume or data/output)
    catalog: Optional[str] = None
    schema: Optional[str] = None
    volume: Optional[str] = None

    @classmethod
    def for_databricks(
        cls,
        repo_root: str,
        catalog: str,
        schema: str = DEFAULT_SCHEMA,
        volume: str = DEFAULT_VOLUME,
    ) -> "PipelineConfig":
        schema, volume = schema.strip() or DEFAULT_SCHEMA, volume.strip() or DEFAULT_VOLUME
        return cls(
            repo_root=ensure_workspace_prefix(repo_root),
            root=f"/Volumes/{catalog}/{schema}/{volume}",
            catalog=catalog,
            schema=schema,
            volume=volume,
        )

    @classmethod
    def for_local(cls, repo_root: str) -> "PipelineConfig":
        repo_root = os.path.abspath(repo_root)
        return cls(repo_root=repo_root, root=os.path.join(repo_root, "data", "output"))

    @property
    def on_databricks(self) -> bool:
        return self.catalog is not None

    @property
    def data_dir(self) -> str:
        """The repo's data/ folder holding the source zips."""
        return os.path.join(self.repo_root, "data")

    @property
    def source_dir(self) -> str:
        """Unzipped raw inputs, readable by Spark."""
        return f"{self.root}/source"

    def source(self, name: str) -> str:
        return f"{self.source_dir}/{name}"

    def layer(self, name: str) -> str:
        """Delta / Parquet / figure output folder, e.g. layer('bronze')."""
        return f"{self.root}/{name}"

    def table(self, name: str) -> Optional[str]:
        """Fully qualified Unity Catalog table name, or None when running locally."""
        return f"{self.catalog}.{self.schema}.{name}" if self.on_databricks else None

    def describe(self) -> str:
        lines = [f"repo_root : {self.repo_root}", f"root      : {self.root}"]
        if self.on_databricks:
            lines.append(f"tables    : {self.catalog}.{self.schema}.*")
        return "\n".join(lines)


def get_local_spark(app_name: str):
    """Local SparkSession with Delta Lake enabled (on Databricks use the built-in `spark`)."""
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession

    builder = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"
        )
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()


def stage_sources(data_dir: str, source_dir: str) -> dict:
    """Decompress the raw inputs from the repo's data/ folder into ``source_dir``.

    Always overwrites, so a re-run picks up changed source data. Returns {name: path}.
    """
    os.makedirs(source_dir, exist_ok=True)
    staged = {}
    for name, gz_rel in SOURCE_FILES.items():
        gz_path = os.path.join(data_dir, gz_rel)
        if not os.path.exists(gz_path):
            raise FileNotFoundError(
                f"{gz_path} not found. The source files must be deployed with the code "
                "(they are tracked in git and listed under `sync.include` in databricks.yml)."
            )
        dst = os.path.join(source_dir, name)
        with gzip.open(gz_path, "rb") as src, open(dst, "wb") as out:
            shutil.copyfileobj(src, out)
        staged[name] = dst
    return staged
