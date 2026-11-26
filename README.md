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
python -m streamlit run app.py
```

The app currently displays a project introduction and implementation status.
The Python modules are placeholders; data loading, Neo4j integration, search,
and recommendations are not implemented yet. Launching this scaffold does not
require a dataset or a running database.

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
.env.example                       Planned local Neo4j configuration
requirements.txt                   Python dependencies
583 Project Proposal.pdf           Project scope
```

Keep UI code in `app.py` and data/recommendation logic in `steam_recommender`.
Add focused tests as behavior is implemented.

## Data and database

Place the Steam Game Dataset 2025 CSV from Kaggle in `data/raw/`. Start with
5,000–10,000 games as described in the proposal. Inspect the actual CSV schema
before implementing preprocessing or choosing how to interpret ratings.

The planned graph contains `Game`, `Genre`, `Tag`, `Developer`, and `Publisher`
nodes, linked by relationships such as `HAS_GENRE`, `HAS_TAG`, `DEVELOPED_BY`,
and `PUBLISHED_BY`.

For future database integration, use a local Neo4j instance and copy
`.env.example` to `.env`, replacing the password. The scaffold does not yet
read these settings or automatically load `.env`. Keep credentials and datasets
out of Git; the included `.gitignore` excludes them.
