# Steam Game Recommender

CPSC 583 project: explainable game recommendations using a Neo4j knowledge
graph of Steam games, genres, tags, developers, and publishers.

The initial scope is game search by genre, price, and rating, followed by
similarity-based recommendations with shared-attribute explanations. Multi-hop
discovery and adjustable ranking weights are potential extensions. No LLM is
planned. See `583 Project Proposal.pdf` for the proposal.

## Setup

Use Python 3.12. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The app searches the imported Neo4j catalog. Keep your instance running and
configure `.env`, then preprocess and import the data using the commands below
before opening the app. On a fresh checkout, follow [Data and database](#data-and-database)
and [Import into Neo4j](#import-into-neo4j) first; the datasets and credentials are
local and are not downloaded with the repository. Then launch:

```bash
python -m streamlit run app.py
```

Search matches part of a game name regardless of capitalization. Genre, maximum
price, and minimum positive-review percentage filters combine with the name
search. Leave numeric fields blank to apply no limit; a maximum price of zero
selects free games. Setting any minimum rating excludes unknown ratings, while
leaving it blank includes them. Click **Search** to apply changes.

Results show up to 50 games, ordered by total review count (highest first), then
name and game ID for stable ordering. Narrow the filters if more than 50 match.
Prices and reviews reflect the dataset snapshot, not current Steam store data.

Games tagged `Sexual Content`, `Nudity`, `Hentai`, or `NSFW` are hidden from search
and recommendations, including selection as a starting game. Genre choices also
exclude genres found only on hidden games. This is a tag-based filter; untagged
content cannot be identified by it. `Mature` and violence-related tags are not
excluded. The source files and Neo4j records remain intact; no reimport is needed.

## Similarity recommendations

Choose a game from **Find games similar to** below the search results. The app
finds games connected through shared tags, genres, or developers and shows the
top 10 matches. Submitted genre, price, and rating filters also apply to these
candidates; the name search only applies when finding the starting game.

For each attribute type, Jaccard similarity is the number of shared values divided
by the number of distinct values across both games. The score out of 100 is:

```text
60 × tag similarity + 30 × genre similarity + 10 × developer similarity
```

The weights are initial project choices, not learned preferences. Empty unions
contribute zero; missing attributes do not cause the remaining weights to be
rescaled. Tag votes and publishers do not affect this initial score. Prices and
ratings filter candidates rather than contribute points.

All eligible candidates are scored before selecting the top 10. The selected game
and zero-overlap games are excluded. Ties use review count (descending), name,
then app ID. Expand a result to see its shared attributes, overlap counts, and
score contributions. Scores measure attribute overlap, not a probability of
enjoyment. Recommendations cover only the imported sample.

## Demo walkthrough

These examples are present in the default 10,000-game sample:

1. Leave genre, price, and rating unrestricted. Search for `HELLDIVERS`, select
   `HELLDIVERS™ 2` (553850), and expand its first recommendation. The original
   `HELLDIVERS™ Dive Harder Edition` scores about 57.4/100. Explain the shared
   attributes and their separate contributions.
2. Search for `Darkest Dungeon` (262060) or `MiSide` (2527500) to show a different
   set of recommendations. The name search finds the starting game; recommended
   titles do not need to contain the same words.
3. Clear the name, choose Action, set maximum price to 0 and minimum positive
   reviews to 80, then click Search. Select one of the results and check that its
   recommendations are also free, Action games with at least 80% positive reviews.
4. Clear all filters and search for `Dark Man` (949720). This game has no scored
   attributes in the sample, so the app explains the missing data and returns no
   similar games instead of inventing matches.

On November 26, 2026, rankings, candidate counts, and explanation attributes for
these four starting games were checked against an independent calculation over
the complete processed sample, both without filters and with price <= 20 and
rating >= 80. All eight distinct cases matched. This checks implementation
correctness, not whether players would enjoy the recommendations.

Before presenting, review the top results for several games you know. Consider
whether the shared tags explain meaningful gameplay similarity and whether the
fixed weights need adjustment. The dataset is a historical sample; missing games,
missing attributes, and broad genres limit what the recommender can infer.

## Structure

```text
app.py                             Streamlit entry point
steam_recommender/
    data.py                        Dataset cleaning and normalization
    graph.py                       Neo4j import and queries
    recommendations.py             Similarity scoring and explanations
data/
    raw/                           Original CSV files (ignored by Git)
    processed/                     Cleaned data (ignored by Git)
.env.example                       Local Neo4j configuration template
requirements.txt                   Python dependencies
583 Project Proposal.pdf           Project scope
```

Keep UI code in `app.py` and data/recommendation logic in `steam_recommender`.
Add focused tests as behavior is implemented.

## Data and database

Download the [Steam Games Dataset from Kaggle](https://www.kaggle.com/datasets/artermiloff/steam-games-dataset?resource=download)
and extract it into `data/raw/`. Use `games_march2025_cleaned.csv`; the supplied
copy contains 89,618 games with unique IDs.
From the repository root, run:

```bash
python -m steam_recommender.data "data/raw/archive 2/games_march2025_cleaned.csv"
```

Adjust the path if your extracted directory has a different name. This validates
the selected columns across the source, then writes a reproducible uniform sample
of 10,000 games to `data/processed/games.jsonl` (seed 583, sorted by app ID).
Use `--limit 5000` for a smaller graph or `--output PATH` to change the destination.
Sampling does not require ratings or tags, so games with sparse metadata remain
represented. The source CSV is unchanged.

Each JSON line contains a game with its ID, name, release date, price, genres,
developers, publishers, tag-to-vote dictionary, positive/negative counts, and
total review percentage/count. Serialized lists and dictionaries are parsed as
Python literals, preserving names containing commas. Blank list entries are
removed (six source games have a blank publisher), and duplicate list names are
collapsed. Missing tags become `{}`;
missing review percentages/counts (`-1` in the CSV) become JSON `null`.
Actual zero prices and 0% ratings remain zero.

Use `pct_pos_total` (0–100) for the initial rating filter, keeping unavailable
ratings distinct from poor ratings. The supplied file has 36,419 missing total
review ratings. Its `user_score` is zero for 89,579 games, so preprocessing omits
that field. Positive/negative counts are retained separately without substituting
a different rating formula when `pct_pos_total` is missing.

Run the unit tests with:

```bash
python -m unittest discover -s tests
```

With Neo4j running and `.env` configured, run the database integration tests:

```bash
python -m unittest discover -s tests -p '*integration.py'
```

They check imports, updates, search filters, and recommendation candidates against the real
database. Their temporary graph changes are rolled back.

The graph contains `Game`, `Genre`, `Tag`, `Developer`, and `Publisher`
nodes, linked by relationships such as `HAS_GENRE`, `HAS_TAG`, `DEVELOPED_BY`,
and `PUBLISHED_BY`.

## Import into Neo4j

Start your local Neo4j instance. Copy `.env.example` to `.env` if you have not
already done so, then set the URI, username, password, and database name to match
your instance. Keep credentials and datasets out of Git; `.gitignore` excludes
them. The importer reads the repository's `.env`; exported environment variables
take precedence. Values containing spaces or `#` should be quoted.

After installing requirements and running preprocessing, import the sample:

```bash
python -m steam_recommender.graph
```

An optional positional argument selects another preprocessed JSONL file. The
importer creates uniqueness constraints for game IDs and attribute names, then
imports 500 games per transaction. It preserves tag votes on `HAS_TAG` relationships
and stores release dates as Neo4j dates. Missing ratings remain absent properties,
which Cypher reads as `null`; zero prices and ratings are preserved.

Rerunning updates matching games without duplicating nodes or relationships.
For each imported game, its four types of attribute relationships are replaced
to match the input. Games outside the input and unrelated relationship types are
untouched. Unused attribute nodes are retained. If a batch fails, earlier batches
remain committed; fix the error and rerun the command to finish the import.

In Neo4j Desktop's Query tool, select your database and check the import:

```cypher
MATCH (game:Game)
RETURN count(game) AS games;
```

To view a small part of the graph:

```cypher
MATCH (game:Game)-[relationship]->(attribute)
RETURN game, relationship, attribute
LIMIT 50;
```
