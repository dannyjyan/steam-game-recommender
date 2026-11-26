"""Streamlit entry point for the Steam game recommender."""

import streamlit as st

st.set_page_config(page_title="Steam Game Recommender", page_icon="🎮")
st.title("Steam Game Recommender")
st.write("Discover similar games and understand why they are recommended.")
st.info(
    "Project scaffold: dataset loading, graph queries, and recommendations "
    "have not been implemented yet."
)
