import streamlit as st
import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from datetime import datetime

COLUMNS_REQUIRED = [
    "company", "nace", "ebit", "employees", "net income", "capex", "d&a",
    "changes in wc", "lt debt", "st debt", "sh equity", "capital equity", "cash", "category_code"
]

COLUMNS_PORTFOLIO = ["company", "sector", "revenue", "employees"]

# Financial statement line items to extract
FINANCIAL_ITEMS = {
    'long_term_debt': 'Long term debt',
    'shareholders_funds': 'Shareholders funds',
    'operating_revenue': 'Operating revenue (Turnover)',
    'cost_of_employees': 'Costs of employees',
    'ebitda': 'EBITDA'
}

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

def extract_date_columns(df):
    """Extract date columns from dataframe (date format like 31/12/2024)"""
    date_cols = []
        try:
            # Try to parse as date
            parsed_date = pd.to_datetime(col, format='%d/%m/%Y', errors='coerce')
            if pd.notna(parsed_date):
                date_cols.append((col, parsed_date))
        except:
            pass
    
    # Sort by date in descending order (latest first)
    date_cols.sort(key=lambda x: x[1], reverse=True)
    return [col[0] for col in date_cols]  # Return just column names

def find_financial_item(df, item_name):
    """Find a financial statement item by name (fuzzy matching)"""
    value_col = df.columns[0]  # First column is "Value"
    
    if value_col not in df.columns:
        return None
    
    # Get all items in the Value column
    items = df[value_col].astype(str).tolist()
    
    # Use fuzzy matching to find the item
    matches = process.extract(item_name, items, scorer=fuzz.token_set_ratio, limit=1)
    
    if matches and matches[0][1] >= 60:
        matching_item = matches[0][0]
        # Find the row index
        row_idx = df[df[value_col] == matching_item].index
        if len(row_idx) > 0:
            return row_idx[0]
    
    return None

def extract_financial_statement_data(df, date_cols):
    """
    Extract financial data from financial statement format
    Returns dict with extracted values for latest year
    """
    data = {}
    
    if not date_cols:
        return data, "No date columns found"
    
    latest_date = date_cols[0]  # Latest date (first in sorted list)
    
    try:
        # Extract each financial item
        value_col = df.columns[0]
        
        items_found = {}
        for key, item_name in FINANCIAL_ITEMS.items():
            row_idx = find_financial_item(df, item_name)
            if row_idx is not None:
                try:
                    value = df.loc[row_idx, latest_date]
                    if pd.notna(value):
                        items_found[key] = float(value)
                    else:
                        items_found[key] = np.nan
                except:
                    items_found[key] = np.nan
            else:
                items_found[key] = np.nan
        
        return items_found, latest_date
    
    except Exception as e:
        return data, f"Error extracting data: {str(e)}"

def calculate_ratios_from_financial_statement(items_found):
    """Calculate LTDE, EDAMARGIN, FX ratios from extracted financial statement data"""
    metrics = {}
    
    try:
        # LTDE: Long term debt / Shareholders funds
        lt_debt = items_found.get('long_term_debt', np.nan)
        sh_funds = items_found.get('shareholders_funds', np.nan)
        
        if not pd.isna(sh_funds) and sh_funds != 0 and not pd.isna(lt_debt):
            metrics['ltde'] = lt_debt / sh_funds
        else:
            metrics['ltde'] = np.nan
        
        # EDAMARGIN: EBITDA / Operating revenue
        ebitda = items_found.get('ebitda', np.nan)
        op_revenue = items_found.get('operating_revenue', np.nan)
        
        if not pd.isna(op_revenue) and op_revenue != 0 and not pd.isna(ebitda):
            metrics['edamargin'] = ebitda / op_revenue
        else:
            metrics['edamargin'] = np.nan
        
        # FX: Cost of employees / Operating revenue
        cost_emp = items_found.get('cost_of_employees', np.nan)
        
        if not pd.isna(op_revenue) and op_revenue != 0 and not pd.isna(cost_emp):
            metrics['fx'] = cost_emp / op_revenue
        else:
            metrics['fx'] = np.nan
        
        return metrics
    
    except Exception as e:
        st.error(f"Error calculating ratios: {str(e)}")
        return metrics

def get_company_category_code(company_name, dataset_df):
    """Lookup company's category_code from dataset"""
    matching_companies = dataset_df[dataset_df['company'].str.contains(company_name, case=False, na=False)]
    
    if not matching_companies.empty:
        category_code = matching_companies.iloc[0]['category_code']
        return category_code
    
    return None

