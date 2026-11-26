"""Prepare the March 2025 Steam CSV as JSON Lines for graph import."""

import argparse
import ast
from pathlib import Path

import pandas as pd


COLUMNS = [
    "appid", "name", "release_date", "price", "genres", "tags",
    "developers", "publishers", "positive", "negative",
    "pct_pos_total", "num_reviews_total",
]


def parse_attributes(value: str, column: str, appid: int):
    """Parse CSV Python literals without splitting names that contain commas."""
    try:
        parsed = ast.literal_eval(value)
        if column == "tags":
            # The source uses [] for games without tag votes.
            if parsed == []:
                return {}
            if not isinstance(parsed, dict) or any(
                not isinstance(tag, str) or not tag.strip()
                or type(votes) is not int or votes < 0
                for tag, votes in parsed.items()
            ):
                raise ValueError("expected a dictionary of tag names and vote counts")
            return parsed
        if not isinstance(parsed, list) or any(
            not isinstance(item, str) for item in parsed
        ):
            raise ValueError("expected a list of names")
        return list(dict.fromkeys(item.strip() for item in parsed if item.strip()))
    except (ValueError, SyntaxError) as exc:
        raise ValueError(f"Game {appid}: invalid {column}: {exc}") from exc


def prepare_games(source: Path, limit: int = 10_000) -> pd.DataFrame:
    """Validate the source and select a deterministic, uniform game sample."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    games = pd.read_csv(source, usecols=COLUMNS, keep_default_na=False)
    for column in ["appid", "positive", "negative", "pct_pos_total", "num_reviews_total"]:
        values = pd.to_numeric(games[column], errors="raise")
        if values.isna().any() or (values % 1 != 0).any():
            raise ValueError(f"{column} must contain integers")
        games[column] = values.astype("int64")
    if games.appid.le(0).any() or games.appid.duplicated().any():
        raise ValueError("Game IDs must be positive and unique")
    games["name"] = games.name.str.strip()
    if games.name.eq("").any():
        raise ValueError("Game names must not be blank")
    games["price"] = pd.to_numeric(games.price, errors="raise")
    if (~games.price.between(0, float("inf"), inclusive="left")).any():
        raise ValueError("Prices must be finite and nonnegative")
    games["release_date"] = pd.to_datetime(
        games.release_date, format="%Y-%m-%d", errors="raise"
    ).dt.strftime("%Y-%m-%d")
    if games.release_date.isna().any():
        raise ValueError("Release dates must not be missing")
    if games[["positive", "negative"]].lt(0).any().any():
        raise ValueError("Positive and negative review counts must be nonnegative")
    if (~games.pct_pos_total.between(-1, 100)).any() or games.num_reviews_total.lt(-1).any():
        raise ValueError("Invalid total review percentage or count")

    for column in ["genres", "tags", "developers", "publishers"]:
        games[column] = [
            parse_attributes(value, column, appid)
            for appid, value in zip(games.appid, games[column])
        ]
    # Preserve genuine 0% ratings; -1 denotes unavailable data in this source.
    for column in ["pct_pos_total", "num_reviews_total"]:
        games[column] = games[column].mask(games[column].eq(-1)).astype("Int64")

    games = games.sort_values("appid")
    if len(games) > limit:
        games = games.sample(n=limit, random_state=583)
    return games.sort_values("appid").reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Path to games_march2025_cleaned.csv")
    parser.add_argument("--limit", type=int, default=10_000)
    parser.add_argument("--output", type=Path, default=Path("data/processed/games.jsonl"))
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error("Output must not overwrite the source CSV")
    games = prepare_games(args.source, args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    games.to_json(args.output, orient="records", lines=True, force_ascii=False)
    print(f"Wrote {len(games):,} games to {args.output}")
    print(f"Missing total review ratings: {games.pct_pos_total.isna().sum():,}")
    print(f"Games without tags: {games.tags.map(len).eq(0).sum():,}")


if __name__ == "__main__":
    main()
