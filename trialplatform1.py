import streamlit as st
import pandas as pd
import numpy as np

COLUMNS_REQUIRED = [
    "company", "nace", "ebit", "employees", "net income", "capex", "d&a",
    "changes in wc", "lt debt", "st debt", "sh equity", "capital equity", "cash", "category_code"
]

def validate_columns(df, file_type="Dataset"):
    """Validate that the dataframe has all required columns"""
    missing_cols = [col for col in COLUMNS_REQUIRED if col not in df.columns]
    if missing_cols:
        st.error(f"❌ {file_type} - Missing required columns: {', '.join(missing_cols)}")
        return False
    st.success(f"✅ {file_type} - All required columns present")
    return True

def show_search(df, waccmap):
    """Display search interface and run DCF analysis"""
    st.subheader("Company Search & DCF Analysis")
    name_query = st.text_input("Search company name (case-insensitive, substring allowed)")
    
    if not name_query:
        st.info("Enter a company name to search")
        return
    
    # Filter companies by search query
    filtered_df = df[df['company'].str.contains(name_query, case=False, na=False)]
    
    if filtered_df.empty:
        st.warning(f"No companies found matching '{name_query}'")
        return
    
    st.write(f"Found {len(filtered_df)} company(ies)")
    
    for i, r in filtered_df.iterrows():
        st.markdown("---")
        
        # Display company information
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Company:** {r['company']}")
            st.write(f"**NACE:** {r['nace']}")
        with col2:
            st.write(f"**Net Income:** {r['net income']:.2f}")
            st.write(f"**Employees:** {r['employees']}")
        with col3:
            st.write(f"**EBIT:** {r['ebit']:.2f}")
            st.write(f"**Category Code:** {r['category_code']}")
        
        # DCF Analysis button
        if st.button(f"Run DCF Automated for {r['company']}", key=f"dcfbtn{i}"):
            dcf_result = DCF_automated(r, waccmap)
            
            st.subheader("📊 DCF Automated Results")
            
            result_col1, result_col2, result_col3 = st.columns(3)
            with result_col1:
                st.metric("Current EV", f"${dcf_result['EV_current']:.2f}")
            with result_col2:
                st.metric("DCF EV", f"${dcf_result['EV_DCF']:.2f}")
            with result_col3:
                st.metric("EV Growth Expected", f"{dcf_result['growth_expected']:.2%}")
            
            st.write("**DCF Parameters Used:**")
            params_df = pd.DataFrame([dcf_result['params']])
            st.dataframe(params_df, use_container_width=True)

def DCF_automated(company_row, waccmap, years=5):
    """Calculate DCF valuation for a company"""
    # Current Enterprise Value calculation
    sh_equity = company_row['sh equity']
    capital_equity = company_row['capital equity']
    lt_debt = company_row['lt debt']
    st_debt = company_row['st debt']
    cash = company_row['cash']
    EV_current = sh_equity + capital_equity + lt_debt + st_debt - cash

    # Retrieve WACC and growth parameters based on category code
    category_code = str(company_row['category_code'])
    params_match = waccmap[waccmap['category_code'].astype(str) == category_code]
    
    if not params_match.empty:
        re = params_match.iloc[0]['re']
        rd = params_match.iloc[0]['rd']
        wacc = params_match.iloc[0]['wacc']
        g = params_match.iloc[0]['g']
    else:
        re = rd = wacc = g = np.nan

    # Free Cash Flow calculation
    net_income = company_row['net income']
    d_and_a = company_row['d&a']
    capex = company_row['capex']
    changes_in_wc = company_row['changes in wc']
    FCF0 = net_income + d_and_a - capex + changes_in_wc

    # Project FCFs and calculate Terminal Value
    FCFs = [FCF0 * ((1 + g) ** n) for n in range(1, years + 1)]
    TV = FCFs[-1] / (wacc - g) if (wacc - g) != 0 else 0

    # Discount all cash flows and terminal value
    discount_factors = [(1 + wacc) ** n for n in range(1, years + 1)]
    discounted_FCFs = [f / d for f, d in zip(FCFs, discount_factors)]
    discounted_TV = TV / discount_factors[-1]

    # Calculate DCF Enterprise Value
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
    # Page configuration
    st.set_page_config(page_title="Incrolink Agent", layout="wide", initial_sidebar_state="expanded")
    
    # Header with branding
    st.title("🔗 Incrolink Agent")
    st.markdown("**Automated DCF Valuation Platform**")
    st.markdown("---")
    
    # Sidebar for file uploads
    st.sidebar.header("📁 Data Configuration")
    
    dataset_file = st.sidebar.file_uploader(
        "Upload Dataset (XLSX)", 
        type="xlsx", 
        key="dataset_uploader",
        help="Upload the company dataset with all required columns"
    )
    
    wacc_file = st.sidebar.file_uploader(
        "Upload WACC Map (XLSX)", 
        type="xlsx", 
        key="wacc_uploader",
        help="Upload the WACC parameters mapped by category code"
    )
    
    # Process uploaded files
    if dataset_file and wacc_file:
        try:
            df = pd.read_excel(dataset_file)
            waccmap = pd.read_excel(wacc_file)
            
            # Validate dataset columns
            if validate_columns(df, "Dataset"):
                # Display dataset summary
                st.sidebar.metric("Companies Loaded", len(df))
                st.sidebar.metric("Categories", df['category_code'].nunique())
                
                # Run search and DCF analysis
                show_search(df, waccmap)
            else:
                st.stop()
                
        except Exception as e:
            st.error(f"Error loading files: {str(e)}")
    else:
        st.info("👈 Please upload both the Dataset and WACC Map files in the sidebar to proceed.")
        
        # Display column requirements
        with st.expander("📋 Required Columns Reference"):
            st.write("Your dataset must include the following columns:")
            for col in COLUMNS_REQUIRED:
                st.text(f"• {col}")

if __name__ == "__main__":
    main()












