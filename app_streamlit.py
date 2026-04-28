import streamlit as st
from backend_api import analyser_projet

st.set_page_config(layout="wide")

st.title("🌱 Carbon Design Assistant (APS/APD)")

chemin = st.text_input("Chemin du dossier client")

if st.button("Analyser le projet"):
    data, bilan = analyser_projet(chemin)

    st.subheader("📊 Résultats carbone")

    col1, col2, col3 = st.columns(3)

    col1.metric("Ic énergie", bilan["resume"]["ic_energie_kgco2_m2_an"])
    col2.metric("Ic bâtiment", bilan["resume"]["ic_batiment_kgco2_m2_an"])
    col3.metric("Ic total", bilan["resume"]["ic_total_kgco2_m2_an"])

    st.subheader("📁 Données projet")
    st.json(data)
