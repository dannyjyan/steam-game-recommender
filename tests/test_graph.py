"""Validate prepared input before the importer starts database writes."""

import json
from pathlib import Path
import tempfile
import unittest

from steam_recommender.graph import load_games


class LoadGamesTest(unittest.TestCase):
    def test_rejects_duplicate_ids_before_import(self):
        game = {
            "appid": 1, "name": "Game", "release_date": "2025-01-01", "price": 0,
            "positive": 0, "negative": 0, "pct_pos_total": None,
            "num_reviews_total": None, "genres": [], "tags": {},
            "developers": [], "publishers": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "games.jsonl"
            source.write_text((json.dumps(game) + "\n") * 2, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "line 2: game IDs must be positive, unique integers"):
                load_games(source)
