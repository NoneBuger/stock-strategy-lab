"""Direct navigation entrypoint for fund analysis."""

import runpy
from pathlib import Path

import streamlit as st


st.session_state["_asset_page_type"] = "基金"
runpy.run_path(str(Path(__file__).with_name("fund_index_page.py")), run_name="__main__")
