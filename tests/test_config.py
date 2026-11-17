"""Unit tests for amsterdam_rental.config (path resolution and source staging)."""

import gzip
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from amsterdam_rental.config import (
    SOURCE_FILES,
    PipelineConfig,
    ensure_workspace_prefix,
    resolve_catalog,
    stage_sources,
    workspace_repo_root,
)


class TestResolveCatalog:
    def test_explicit_catalog_wins(self):
        """An explicitly requested catalog is used even when the session has another one."""
        assert resolve_catalog("analytics", "workspace") == "analytics"

    def test_blank_falls_back_to_current(self):
        """A blank or whitespace catalog falls back to the session's current catalog."""
        assert resolve_catalog("  ", "workspace") == "workspace"
        assert resolve_catalog(None, "main") == "main"

    @pytest.mark.parametrize("current", ["hive_metastore", "spark_catalog", "", None])
    def test_non_uc_catalog_raises(self, current):
        """No usable Unity Catalog catalog → ValueError telling the user how to pass one."""
        with pytest.raises(ValueError, match="--var catalog="):
            resolve_catalog("", current)


class TestWorkspacePaths:
    def test_repo_root_from_notebook_path(self):
        """/Users/u/repo/notebooks/01_bronze → /Workspace/Users/u/repo."""
        assert workspace_repo_root("/Users/u/repo/notebooks/01_bronze") == "/Workspace/Users/u/repo"

    def test_prefix_not_doubled(self):
        """A path already under /Workspace is returned unchanged (minus trailing slash)."""
        assert ensure_workspace_prefix("/Workspace/Users/u/files/") == "/Workspace/Users/u/files"


class TestPipelineConfig:
    def test_databricks_paths_and_tables(self):
        """Databricks config builds the volume root and three-level table names from parameters."""
        cfg = PipelineConfig.for_databricks("/Users/u/files", "cat", "sch", "vol")
        assert cfg.on_databricks
        assert cfg.repo_root == "/Workspace/Users/u/files"
        assert cfg.root == "/Volumes/cat/sch/vol"
        assert cfg.source("airbnb.csv") == "/Volumes/cat/sch/vol/source/airbnb.csv"
        assert cfg.layer("gold") == "/Volumes/cat/sch/vol/gold"
        assert cfg.table("revenue_per_postcode") == "cat.sch.revenue_per_postcode"

    def test_blank_schema_and_volume_use_defaults(self):
        """Empty widget values fall back to the default schema and volume names."""
        cfg = PipelineConfig.for_databricks("/Users/u/files", "cat", "", " ")
        assert cfg.root == "/Volumes/cat/amsterdam_rental/pipeline"

    def test_local_paths(self, tmp_path):
        """Local config writes under data/output and has no catalog tables."""
        cfg = PipelineConfig.for_local(str(tmp_path))
        assert not cfg.on_databricks
        assert cfg.root == os.path.join(str(tmp_path), "data", "output")
        assert cfg.data_dir == os.path.join(str(tmp_path), "data")
        assert cfg.table("x") is None


class TestStageSources:
    def _make_sources(self, data_dir):
        for name, gz_rel in SOURCE_FILES.items():
            path = data_dir / gz_rel
            path.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(path, "wt") as f:
                f.write(f"content of {name}")

    def test_decompresses_every_source(self, tmp_path):
        """Each gzipped source is decompressed into source_dir under its expected file name."""
        self._make_sources(tmp_path / "data")
        staged = stage_sources(str(tmp_path / "data"), str(tmp_path / "out" / "source"))
        assert set(staged) == set(SOURCE_FILES)
        for name, path in staged.items():
            with open(path) as f:
                assert f.read() == f"content of {name}"

    def test_overwrites_stale_copy(self, tmp_path):
        """A previously staged file is replaced, so changed source data is picked up."""
        self._make_sources(tmp_path / "data")
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "airbnb.csv").write_text("stale")
        stage_sources(str(tmp_path / "data"), str(source_dir))
        assert (source_dir / "airbnb.csv").read_text() == "content of airbnb.csv"

    def test_missing_source_raises(self, tmp_path):
        """A missing source file fails with a message pointing at the bundle sync config."""
        with pytest.raises(FileNotFoundError, match="sync.include"):
            stage_sources(str(tmp_path), str(tmp_path / "source"))

    def test_real_repo_sources_are_valid_gzip(self):
        """Every source file shipped in data/ exists and is a readable gzip stream."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        for gz_rel in SOURCE_FILES.values():
            with gzip.open(os.path.join(data_dir, gz_rel), "rb") as f:
                assert f.read(64)
