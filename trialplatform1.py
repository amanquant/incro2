import streamlit as st
import pandas as pd
import numpy as np
import time

COLUMNS_REQUIRED = [
    "company", "nace", "ebit", "employees", "net income", "capex", "d&a",
    "changes in wc", "lt debt", "st debt", "sh equity", "capital equity", "cash"
]

import streamlit as st
import time

def logo_screener():
    st.markdown("""
        <style>
        .stApp { background: #fff !important; }
        .logo-wrap { display: flex; justify-content: center; align-items: center; height: 400px; }
        .logo-img {
            opacity: 0;
            animation: fadeInLogo 2s ease-in forwards;
            width: 220px;
        }
        .platform-title {
            opacity: 0;
            text-align: center;
            font-size: 28px;
            font-weight: 700;
            margin-top: 10px;
            animation: fadeInTitle 1.2s 2s ease-in forwards;
        }
        @keyframes fadeInLogo { to { opacity: 1; } }
        @keyframes fadeInTitle { to { opacity: 1; } }
        </style>
        <div class='logo-wrap'>
            <img src='logoincrolink1.jpeg' class='logo-img' />
        </div>
        <div class='platform-title'>Incrolink Platform</div>
        """, unsafe_allow_html=True)

def small_logo():
    st.markdown("""
        <style>
        .small-logo {
            position: fixed;
            top: 25px;
            right: 25px;
            z-index: 100;
        }
        </style>
        <div class='small-logo'>
            <img src='logoincrolink1.jpeg' width='48'/>
        </div>
        """, unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="Incrolink Company Info", page_icon="🟢", layout="wide")
    if "platform_ready" not in st.session_state:
        st.session_state["platform_ready"] = False
        st.session_state["start_time"] = time.time()

    if not st.session_state["platform_ready"]:
        logo_screener()
        # Wait for 2.5 seconds, then switch to platform
        if time.time() - st.session_state["start_time"] > 2.5:
            st.session_state["platform_ready"] = True
            st.experimental_rerun()
        st.stop()
    else:
        small_logo()
        st.title("Incrolink Company Info Extractor + DCF Automated")
        def def normalize_columns(df):
    lower_cols = [c.lower() for c in df.columns]
    col_map = {}
    for required in COLUMNS_REQUIRED:
        for i, col in enumerate(lower_cols):
            if required in col.replace("_", " "):
                col_map[df.columns[i]] = required
                break
    return df.rename(columns=col_map)

def load_db():
    file = st.file_uploader("Upload Excel Company DB", type=["xlsx"])
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
    if st.checkbox("Preview company data", False):
        st.dataframe(df.head())
    return df

def load_secret_dropbox_xlsx(url, sheet_name=None):
    return pd.read_excel(url, sheet_name=sheet_name)

def show_search(df, nacemapping, waccmap):
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
        if st.button(f"Run DCF Automated for {r['company']}", key=f"dcfbtn{i}"):
            dcf_result = DCF_automated(r, nacemapping, waccmap)
            st.subheader("DCF Automated Results")
            st.write("Current EV:", dcf_result['EV_current'])
            st.write("DCF EV:", dcf_result['EV_DCF'])
            st.write("EV Growth Expected:",  "{:.2%}".format(dcf_result['growth_expected']))
            st.write("Industry code letter:", dcf_result['code_letter'])
            st.write("Parameters Used:", dcf_result['params'])

def DCF_automated(company_row, nacemapping, waccmap, years=5):
    sh_equity = company_row['sh equity']
    capital_equity = company_row['capital equity']
    lt_debt = company_row['lt debt']
    st_debt = company_row['st debt']
    cash = company_row['cash']
    EV_current = sh_equity + capital_equity + lt_debt + st_debt - cash

    nace_code = str(company_row['nace'])
    sector_match = nacemapping[nacemapping['nace_code'].astype(str) == nace_code]
    if not sector_match.empty:
        code_letter = sector_match.iloc[0]['sector_code']  # A, B, C, ...
    else:
        code_letter = None

    params_match = waccmap[waccmap['sector_code'] == code_letter]
    if not params_match.empty:
        re = params_match.iloc[0]['re']
        rd = params_match.iloc[0]['rd']
        wacc = params_match.iloc[0]['wacc']
        g = params_match.iloc[0]['g']
    else:
        re = rd = wacc = g = np.nan

    net_income = company_row['net income']
    d_and_a = company_row['d&a']
    capex = company_row['capex']
    changes_in_wc = company_row['changes in wc']
    FCF0 = net_income + d_and_a - capex + changes_in_wc

    FCFs = [FCF0 * ((1 + g) ** n) for n in range(1, years + 1)]
    TV = FCFs[-1] / (wacc - g) if (wacc - g) != 0 else 0

    discount_factors = [(1 + wacc) ** n for n in range(1, years + 1)]
    discounted_FCFs = [f / d for f, d in zip(FCFs, discount_factors)]
    discounted_TV = TV / discount_factors[-1]

    EV_DCF = sum(discounted_FCFs) + discounted_TV
    growth_expected = (EV_DCF / EV_current) - 1 if EV_current else np.nan

    return {
        'EV_current': EV_current,
        'EV_DCF': EV_DCF,
        'growth_expected': growth_expected,
        'code_letter': code_letter,
        'params': dict(re=re, rd=rd, wacc=wacc, g=g),
        'nace_code': nace_code
    }

if __name__ == "__main__":
    main()



