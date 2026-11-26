"""Neo4j connections, graph import, and game search."""

import argparse
import json
import math
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase


IMPORT_QUERY = """
UNWIND $games AS row
MERGE (game:Game {appid: row.appid})
SET game.name = row.name,
    game.release_date = date(row.release_date),
    game.price = row.price,
    game.positive = row.positive,
    game.negative = row.negative,
    game.pct_pos_total = row.pct_pos_total,
    game.num_reviews_total = row.num_reviews_total
WITH game, row
OPTIONAL MATCH (game)-[old:HAS_GENRE|HAS_TAG|DEVELOPED_BY|PUBLISHED_BY]->()
DELETE old
WITH DISTINCT game, row
FOREACH (name IN row.genres |
    MERGE (genre:Genre {name: name})
    MERGE (game)-[:HAS_GENRE]->(genre)
)
FOREACH (name IN keys(row.tags) |
    MERGE (tag:Tag {name: name})
    MERGE (game)-[link:HAS_TAG]->(tag)
    SET link.votes = row.tags[name]
)
FOREACH (name IN row.developers |
    MERGE (developer:Developer {name: name})
    MERGE (game)-[:DEVELOPED_BY]->(developer)
)
FOREACH (name IN row.publishers |
    MERGE (publisher:Publisher {name: name})
    MERGE (game)-[:PUBLISHED_BY]->(publisher)
)
"""


def connect():
    """Read local settings; exported environment variables take precedence."""
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", interpolate=False)
    required = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise ValueError(f"Set {', '.join(missing)} in .env or your environment")
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )
    return driver


def list_genres(tx):
    """List genres attached to games, excluding unused attribute nodes."""
    return [record["name"] for record in tx.run(
        "MATCH (:Game)-[:HAS_GENRE]->(genre:Genre) "
        "RETURN DISTINCT genre.name AS name ORDER BY name"
    )]


def search_games(tx, name="", genre=None, max_price=None, min_rating=None, limit=51):
    """Combine optional filters; missing ratings only pass when no minimum is set."""
    if max_price is not None and (not math.isfinite(max_price) or max_price < 0):
        raise ValueError("Maximum price must be finite and nonnegative")
    if min_rating is not None and not 0 <= min_rating <= 100:
        raise ValueError("Minimum rating must be between 0 and 100")
    if type(limit) is not int or limit < 1:
        raise ValueError("Result limit must be a positive integer")
    result = tx.run(
        """
        MATCH (game:Game)
        WHERE toLower(game.name) CONTAINS toLower($name)
          AND ($genre IS NULL OR EXISTS {
              MATCH (game)-[:HAS_GENRE]->(:Genre {name: $genre})
          })
          AND ($max_price IS NULL OR game.price <= $max_price)
          AND ($min_rating IS NULL OR game.pct_pos_total >= $min_rating)
        WITH game
        ORDER BY coalesce(game.num_reviews_total, -1) DESC,
                 toLower(game.name), game.appid
        LIMIT $limit
        OPTIONAL MATCH (game)-[:HAS_GENRE]->(genre:Genre)
        WITH game, genre ORDER BY genre.name
        RETURN game.appid AS appid, game.name AS name, game.price AS price,
               game.pct_pos_total AS rating, game.num_reviews_total AS reviews,
               toString(game.release_date) AS release_date,
               collect(genre.name) AS genres
        ORDER BY coalesce(reviews, -1) DESC, toLower(name), appid
        """,
        name=name.strip(), genre=genre, max_price=max_price,
        min_rating=min_rating, limit=limit,
    )
    return result.data()


def load_games(source: Path) -> list[dict]:
    """Read the prepared file before writing any batches to the database."""
    games = []
    seen = set()
    required = {
        "appid", "name", "release_date", "price", "positive", "negative",
        "pct_pos_total", "num_reviews_total", "genres", "tags", "developers",
        "publishers",
    }
    with source.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                game = json.loads(line)
                if not isinstance(game, dict) or not required.issubset(game):
                    raise ValueError("expected a complete preprocessed game record")
                appid = game["appid"]
                if type(appid) is not int or appid <= 0 or appid in seen:
                    raise ValueError("game IDs must be positive, unique integers")
                if not isinstance(game["tags"], dict) or any(
                    not isinstance(game[field], list)
                    for field in ["genres", "developers", "publishers"]
                ):
                    raise ValueError("expected parsed attribute lists and a tag dictionary")
                seen.add(appid)
                games.append(game)
            except ValueError as exc:
                raise ValueError(f"{source}, line {line_number}: {exc}") from exc
    if not games:
        raise ValueError(f"{source} contains no games; run preprocessing first")
    return games


def create_constraints(session):
    # Labels and property names are fixed here, never taken from input data.
    for label, key in [
        ("Game", "appid"), ("Genre", "name"), ("Tag", "name"),
        ("Developer", "name"), ("Publisher", "name"),
    ]:
        session.run(
            f"CREATE CONSTRAINT {label.lower()}_{key}_unique IF NOT EXISTS "
            f"FOR (node:{label}) REQUIRE node.{key} IS UNIQUE"
        ).consume()


def import_batch(tx, games):
    """Update games and their attribute relationships in one transaction."""
    tx.run(IMPORT_QUERY, games=games).consume()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=Path("data/processed/games.jsonl"))
    args = parser.parse_args()
    games = load_games(args.source)
    with connect() as driver:
        driver.verify_connectivity()
        with driver.session(database=os.environ["NEO4J_DATABASE"]) as session:
            create_constraints(session)
            for start in range(0, len(games), 500):
                batch = games[start:start + 500]
                session.execute_write(import_batch, batch)
                print(f"Imported {start + len(batch):,}/{len(games):,} games", flush=True)
            count = session.run("MATCH (game:Game) RETURN count(game) AS count").single()["count"]
            print(f"Import complete. Database contains {count:,} Game nodes.")


if __name__ == "__main__":
    main()
