"""Search the imported Steam game catalog."""

import logging
import os

import streamlit as st
from neo4j.exceptions import DriverError, Neo4jError

from steam_recommender.graph import connect, list_genres, search_games


@st.cache_resource
def get_driver():
    return connect()


st.set_page_config(page_title="Steam Game Recommender", page_icon="🎮", layout="wide")
st.title("Steam Game Recommender")
st.write("Search games by name, genre, price, and player reviews.")

try:
    driver = get_driver()
    with driver.session(database=os.environ["NEO4J_DATABASE"]) as session:
        genres = session.execute_read(list_genres)

    with st.form("game_search"):
        name = st.text_input("Game name", placeholder="Search all games or enter part of a name")
        genre_column, price_column, rating_column = st.columns(3)
        with genre_column:
            genre = st.selectbox("Genre", [None, *genres], format_func=lambda value: value or "All genres")
        with price_column:
            max_price = st.number_input(
                "Maximum price", min_value=0.0, value=None, step=5.0,
                format="%.2f", placeholder="Any price",
                help="Set to 0 for free games. Prices are from the dataset snapshot, not live store prices.",
            )
        with rating_column:
            min_rating = st.number_input(
                "Minimum positive reviews (%)", min_value=0, max_value=100,
                value=None, step=5, placeholder="Any rating",
                help="Setting a minimum excludes games with an unknown rating, including when the minimum is 0%.",
            )
        st.form_submit_button("Search", type="primary")

    with driver.session(database=os.environ["NEO4J_DATABASE"]) as session:
        games = session.execute_read(
            search_games, name=name, genre=genre, max_price=max_price, min_rating=min_rating,
        )
except (DriverError, Neo4jError, OSError, ValueError):
    logging.getLogger(__name__).exception("Could not search the game catalog")
    st.error("Could not load games. Check that Neo4j is running and your .env connection settings are correct.")
    st.stop()

st.subheader("Search results")
if not games:
    st.info("No games match your search. Try a different name or fewer filters.")
else:
    if len(games) > 50:
        st.caption("Showing the first 50 matches, most reviewed first. Narrow your search to see more specific results.")
    else:
        st.caption(f"{len(games)} {'game' if len(games) == 1 else 'games'} found · Most reviewed first")
    rows = [
        {
            "Game": game["name"],
            "Genres": ", ".join(game["genres"]) or "Unknown",
            "Price": "Unknown" if game["price"] is None else ("Free" if game["price"] == 0 else f"{game['price']:.2f}"),
            "Positive reviews": "Unknown" if game["rating"] is None else f"{game['rating']}%",
            "Review count": game["reviews"],
            "Released": game["release_date"],
        }
        for game in games[:50]
    ]
    st.dataframe(rows, hide_index=True, width="stretch")
    st.caption("Prices and reviews reflect the March 2025 dataset. Unknown ratings are not treated as 0%.")
