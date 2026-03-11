"""Tests for the ingestion tracker."""

import json
import os
import tempfile

from pipeline.ingestion_tracker import IngestionTracker


class TestIngestionTracker:
    def _make_tracker(self, tmp_path):
        state_file = os.path.join(tmp_path, "test_state.json")
        return IngestionTracker(state_file=state_file)

    def test_new_item_has_changed(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        assert tracker.has_changed("confluence", "page-1", "2025-01-01") is True

    def test_unchanged_item(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.mark_ingested("confluence", "page-1", "2025-01-01")
        assert tracker.has_changed("confluence", "page-1", "2025-01-01") is False

    def test_modified_item(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.mark_ingested("confluence", "page-1", "2025-01-01")
        assert tracker.has_changed("confluence", "page-1", "2025-06-15") is True

    def test_save_and_reload(self, tmp_path):
        state_file = os.path.join(tmp_path, "test_state.json")
        tracker = IngestionTracker(state_file=state_file)
        tracker.mark_ingested("confluence", "page-1", "2025-01-01")
        tracker.save()

        tracker2 = IngestionTracker(state_file=state_file)
        assert tracker2.has_changed("confluence", "page-1", "2025-01-01") is False

    def test_get_all_keys(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.mark_ingested("confluence", "page-1", "fp1")
        tracker.mark_ingested("confluence", "page-2", "fp2")
        tracker.mark_ingested("github_code", "repo/file.cs", "fp3")

        keys = tracker.get_all_keys("confluence")
        assert keys == {"page-1", "page-2"}

    def test_remove(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.mark_ingested("confluence", "page-1", "fp1")
        tracker.remove("confluence", "page-1")
        assert tracker.has_changed("confluence", "page-1", "fp1") is True

    def test_clear_all(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.mark_ingested("confluence", "page-1", "fp1")
        tracker.mark_ingested("github_code", "file-1", "fp2")
        tracker.clear()
        assert tracker.state == {}

    def test_clear_by_source(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.mark_ingested("confluence", "page-1", "fp1")
        tracker.mark_ingested("github_code", "file-1", "fp2")
        tracker.clear("confluence")
        assert tracker.has_changed("confluence", "page-1", "fp1") is True
        assert tracker.has_changed("github_code", "file-1", "fp2") is False

    def test_different_source_types_independent(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.mark_ingested("confluence", "item-1", "fp1")
        tracker.mark_ingested("github_code", "item-1", "fp2")
        # Same identifier but different source types are independent
        assert tracker.has_changed("confluence", "item-1", "fp1") is False
        assert tracker.has_changed("github_code", "item-1", "fp2") is False
        assert tracker.has_changed("github_docs", "item-1", "fp1") is True
