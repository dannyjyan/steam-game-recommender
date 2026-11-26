"""Search the imported Steam game catalog."""

import logging
import os

import streamlit as st
from neo4j.exceptions import DriverError, Neo4jError

from steam_recommender.graph import connect, get_recommendation_data, list_genres, search_games
from steam_recommender.recommendations import WEIGHTS, recommend_games


@st.cache_resource
def get_driver():
    return connect()


st.set_page_config(page_title="Steam Game Recommender", page_icon="🎮", layout="wide")
st.title("Steam Game Recommender")
st.write("Find a game you enjoy, then discover similar games with explanations for each match.")

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

    st.subheader("Similar games")
    game_names = {game["appid"]: game["name"] for game in games[:50]}
    if st.session_state.get("selected_game") not in game_names:
        st.session_state["selected_game"] = None
    selected = st.selectbox(
        "Find games similar to", list(game_names), index=None, key="selected_game",
        placeholder="Choose a game from your search results",
        format_func=lambda appid: f"{game_names[appid]} (App ID {appid})",
    )
    st.caption("Recommendations use your submitted genre, price, and rating filters. The name search only finds the starting game.")
    if selected is not None:
        try:
            with st.spinner("Finding similar games…"):
                with driver.session(database=os.environ["NEO4J_DATABASE"]) as session:
                    source, candidates = session.execute_read(
                        get_recommendation_data, selected, genre=genre,
                        max_price=max_price, min_rating=min_rating,
                    )
                recommendations = recommend_games(source, candidates)
        except (DriverError, Neo4jError, OSError, ValueError):
            logging.getLogger(__name__).exception("Could not load similar games")
            st.error("Could not load recommendations. Check your database connection and search again.")
            st.stop()

        st.caption("Similarity: tags up to 60 points, genres up to 30, developers up to 10. Scores measure overlap, not the probability you will enjoy a game.")
        if any(not source[field] for field in WEIGHTS):
            st.info("This game has incomplete attribute data. Missing attributes contribute no similarity points, so scores may be lower.")
        if not recommendations:
            st.info("No similar games match these filters. Try fewer filters or choose another starting game.")
        else:
            st.write(f"Top {len(recommendations)} matches")
            for rank, game in enumerate(recommendations, start=1):
                with st.expander(f"{rank}. {game['name']} — {game['score']:.1f}/100"):
                    price = "Unknown" if game["price"] is None else ("Free" if game["price"] == 0 else f"{game['price']:.2f}")
                    rating = "Unknown" if game["rating"] is None else f"{game['rating']}%"
                    st.write(f"Price: {price} · Positive reviews: {rating}")
                    st.dataframe([
                        {
                            "Attribute": field.capitalize(),
                            "Shared": ", ".join(part["shared"]) or "None",
                            "Shared / combined distinct": f"{len(part['shared'])} / {part['union_count']}",
                            "Points": round(part["points"], 2),
                            "Maximum points": WEIGHTS[field],
                        }
                        for field, part in game["breakdown"].items()
                    ], hide_index=True, width="stretch")
                    st.caption("Each contribution is shared ÷ combined distinct attributes × maximum points. An empty attribute set contributes 0. Displayed values are rounded.")
