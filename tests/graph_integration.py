"""Run explicitly against the configured Neo4j database; all fixture writes roll back."""

import os
import unittest
from uuid import uuid4

from steam_recommender.graph import connect, get_recommendation_data, import_batch, list_genres, search_games
from steam_recommender.recommendations import recommend_games


class GraphImportTest(unittest.TestCase):
    def test_recommendations_exclude_self_and_apply_filters_without_losing_attributes(self):
        token = uuid4().hex
        appid = int(token[:15], 16)
        genre, tag, developer, publisher = [f"{label} {token}" for label in ["Genre", "Tag", "Developer", "Publisher"]]
        source = {
            "appid": appid, "name": f"Source {token}", "release_date": "2025-01-01",
            "price": 10, "positive": 8, "negative": 2, "pct_pos_total": 80,
            "num_reviews_total": 10, "genres": [genre], "tags": {tag: 50},
            "developers": [developer], "publishers": [publisher],
        }
        games = [
            source,
            dict(source, appid=appid+1, name="Perfect match", tags={tag: 1}),
            dict(source, appid=appid+2, name="Free zero-rated", price=0, pct_pos_total=0, tags={}, developers=[]),
            dict(source, appid=appid+3, name="Unknown rating", price=0, pct_pos_total=None, num_reviews_total=None),
            dict(source, appid=appid+4, name="Expensive", price=20),
            dict(source, appid=appid+5, name="Publisher only", genres=[], tags={}, developers=[]),
        ]
        hidden_genre = f"Hidden genre {token}"
        for offset, excluded_tag in enumerate(["Sexual Content", "Nudity", "Hentai", "NSFW"], start=6):
            games.append(dict(
                source, appid=appid+offset, name=f"Hidden {token} {offset}",
                tags={tag: 1, excluded_tag: 1}, genres=[genre, hidden_genre],
            ))
        games[2]["tags"] = {"Mature": 1}
        with connect() as driver:
            with driver.session(database=os.environ["NEO4J_DATABASE"]) as session:
                with session.begin_transaction() as tx:
                    existing = tx.run(
                        "MATCH (g:Game) WHERE g.appid IN $ids RETURN count(g) AS count",
                        ids=[game["appid"] for game in games],
                    ).single()["count"]
                    self.assertEqual(existing, 0)
                    try:
                        import_batch(tx, games)
                        self.assertEqual(search_games(tx, name=f"Hidden {token}"), [])
                        self.assertNotIn(hidden_genre, list_genres(tx))
                        self.assertIn(appid+2, [game["appid"] for game in search_games(tx, genre=genre)])
                        for hidden in games[6:]:
                            with self.assertRaisesRegex(ValueError, "excluded by the content filter"):
                                get_recommendation_data(tx, hidden["appid"])
                        selected, candidates = get_recommendation_data(tx, appid)
                        self.assertEqual({game["appid"] for game in candidates}, {appid+1, appid+2, appid+3, appid+4})
                        self.assertEqual(len(candidates), 4)
                        selected, filtered = get_recommendation_data(tx, appid, genre=genre, max_price=10, min_rating=80)
                        ranked = recommend_games(selected, filtered)
                        self.assertEqual([game["appid"] for game in ranked], [appid+1])
                        self.assertEqual(ranked[0]["score"], 100)
                        _, free = get_recommendation_data(tx, appid, max_price=0)
                        self.assertEqual({game["appid"] for game in free}, {appid+2, appid+3})
                        _, rated_free = get_recommendation_data(tx, appid, max_price=0, min_rating=0)
                        self.assertEqual([game["appid"] for game in rated_free], [appid+2])
                        _, wrong_genre = get_recommendation_data(tx, appid, genre=f"Missing {token}")
                        self.assertEqual(wrong_genre, [])
                        sparse_source, sparse_candidates = get_recommendation_data(tx, appid+5)
                        self.assertEqual(recommend_games(sparse_source, sparse_candidates), [])
                    finally:
                        tx.rollback()

    def test_search_combines_filters_and_distinguishes_unknown_from_zero(self):
        token = uuid4().hex
        appid = int(token[:15], 16)
        genre = f"Genre {token}"
        common = {
            "release_date": "2025-01-01", "positive": 1, "negative": 1,
            "genres": [genre], "tags": {}, "developers": [], "publishers": [],
        }
        games = [
            dict(common, appid=appid, name=f"{token} Alpha", price=10, pct_pos_total=80, num_reviews_total=100),
            dict(common, appid=appid+1, name=f"{token} Free", price=0, pct_pos_total=0, num_reviews_total=10),
            dict(common, appid=appid+2, name=f"{token} Unknown", price=0, pct_pos_total=None, num_reviews_total=None),
            dict(common, appid=appid+3, name=f"{token} Expensive", price=20, pct_pos_total=90, num_reviews_total=200),
            dict(common, appid=appid+4, name=f"{token} Other", price=5, pct_pos_total=95, num_reviews_total=300, genres=[]),
        ]
        with connect() as driver:
            with driver.session(database=os.environ["NEO4J_DATABASE"]) as session:
                with session.begin_transaction() as tx:
                    existing = tx.run(
                        "MATCH (g:Game) WHERE g.appid IN $ids RETURN count(g) AS count",
                        ids=[game["appid"] for game in games],
                    ).single()["count"]
                    self.assertEqual(existing, 0)
                    try:
                        import_batch(tx, games)
                        self.assertIn(genre, list_genres(tx))
                        results = search_games(tx, name=f"  {token.upper()}  ", genre=genre, max_price=10, min_rating=80)
                        self.assertEqual([game["appid"] for game in results], [appid])
                        self.assertEqual(results[0]["genres"], [genre])
                        free = search_games(tx, name=token, max_price=0)
                        self.assertEqual([game["appid"] for game in free], [appid+1, appid+2])
                        rated_free = search_games(tx, name=token, max_price=0, min_rating=0)
                        self.assertEqual([game["appid"] for game in rated_free], [appid+1])
                        limited = search_games(tx, name=token, limit=1)
                        self.assertEqual([game["appid"] for game in limited], [appid+4])
                        self.assertEqual(search_games(tx, name=f"{token}' OR true //"), [])
                    finally:
                        tx.rollback()

    def test_reimport_and_updates_preserve_graph_data(self):
        token = uuid4().hex
        appid = int(token[:15], 16)
        game = {
            "appid": appid, "name": f"Import test {token}",
            "release_date": "2025-01-01", "price": 0,
            "positive": 0, "negative": 10, "pct_pos_total": 0,
            "num_reviews_total": 10, "genres": [f"Genre {token}"],
            "tags": {f"Tag {token}": 12},
            "developers": [f"Studio, Inc. {token}"], "publishers": [],
        }
        other = dict(game, appid=appid + 1, name=f"Other {token}", tags={})
        with connect() as driver:
            with driver.session(database=os.environ["NEO4J_DATABASE"]) as session:
                with session.begin_transaction() as tx:
                    # Avoid touching existing games, even in the unlikely event of an ID collision.
                    existing = tx.run(
                        "MATCH (g:Game) WHERE g.appid IN $ids RETURN count(g) AS count",
                        ids=[appid, appid + 1],
                    ).single()["count"]
                    self.assertEqual(existing, 0)
                    try:
                        import_batch(tx, [game, other])
                        import_batch(tx, [game, other])
                        result = tx.run(
                            "MATCH (g:Game {appid: $appid}) "
                            "OPTIONAL MATCH (g)-[r]->() "
                            "RETURN g.price AS price, g.pct_pos_total AS rating, "
                            "toString(g.release_date) AS released, count(r) AS links",
                            appid=appid,
                        ).single()
                        self.assertEqual(dict(result), {
                            "price": 0, "rating": 0, "released": "2025-01-01", "links": 3,
                        })
                        votes = tx.run(
                            "MATCH (:Game {appid: $appid})-[r:HAS_TAG]->() RETURN r.votes AS votes",
                            appid=appid,
                        ).single()["votes"]
                        self.assertEqual(votes, 12)
                        shared = tx.run(
                            "MATCH (:Game {appid: $first})-[:HAS_GENRE]->(genre)"
                            "<-[:HAS_GENRE]-(:Game {appid: $second}) RETURN count(genre) AS count",
                            first=appid, second=appid + 1,
                        ).single()["count"]
                        self.assertEqual(shared, 1)

                        # Updating an imported game clears removed attributes and unknown ratings.
                        updated = dict(game, tags={}, genres=[], pct_pos_total=None, num_reviews_total=None)
                        import_batch(tx, [updated])
                        result = tx.run(
                            "MATCH (g:Game {appid: $appid}) OPTIONAL MATCH (g)-[r]->() "
                            "RETURN g.pct_pos_total AS rating, g.num_reviews_total AS reviews, "
                            "count(r) AS links",
                            appid=appid,
                        ).single()
                        self.assertEqual(dict(result), {"rating": None, "reviews": None, "links": 1})
                        remaining = tx.run(
                            "MATCH (:Game {appid: $appid})-[r]->() RETURN count(r) AS links",
                            appid=appid + 1,
                        ).single()["links"]
                        self.assertEqual(remaining, 2)
                    finally:
                        tx.rollback()