def get_sector_percentiles(category_code, waccmap):
    """Retrieve sector percentile ranges for LTDE, EDAMARGIN, FX (10th, 25th, 50th, 75th, 90th)"""
    percentiles = {}
    
    category_data = waccmap[waccmap['category_code'].astype(str) == str(category_code)]
    
    if not category_data.empty:
        row = category_data.iloc[0]
        
        # Extract percentile ranges for LTDE
        percentiles['ltde'] = {
            'p10': row.get('ltde10th', np.nan),
            'p25': row.get('ltde25th', np.nan),
            'p50': row.get('ltde50th', np.nan),
            'p75': row.get('ltde75th', np.nan),
            'p90': row.get('ltde90th', np.nan)
        }
        
        # Extract percentile ranges for EDAMARGIN
        percentiles['edamargin'] = {
            'p10': row.get('edamarg10th', np.nan),
            'p25': row.get('edamarg25th', np.nan),
            'p50': row.get('edamarg50th', np.nan),
            'p75': row.get('edamarg75th', np.nan),
            'p90': row.get('edamarg90th', np.nan)
        }
        
        # Extract percentile ranges for FX
        percentiles['fx'] = {
            'p10': row.get('fx10th', np.nan),
            'p25': row.get('fx25th', np.nan),
            'p50': row.get('fx50th', np.nan),
            'p75': row.get('fx75th', np.nan),
            'p90': row.get('fx90th', np.nan)
        }
    
    return percentiles

def get_percentile_position(value, percentiles_dict):
    """Calculate company's percentile position within sector range"""
    if np.isnan(value):
        return None, None, "N/A"
    
    # Get the percentile values in order
    p10 = percentiles_dict.get('p10', np.nan)
    p25 = percentiles_dict.get('p25', np.nan)
    p50 = percentiles_dict.get('p50', np.nan)
    p75 = percentiles_dict.get('p75', np.nan)
    p90 = percentiles_dict.get('p90', np.nan)
    
    # Determine which quartile/quintile
    if value < p10:
        position = "Below P10"
        rank = "Exceptional (Bottom)"
    elif value < p25:
        position = "P10-P25"
        rank = "Q1 (Very Low)"
    elif value < p50:
        position = "P25-P50"
        rank = "Q2 (Below Median)"
    elif value < p75:
        position = "P50-P75"
        rank = "Q3 (Above Median)"
    elif value < p90:
        position = "P75-P90"
        rank = "Q4 (High)"
    else:
        position = "Above P90"
        rank = "Exceptional (Top)"
    
    return position, rank, f"{p10:.4f} | {p25:.4f} | {p50:.4f} | {p75:.4f} | {p90:.4f}"

def display_metric_comparison(company_metrics, sector_percentiles, metric_name, metric_label):
    """Display metric with sector percentile comparison"""
    company_value = company_metrics.get(metric_name, np.nan)
    percentiles = sector_percentiles.get(metric_name, {})
    
    st.write(f"**{metric_label}**")
    
    if not np.isnan(company_value):
        position, rank, percentile_range = get_percentile_position(company_value, percentiles)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Company Value", f"{company_value:.4f}")
        with col2:
            st.metric("Sector Position", rank)
        with col3:
            st.metric("Percentile Range", position)
        
        # Display percentile comparison bar
        st.write("**Sector Distribution (P10 | P25 | P50 | P75 | P90):**")
        st.write(percentile_range)
    else:
        st.metric(metric_label, "N/A")
    
    st.markdown("---")

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

