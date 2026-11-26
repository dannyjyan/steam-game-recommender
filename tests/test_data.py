"""Regression coverage for the source dataset's nested values and missing ratings."""

import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from steam_recommender.data import prepare_games


class PrepareGamesTest(unittest.TestCase):
    def test_nested_attributes_and_missing_ratings_survive_json_export(self):
        common = {
            "name": " Test Game ", "release_date": "2025-01-01", "price": 0,
            "genres": "['Action', 'Action']", "developers": "['Studio, Inc.']",
            "publishers": "['']", "positive": 0, "negative": 10,
        }
        rows = [
            dict(common, appid=2, tags="[]", pct_pos_total=-1, num_reviews_total=-1),
            dict(common, appid=1, tags="{'Action': 12}", pct_pos_total=0, num_reviews_total=10),
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "games.csv"
            pd.DataFrame(rows).to_csv(source, index=False)
            result = prepare_games(source)
            records = [json.loads(line) for line in result.to_json(orient="records", lines=True).splitlines()]

        self.assertEqual([row["appid"] for row in records], [1, 2])
        self.assertEqual(records[0]["name"], "Test Game")
        self.assertEqual(records[0]["genres"], ["Action"])
        self.assertEqual(records[0]["developers"], ["Studio, Inc."])
        self.assertEqual(records[0]["publishers"], [])
        self.assertEqual(records[0]["tags"], {"Action": 12})
        self.assertEqual(records[0]["price"], 0)
        self.assertEqual(records[0]["pct_pos_total"], 0)
        self.assertEqual(records[0]["num_reviews_total"], 10)
        self.assertEqual(records[1]["tags"], {})
        self.assertIsNone(records[1]["pct_pos_total"])
        self.assertIsNone(records[1]["num_reviews_total"])
