import streamlit as st
import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

COLUMNS_REQUIRED = [
    "company", "nace", "ebit", "employees", "net income", "capex", "d&a",
    "changes in wc", "lt debt", "st debt", "sh equity", "capital equity", "cash", "category_code"
]

COLUMNS_PORTFOLIO = ["company", "sector", "revenue", "employees"]

def validate_columns(df, file_type="Dataset", required_cols=None):
    """Validate that the dataframe has all required columns"""
    if required_cols is None:
        required_cols = COLUMNS_REQUIRED
    
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.error(f"❌ {file_type} - Missing required columns: {', '.join(missing_cols)}")
        return False
    st.success(f"✅ {file_type} - All required columns present")
    return True

def nace_to_category(nace_code, nace_mapping=None):
    """Convert NACE code to category code using mapping"""
    if nace_mapping is None or nace_code not in nace_mapping.values:
        return None
    mapping_row = nace_mapping[nace_mapping['nace'] == nace_code]
    return mapping_row['category_code'].iloc[0] if not mapping_row.empty else None

def fuzzy_match_companies(portfolio_company, db_companies, threshold=80):
    """Find similar companies in database using fuzzy matching"""
    matches = process.extract(
        portfolio_company,
        db_companies['company'].tolist(),
        scorer=fuzz.token_set_ratio,
        limit=5
    )
    return [match for match in matches if match[1] >= threshold]

def create_filtered_search(db, portfolio_df, nace_mapping):
    """Create filtered search interface for deal matching"""
    st.subheader("🔍 Search for Deals - Match Portfolio Companies")
    
    # Display portfolio companies
    st.write(f"**Portfolio Companies to Match:** {len(portfolio_df)} companies")
    
    selected_portfolio_idx = st.selectbox(
        "Select a portfolio company to match",
        range(len(portfolio_df)),
        format_func=lambda i: f"{portfolio_df.iloc[i]['company']} ({portfolio_df.iloc[i]['sector']})"
    )
    
    portfolio_company = portfolio_df.iloc[selected_portfolio_idx]
    
    st.markdown("---")
    st.write("**Portfolio Company Details:**")
    port_col1, port_col2, port_col3 = st.columns(3)
    with port_col1:
        st.write(f"**Name:** {portfolio_company['company']}")
        st.write(f"**Sector:** {portfolio_company['sector']}")
    with port_col2:
        st.write(f"**Revenue:** {portfolio_company['revenue']:,.2f}")
    with port_col3:
        st.write(f"**Employees:** {portfolio_company['employees']}")
    
    st.markdown("---")
    st.subheader("Advanced Filters")
    
    # Create filter options
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    
    with filter_col1:
        revenue_range = st.slider(
            "Revenue Range (M€)",
            min_value=0.0,
            max_value=float(db['revenue'].max()) if 'revenue' in db.columns else 1000.0,
            value=(0.0, float(db['revenue'].max()) if 'revenue' in db.columns else 1000.0),
            step=10.0
        )
    
    with filter_col2:
        employee_range = st.slider(
            "Employee Range",
            min_value=0,
            max_value=int(db['employees'].max()) if 'employees' in db.columns else 10000,
            value=(0, int(db['employees'].max()) if 'employees' in db.columns else 10000),
            step=10
        )
    
    with filter_col3:
        sector_filter = st.multiselect(
            "Filter by NACE Code",
            options=sorted(db['nace'].unique()),
            default=None
        )
    
    # Apply filters
    filtered_db = db.copy()
    
    if 'revenue' in filtered_db.columns:
        filtered_db = filtered_db[
            (filtered_db['revenue'] >= revenue_range[0]) &
            (filtered_db['revenue'] <= revenue_range[1])
        ]
    
    if 'employees' in filtered_db.columns:
        filtered_db = filtered_db[
            (filtered_db['employees'] >= employee_range[0]) &
            (filtered_db['employees'] <= employee_range[1])
        ]
    
    if sector_filter:
        filtered_db = filtered_db[filtered_db['nace'].isin(sector_filter)]
    
    st.write(f"**Matching Results:** {len(filtered_db)} companies found")
    
    if filtered_db.empty:
        st.warning("No companies match the selected filters.")
        return None
    
    # Display matches with fuzzy matching
    st.subheader("Matched Companies")
    
    fuzzy_matches = fuzzy_match_companies(
        portfolio_company['company'],
        filtered_db,
        threshold=60
    )
    
    if fuzzy_matches:
        st.write("**Fuzzy Name Matches:**")
        for match_name, score in fuzzy_matches:
            matched_row = filtered_db[filtered_db['company'] == match_name].iloc[0]
            st.write(f"• {match_name} (Match Score: {score}%)")
    
    # Display filtered results in a dataframe
    display_cols = ['company', 'nace', 'employees']
    if 'revenue' in filtered_db.columns:
        display_cols.insert(1, 'revenue')
    
    st.dataframe(
        filtered_db[display_cols].head(20),
        use_container_width=True,
        height=300
    )
    
    # Allow manual selection from filtered results
    selected_match = st.selectbox(
        "Select a company from filtered results for DCF analysis",
        range(len(filtered_db)),
        format_func=lambda i: f"{filtered_db.iloc[i]['company']} (Employees: {filtered_db.iloc[i]['employees']})"
    )
    
    return filtered_db.iloc[selected_match]