def frame1_analysis(dataset_df, waccmap, company_name, company_metrics, extraction_note, items_found):
    """Frame 1: Analysis with metrics calculation and sector comparison"""
    st.subheader("📊 Frame 1: Financial Metrics Analysis")
    
    # Lookup category_code from dataset
    category_code = get_company_category_code(company_name, dataset_df)
    
    st.write(f"**Analysis for:** {company_name}")
    st.write(f"**Data Source:** {extraction_note}")
    if category_code:
        st.write(f"**Category Code:** {category_code}")
    else:
        st.warning(f"⚠️ Category code not found for {company_name} in dataset")
    
    st.markdown("---")
    
    # Display extracted financial statement items
    st.subheader("📋 Extracted Financial Data")
    
    items_col1, items_col2 = st.columns(2)
    with items_col1:
        st.write("**Long-term Debt:**")
        if not np.isnan(items_found.get('long_term_debt', np.nan)):
            st.write(f"€ {items_found['long_term_debt']:,.2f}")
        else:
            st.write("N/A")
        
        st.write("**Shareholders Funds:**")
        if not np.isnan(items_found.get('shareholders_funds', np.nan)):
            st.write(f"€ {items_found['shareholders_funds']:,.2f}")
        else:
            st.write("N/A")
    
    with items_col2:
        st.write("**Operating Revenue:**")
        if not np.isnan(items_found.get('operating_revenue', np.nan)):
            st.write(f"€ {items_found['operating_revenue']:,.2f}")
        else:
            st.write("N/A")
        
        st.write("**EBITDA:**")
        if not np.isnan(items_found.get('ebitda', np.nan)):
            st.write(f"€ {items_found['ebitda']:,.2f}")
        else:
            st.write("N/A")
        
        st.write("**Cost of Employees:**")
        if not np.isnan(items_found.get('cost_of_employees', np.nan)):
            st.write(f"€ {items_found['cost_of_employees']:,.2f}")
        else:
            st.write("N/A")
    
    st.markdown("---")
    
    # Get sector percentiles if category_code is found
    if category_code:
        sector_percentiles = get_sector_percentiles(category_code, waccmap)
        
        st.subheader("📈 Company Metrics vs. Sector Benchmarks")
        st.write(f"*Comparing against {category_code} sector (10th, 25th, 50th, 75th, 90th percentiles)*")
        st.markdown("---")
        
        # Display each metric with sector comparison
        display_metric_comparison(company_metrics, sector_percentiles, 'ltde', 
                                 'Metric 1: LTDE (Long-term Debt / Shareholders\' Funds)')
        st.write("*Measures financial leverage - lower values indicate less debt relative to equity*")
        st.markdown("---")
        
        display_metric_comparison(company_metrics, sector_percentiles, 'edamargin',
                                 'Metric 2: EDAMARGIN (EBITDA / Operating Revenue)')
        st.write("*Measures operational profitability - higher values indicate better operational efficiency*")
        st.markdown("---")
        
        display_metric_comparison(company_metrics, sector_percentiles, 'fx',
                                 'Metric 3: FX (Cost of Employees / Operating Revenue)')
        st.write("*Measures labor cost intensity - lower values indicate lower employee costs relative to revenue*")
        st.markdown("---")
        
        # Summary table
        st.subheader("📊 Metrics Summary Table")
        
        summary_data = {
            'Metric': ['LTDE', 'EDAMARGIN', 'FX'],
            'Company Value': [
                f"{company_metrics.get('ltde', np.nan):.4f}" if not np.isnan(company_metrics.get('ltde', np.nan)) else 'N/A',
                f"{company_metrics.get('edamargin', np.nan):.4f}" if not np.isnan(company_metrics.get('edamargin', np.nan)) else 'N/A',
                f"{company_metrics.get('fx', np.nan):.4f}" if not np.isnan(company_metrics.get('fx', np.nan)) else 'N/A'
            ],
            'P10': [
                f"{sector_percentiles.get('ltde', {}).get('p10', np.nan):.4f}" if not np.isnan(sector_percentiles.get('ltde', {}).get('p10', np.nan)) else 'N/A',
                f"{sector_percentiles.get('edamargin', {}).get('p10', np.nan):.4f}" if not np.isnan(sector_percentiles.get('edamargin', {}).get('p10', np.nan)) else 'N/A',
                f"{sector_percentiles.get('fx', {}).get('p10', np.nan):.4f}" if not np.isnan(sector_percentiles.get('fx', {}).get('p10', np.nan)) else 'N/A'
            ],
            'P25': [
                f"{sector_percentiles.get('ltde', {}).get('p25', np.nan):.4f}" if not np.isnan(sector_percentiles.get('ltde', {}).get('p25', np.nan)) else 'N/A',
                f"{sector_percentiles.get('edamargin', {}).get('p25', np.nan):.4f}" if not np.isnan(sector_percentiles.get('edamargin', {}).get('p25', np.nan)) else 'N/A',
                f"{sector_percentiles.get('fx', {}).get('p25', np.nan):.4f}" if not np.isnan(sector_percentiles.get('fx', {}).get('p25', np.nan)) else 'N/A'
            ],
            'P50 (Median)': [
                f"{sector_percentiles.get('ltde', {}).get('p50', np.nan):.4f}" if not np.isnan(sector_percentiles.get('ltde', {}).get('p50', np.nan)) else 'N/A',
                f"{sector_percentiles.get('edamargin', {}).get('p50', np.nan):.4f}" if not np.isnan(sector_percentiles.get('edamargin', {}).get('p50', np.nan)) else 'N/A',
                f"{sector_percentiles.get('fx', {}).get('p50', np.nan):.4f}" if not np.isnan(sector_percentiles.get('fx', {}).get('p50', np.nan)) else 'N/A'
            ],
            'P75': [
                f"{sector_percentiles.get('ltde', {}).get('p75', np.nan):.4f}" if not np.isnan(sector_percentiles.get('ltde', {}).get('p75', np.nan)) else 'N/A',
                f"{sector_percentiles.get('edamargin', {}).get('p75', np.nan):.4f}" if not np.isnan(sector_percentiles.get('edamargin', {}).get('p75', np.nan)) else 'N/A',
                f"{sector_percentiles.get('fx', {}).get('p75', np.nan):.4f}" if not np.isnan(sector_percentiles.get('fx', {}).get('p75', np.nan)) else 'N/A'
            ],
            'P90': [
                f"{sector_percentiles.get('ltde', {}).get('p90', np.nan):.4f}" if not np.isnan(sector_percentiles.get('ltde', {}).get('p90', np.nan)) else 'N/A',
                f"{sector_percentiles.get('edamargin', {}).get('p90', np.nan):.4f}" if not np.isnan(sector_percentiles.get('edamargin', {}).get('p90', np.nan)) else 'N/A',
                f"{sector_percentiles.get('fx', {}).get('p90', np.nan):.4f}" if not np.isnan(sector_percentiles.get('fx', {}).get('p90', np.nan)) else 'N/A'
            ]
        }
        
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df, use_container_width=True)
    else:
        st.warning("Cannot display sector benchmarks - category code not found for this company")

