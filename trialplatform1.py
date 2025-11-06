import streamlit as st
import pandas as pd

COLUMNS_REQUIRED = [
    "company", "nace", "ebit", "employees", "net income", "capex", "d&a",
    "changes in wc", "lt debt", "st debt", "sh equity", "capital equity"
]

def normalize_columns(df):
    # Try to map user file to required columns. Strict: looks for substring matches.
    lower_cols = [c.lower() for c in df.columns]
    col_map = {}
    for required in COLUMNS_REQUIRED:
        for i, col in enumerate(lower_cols):
            if required in col.replace("_", " "):
                col_map[df.columns[i]] = required
                break
    return df.rename(columns=col_map)

def load_db():
    file = st.file_uploader("Upload Excel DB", type=["xlsx"])
    if not file:
        st.warning("Please upload an Excel database with the required columns.")
        return None
    df = pd.read_excel(file)
    df = normalize_columns(df)
    missing = [c for c in COLUMNS_REQUIRED if c not in df.columns]
    if missing:
        st.error(f"Missing columns: {', '.join(missing)}")
        return None
    st.success(f"Loaded company database with {len(df)} rows.")
    if st.checkbox("Preview data", False):
        st.dataframe(df.head())
    return df

def show_search(df):
    st.write("### Company Information Search")
    name_query = st.text_input("Search company name (case-insensitive, substring allowed)")
    if not name_query:
        return
    matches = df[df["company"].str.lower().str.contains(name_query.lower(), na=False)]
    if matches.empty:
        st.warning("No companies found.")
        return
    for i, r in matches.iterrows():
        st.markdown("---")
        for c in COLUMNS_REQUIRED:
            st.write(f"**{c.title()}:** {r[c]}")

def main():
    st.set_page_config(page_title="Incrolink Company Info", page_icon="🟢", layout="wide")
    st.title("Incrolink Company Info Extractor")
    df = load_db()
    if df is not None:
        show_search(df)

if __name__ == "__main__":
    main()
