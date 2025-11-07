import streamlit as st
import pandas as pd
import numpy as np

COLUMNS_REQUIRED = [
    "company", "nace", "ebit", "employees", "net income", "capex", "d&a",
    "changes in wc", "lt debt", "st debt", "sh equity", "capital equity", "cash", "category_code"
]

def load_secret_dropbox_xlsx(url, sheet_name=None):
    # Automatically switches to dl=1 for direct download
    fixed_url = url.replace("dl=0", "dl=1")
    return pd.read_excel(fixed_url, sheet_name=sheet_name)

def show_search(df, waccmap):
    name_query = st.text_input("Search company name (case-insensitive, substring allowed)")
    if not name_query:
        return
    matches = df["company"]
    if matches.empty:
        st.warning("No companies found.")
        return
    for i, r in matches.iterrows():
        st.markdown("---")
        for c in COLUMNS_REQUIRED:
            st.write(f"**{c.title()}:** {r[c]}")
        if st.button(f"Run DCF Automated for {r['company']}", key=f"dcfbtn{i}"):
            dcf_result = DCF_automated(r, waccmap)
            st.subheader("DCF Automated Results")
            st.write("Current EV:", dcf_result['EV_current'])
            st.write("DCF EV:", dcf_result['EV_DCF'])
            st.write("EV Growth Expected:",  "{:.2%}".format(dcf_result['growth_expected']))
            st.write("Category code:", dcf_result['category_code'])
            st.write("Parameters Used:", dcf_result['params'])

def DCF_automated(company_row, waccmap, years=5):
    sh_equity = company_row['sh equity']
    capital_equity = company_row['capital equity']
    lt_debt = company_row['lt debt']
    st_debt = company_row['st debt']
    cash = company_row['cash']
    EV_current = sh_equity + capital_equity + lt_debt + st_debt - cash

    category_code = str(company_row['category_code'])
    params_match = waccmap[waccmap['category_code'].astype(str) == category_code]
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
        'category_code': category_code,
        'params': dict(re=re, rd=rd, wacc=wacc, g=g),
    }

def main():
    # Read Dropbox URLs from Streamlit secrets
    dataset_url = st.secrets["dataset"]
    waccmap_url = st.secrets["wacc"]

    # Load data from Dropbox URLs
    df = load_secret_dropbox_xlsx(dataset_url)
    waccmap = load_secret_dropbox_xlsx(waccmap_url)

    show_search(df, waccmap)

if __name__ == "__main__":
    main()











