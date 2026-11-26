"""Check recommendation scores, explanations, and ranking behavior."""

import unittest

from steam_recommender.recommendations import recommend_games


class RecommendationsTest(unittest.TestCase):
    def test_score_and_explanation_use_distinct_attribute_overlap(self):
        source = {
            "appid": 1, "tags": ["Survival", "Co-op", "Crafting"],
            "genres": ["Action", "Adventure"], "developers": ["Studio A"],
        }
        candidate = {
            "appid": 2, "name": "Candidate", "reviews": 10,
            "tags": ["Survival", "Co-op", "Open World", "Co-op"],
            "genres": ["Action", "Adventure"], "developers": ["Studio B"],
        }
        result = recommend_games(source, [candidate])[0]
        self.assertAlmostEqual(result["score"], 60)
        self.assertEqual(result["breakdown"]["tags"], {
            "shared": ["Co-op", "Survival"], "union_count": 4, "points": 30,
        })
        self.assertEqual(result["breakdown"]["genres"]["points"], 30)
        self.assertEqual(result["breakdown"]["developers"]["points"], 0)
        self.assertAlmostEqual(result["score"], sum(part["points"] for part in result["breakdown"].values()))

    def test_rank_before_limiting_and_no_points_for_missing_data(self):
        source = {"appid": 1, "tags": [], "genres": ["Action"], "developers": []}
        partial = {"appid": 2, "name": "Popular", "reviews": 1000, "tags": [], "genres": ["Action", "RPG"], "developers": []}
        match = dict(partial, appid=3, name="Match", reviews=None, genres=["Action"])
        tied = dict(match, appid=4, name="Reviewed match", reviews=1)
        no_overlap = dict(match, appid=5, genres=[])
        results = recommend_games(source, [source, partial, no_overlap, match, tied], limit=2)
        self.assertEqual([game["appid"] for game in results], [4, 3])
        self.assertEqual([game["score"] for game in results], [30, 30])
        self.assertEqual(results[0]["breakdown"]["tags"]["points"], 0)
        self.assertEqual(recommend_games(dict(source, genres=[]), [no_overlap]), [])
