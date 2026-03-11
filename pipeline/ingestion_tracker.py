"""Tracks ingestion state for incremental updates."""

import json
import os
from datetime import datetime, timezone


class IngestionTracker:
    """Persists last-seen timestamps/hashes per source item to skip unchanged content."""

    def __init__(self, state_file: str = "ingestion_state.json"):
        self.state_file = state_file
        self.state = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                return json.load(f)
        return {}

    def save(self) -> None:
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def _key(self, source_type: str, identifier: str) -> str:
        return f"{source_type}::{identifier}"

    def has_changed(self, source_type: str, identifier: str, fingerprint: str) -> bool:
        """Check if an item has changed since last ingestion.

        fingerprint is typically last_modified timestamp or file SHA.
        Returns True if the item is new or has changed.
        """
        key = self._key(source_type, identifier)
        stored = self.state.get(key, {}).get("fingerprint")
        return stored != fingerprint

    def mark_ingested(self, source_type: str, identifier: str, fingerprint: str) -> None:
        """Record that an item has been ingested."""
        key = self._key(source_type, identifier)
        self.state[key] = {
            "fingerprint": fingerprint,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_all_keys(self, source_type: str) -> set[str]:
        """Get all tracked identifiers for a source type."""
        prefix = f"{source_type}::"
        return {k[len(prefix):] for k in self.state if k.startswith(prefix)}

    def remove(self, source_type: str, identifier: str) -> None:
        """Remove tracking for a deleted item."""
        key = self._key(source_type, identifier)
        self.state.pop(key, None)

    def clear(self, source_type: str | None = None) -> None:
        """Clear state, optionally for a specific source type only."""
        if source_type is None:
            self.state = {}
        else:
            prefix = f"{source_type}::"
            self.state = {k: v for k, v in self.state.items() if not k.startswith(prefix)}
        self.save()