def frame2_placeholder():
    """Frame 2: Placeholder for future development"""
    st.subheader("📊 Frame 2: Valuation")
    st.info("🚧 Frame 2 - Under Development")

def frame3_placeholder():
    """Frame 3: Placeholder for future development"""
    st.subheader("📊 Frame 3: Predictable")
    st.info("🚧 Frame 3 - Under Development")

def frame4_placeholder():
    """Frame 4: Placeholder for future development"""
    st.subheader("📊 Frame 4: Contacts")
    st.info("🚧 Frame 3 - Under Development")

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
        
        # Three-frame analysis section
        st.markdown("---")
        st.subheader("📈 Company Analysis Review")
        
        # Upload analysis file for detailed metrics
        analysis_file = st.file_uploader(
            f"Upload Financial Statement (XLSX) for {r['company']}",
            type="xlsx",
            key=f"analysis_upload_{i}",
            help="Upload financial statement with Value column and date columns (format: 31/12/2024)"
        )
        
        if analysis_file:
            try:
                # Read the entire file first to inspect structure
                df_analysis = pd.read_excel(analysis_file)
                
                st.info("📂 File structure detected:")
                st.write(f"**Rows:** {len(df_analysis)}")
                st.write(f"**Columns:** {list(df_analysis.columns)}")
                
                # Extract date columns
                date_cols = extract_date_columns(df_analysis)
                
                if date_cols:
                    st.write(f"**Date columns found:** {date_cols}")
                    st.write(f"**Latest year:** {date_cols[0]}")
                    
                    # Extract financial statement data
                    items_found, extraction_note = extract_financial_statement_data(df_analysis, date_cols)
                    
                    if items_found:
                        # Calculate ratios
                        company_metrics = calculate_ratios_from_financial_statement(items_found)
                        
                        if company_metrics:
                            # Create tabs for three frames
                            tab1, tab2, tab3, tab4 = st.tabs(["Frame 1: FS analysis", "Frame 2: Valuation", "Frame 3: Predictable", "Frame 4: Contacts"])
                            
                            with tab1:
                                frame1_analysis(df, waccmap, r['company'], company_metrics, extraction_note, items_found)
                            
                            with tab2:
                                frame2_placeholder()
                            
                            with tab3:
                                frame3_placeholder()
                            
                            with tab4:
                                frame4_placeholder()
                        else:
                            st.error("Could not calculate ratios from extracted data")
                    else:
                        st.warning("Could not extract financial statement items. Please check file format and item names.")
                        st.write("**Looking for items:**")
                        for key, item_name in FINANCIAL_ITEMS.items():
                            st.write(f"• {item_name}")
                else:
                    st.error("No date columns found. Expected format: 31/12/2024, 31/12/2023, etc.")
                    st.write(f"Available columns: {list(df_analysis.columns)}")
            
            except Exception as e:
                st.error(f"Error loading analysis file: {str(e)}")
                import traceback
                st.write(traceback.format_exc())
        else:
            st.info("💡 Upload a financial statement file to analyze company metrics")

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
            
            st.write("**Financial Statement file format:**")
            st.write("Column Headers: Value | 31/12/2024 | 31/12/2023 | 31/12/2022 | ...")
            st.write("")
            st.write("**Required row items:**")
            for key, item_name in FINANCIAL_ITEMS.items():
                st.text(f"• {item_name}")
            
            st.write("**WACC file must include percentile columns:**")
            st.write("• ltde10th, ltde25th, ltde50th, ltde75th, ltde90th")
            st.write("• edamarg10th, edamarg25th, edamarg50th, edamarg75th, edamarg90th")
            st.write("• fx10th, fx25th, fx50th, fx75th, fx90th")

if __name__ == "__main__":
    main()