def show_search(df, waccmap):
    """Display search interface and run DCF analysis - Review Company mode"""
    st.subheader("🏢 Review Company - Evaluate Individual Company")
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
    EV_current = sh_equity + lt_debt + st_debt - cash

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
    FCF0 = net_income + d_and_a - capex - changes_in_wc

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
    st.title("Incrolink Agent")
    try:
        st.logo("logoincrolink1.jpeg")
    except:
        pass  # Logo file may not exist
    
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
    
    portfolio_file = st.sidebar.file_uploader(
        "Upload Portfolio (XLSX) - Optional",
        type="xlsx",
        key="portfolio_uploader",
        help="Upload portfolio companies for deal matching (optional)"
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
                
                st.markdown("---")
                
                # Main workflow selection
                st.subheader("🎯 Select Workflow Mode")
                
                workflow_mode = st.radio(
                    "Choose your analysis mode:",
                    options=["Review Company", "Search for Deals"],
                    horizontal=True,
                    help="Review Company: Evaluate individual companies | Search for Deals: Match portfolio companies"
                )
                
                st.markdown("---")
                
                if workflow_mode == "Review Company":
                    show_search(df, waccmap)
                
                elif workflow_mode == "Search for Deals":
                    if portfolio_file is None:
                        st.warning("⚠️ Portfolio file is required for deal matching. Please upload it in the sidebar.")
                    else:
                        try:
                            portfolio_df = pd.read_excel(portfolio_file)
                            if validate_columns(portfolio_df, "Portfolio", COLUMNS_PORTFOLIO):
                                st.sidebar.metric("Portfolio Companies", len(portfolio_df))
                                
                                selected_company = create_filtered_search(df, portfolio_df, None)
                                
                                if selected_company is not None:
                                    st.markdown("---")
                                    if st.button("Run DCF Analysis on Selected Match"):
                                        dcf_result = DCF_automated(selected_company, waccmap)
                                        
                                        st.subheader("📊 DCF Valuation Results")
                                        
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
                        except Exception as e:
                            st.error(f"Error loading portfolio file: {str(e)}")
            else:
                st.stop()
                
        except Exception as e:
            st.error(f"Error loading files: {str(e)}")
    else:
        st.info("👈 Please upload both the Dataset and WACC Map files in the sidebar to proceed.")
        
        # Display column requirements
        with st.expander("📋 Required Columns Reference"):
            st.write("**Dataset must include:**")
            for col in COLUMNS_REQUIRED:
                st.text(f"• {col}")
            
            st.write("**Portfolio file (optional) must include:**")
            for col in COLUMNS_PORTFOLIO:
                st.text(f"• {col}")

if __name__ == "__main__":
    main()
