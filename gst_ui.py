"""
gst_ui.py
---------
One-page Streamlit dashboard:
  • shows 5 document types as a multi-select
  • “Start download” button calls run_automation for each user in Data.xlsx
Run with:   streamlit run gst_ui.py
"""
from pathlib import Path
import pandas as pd
import streamlit as st
from downloader import run_automation

# ────────────────────────────────────────────────────────────────────────────────
# Settings
# ────────────────────────────────────────────────────────────────────────────────
DATA_FILE = Path("Data.xlsx")     # side-by-side with this script
DOWNLOADS = Path("downloads")     # root downloads folder

DOC_LABELS = {
    "GSTR-1"                 : "gstr1",
    "GSTR-3B"                : "gstr3b",
    "Electronic Cash Ledger" : "cash",
    "Electronic Credit Ledger": "credit",
    "Credit Reversal"        : "reversal",
}

# ────────────────────────────────────────────────────────────────────────────────
# Load spreadsheet
# ────────────────────────────────────────────────────────────────────────────────
df = pd.read_excel(DATA_FILE, engine="openpyxl")

# ────────────────────────────────────────────────────────────────────────────────
# Build UI
# ────────────────────────────────────────────────────────────────────────────────
st.title("GST Portal Downloader")

# ← removed user multiselect entirely

# ① document list
st.markdown("### 1️⃣  Select documents")
picked_docs = st.multiselect(
    "Choose one or more documents:",
    options=list(DOC_LABELS.keys())
)

# ② run button
go = st.button(
    "🚀  Start download for ALL users",
    disabled=(not picked_docs)
)

# ────────────────────────────────────────────────────────────────────────────────
# Action
# ────────────────────────────────────────────────────────────────────────────────
if go:
    with st.spinner("Running Selenium robots for every user…"):
        tasks = [DOC_LABELS[d] for d in picked_docs]

        # Loop over every row in Data.xlsx
        for idx, row in df.iterrows():
            run_automation(row, tasks, DOWNLOADS)

        st.success("All downloads finished for all users! 🎉")
        st.balloons()

