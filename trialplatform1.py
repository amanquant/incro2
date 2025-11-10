import streamlit as st
import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from datetime import datetime

COLUMNS_REQUIRED = [
    "company", "nace", "ebit", "employees", "net income", "capex", "d&a",
    "changes in wc", "lt debt", "st debt", "sh equity", "capital equity", "cash", "category_code", "revenue", "companyID"
]

COLUMNS_PORTFOLIO = ["company", "sector", "revenue", "employees"]

FINANCIAL_ITEMS = {
    'long_term_debt': 'Long term debt',
    'shareholders_funds': 'Shareholders funds',
    'operating_revenue': 'Operating revenue (Turnover)',
    'cost_of_employees': 'Costs of employees',
    'ebitda': 'EBITDA'
}

PREDICTABILITY_CATEGORIES = {
    "0": "Sell Side",
    "0,23": "Buy Side",
    "0,43": "Financing Opportunity",
    "0,54": "Financing Opportunity",
    "0,65": "Financing Opportunity",
    "0,8": "Undetected"
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
    """Extract date columns from dataframe"""
    date_cols = []
    
    for col in df.columns:
        if col.lower() == 'value':
            continue
        try:
            parsed_date = pd.to_datetime(col, format='%d/%m/%Y', errors='coerce')
            if pd.notna(parsed_date):
                date_cols.append((col, parsed_date))
        except:
            pass
    
    date_cols.sort(key=lambda x: x[1], reverse=True)
    return [col[0] for col in date_cols]

def find_financial_item(df, item_name):
    """Find a financial statement item by name (fuzzy matching)"""
    value_col = df.columns[0]
    
    if value_col not in df.columns:
        return None
    
    items = df[value_col].astype(str).tolist()
    matches = process.extract(item_name, items, scorer=fuzz.token_set_ratio, limit=1)
    
    if matches and matches[0][1] >= 60:
        matching_item = matches[0][0]
        row_idx = df[df[value_col] == matching_item].index
        if len(row_idx) > 0:
            return row_idx[0]
    
    return None

def extract_financial_statement_data(df, date_cols):
    """Extract financial data from financial statement format"""
    data = {}
    
    if not date_cols:
        return data, "No date columns found"
    
    latest_date = date_cols[0]
    
    try:
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
    """Calculate LTDE, EDAMARGIN, FX ratios"""
    metrics = {}
    
    try:
        lt_debt = items_found.get('long_term_debt', np.nan)
        sh_funds = items_found.get('shareholders_funds', np.nan)
        
        if not pd.isna(sh_funds) and sh_funds != 0 and not pd.isna(lt_debt):
            metrics['ltde'] = lt_debt / sh_funds
        else:
            metrics['ltde'] = np.nan
        
        ebitda = items_found.get('ebitda', np.nan)
        op_revenue = items_found.get('operating_revenue', np.nan)
        
        if not pd.isna(op_revenue) and op_revenue != 0 and not pd.isna(ebitda):
            metrics['edamargin'] = ebitda / op_revenue
        else:
            metrics['edamargin'] = np.nan
        
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
    """Retrieve sector percentile ranges"""
    percentiles = {}
    
    category_data = waccmap[waccmap['category_code'].astype(str) == str(category_code)]
    
    if not category_data.empty:
        row = category_data.iloc[0]
        
        percentiles['ltde'] = {
            'p10': row.get('ltde10th', np.nan),
            'p25': row.get('ltde25th', np.nan),
            'p50': row.get('ltde50th', np.nan),
            'p75': row.get('ltde75th', np.nan),
            'p90': row.get('ltde90th', np.nan)
        }
        
        percentiles['edamargin'] = {
            'p10': row.get('edamarg10th', np.nan),
            'p25': row.get('edamarg25th', np.nan),
            'p50': row.get('edamarg50th', np.nan),
            'p75': row.get('edamarg75th', np.nan),
            'p90': row.get('edamarg90th', np.nan)
        }
        
        percentiles['fx'] = {
            'p10': row.get('fx10th', np.nan),
            'p25': row.get('fx25th', np.nan),
            'p50': row.get('fx50th', np.nan),
            'p75': row.get('fx75th', np.nan),
            'p90': row.get('fx90th', np.nan)
        }
        
        # Add nsellside for Frame 3
        percentiles['nsellside_p50'] = row.get('nsellside50th', np.nan)
        percentiles['nsellside'] = row.get('nsellside', np.nan)
    
    return percentiles

def get_percentile_position(value, percentiles_dict):
    """Calculate company's percentile position"""
    if np.isnan(value):
        return None, None, "N/A"
    
    p10 = percentiles_dict.get('p10', np.nan)
    p25 = percentiles_dict.get('p25', np.nan)
    p50 = percentiles_dict.get('p50', np.nan)
    p75 = percentiles_dict.get('p75', np.nan)
    p90 = percentiles_dict.get('p90', np.nan)
    
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
        
        st.write("**Sector Distribution (P10 | P25 | P50 | P75 | P90):**")
        st.write(percentile_range)
    else:
        st.metric(metric_label, "N/A")
    
    st.markdown("---")

def get_ceo_age(company_row, contacts_df):
    """Get CEO age from contacts file"""
    if contacts_df is None:
        return None
    
    # Get company ID from dataset
    if 'companyID' not in company_row:
        return None
    
    company_id = company_row['companyID']
    
    # Check if companyID column exists in contacts
    if 'companyID' not in contacts_df.columns:
        return None
    
    # Find CEO for this company
    company_contacts = contacts_df[contacts_df['companyID'] == company_id]
    
    if company_contacts.empty:
        return None
    
    # Look for CEO
    if 'CEO' in company_contacts.columns and 'age' in company_contacts.columns:
        ceo_row = company_contacts[company_contacts['CEO'].notna()]
        if not ceo_row.empty:
            return ceo_row.iloc[0]['age']
    
    return None

def predictability_decision_tree(ev_growth, nsellside, nsellside_p50, ceo_age, revenue, edamargin, edamargin_p75):
    """
    Decision tree for predictability classification
    Returns tuple: (leaf_value, category, path_taken)
    """
    path = []
    
    # Node 1: EV growth < 15%
    path.append(f"EV Growth: {ev_growth:.2%}")
    if ev_growth < 0.15:
        return "0", PREDICTABILITY_CATEGORIES["0"], path
    
    # Node 2: Sector sell side operations < 50th percentile
    path.append(f"N Sell Side: {nsellside} vs P50: {nsellside_p50}")
    if not np.isnan(nsellside) and not np.isnan(nsellside_p50) and nsellside < nsellside_p50:
        return "0,23", PREDICTABILITY_CATEGORIES["0,23"], path
    
    # Node 3: CEO age < 60
    path.append(f"CEO Age: {ceo_age}")
    if ceo_age is not None and not np.isnan(ceo_age) and ceo_age < 60:
        return "0,43", PREDICTABILITY_CATEGORIES["0,43"], path
    
    # Node 4: Revenue < 90M
    path.append(f"Revenue: €{revenue:,.0f}")
    if not np.isnan(revenue) and revenue < 90000000:
        return "0,54", PREDICTABILITY_CATEGORIES["0,54"], path
    
    # Node 5: EDAMARGIN < 75th percentile
    path.append(f"EDAMARGIN: {edamargin:.4f} vs P75: {edamargin_p75:.4f}")
    if not np.isnan(edamargin) and not np.isnan(edamargin_p75) and edamargin < edamargin_p75:
        return "0,65", PREDICTABILITY_CATEGORIES["0,65"], path
    
    # Default: Undetected
    return "0,8", PREDICTABILITY_CATEGORIES["0,8"], path

def DCF_automated(company_row, waccmap, years=5):
    """Calculate DCF valuation for a company"""
    sh_equity = company_row['sh equity']
    capital_equity = company_row['capital equity']
    lt_debt = company_row['lt debt']
    st_debt = company_row['st debt']
    cash = company_row['cash']
    EV_current = sh_equity + lt_debt + st_debt - cash

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
    FCF0 = net_income + d_and_a - capex - changes_in_wc

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
        'FCF0': FCF0,
        'FCFs': FCFs,
        'TV': TV,
        'discounted_FCFs': discounted_FCFs,
        'discounted_TV': discounted_TV,
        'years': years
    }

def frame1_analysis(dataset_df, waccmap, company_name, company_metrics, extraction_note, items_found):
    """Frame 1: Financial Statement Analysis"""
    st.subheader("📊 Frame 1: Financial Metrics Analysis")
    
    category_code = get_company_category_code(company_name, dataset_df) if dataset_df is not None else None
    
    st.write(f"**Analysis for:** {company_name}")
    st.write(f"**Data Source:** {extraction_note}")
    if category_code:
        st.write(f"**Category Code:** {category_code}")
    
    st.markdown("---")
    
    st.subheader("📋 Extracted Financial Data")
    
    items_col1, items_col2 = st.columns(2)
    with items_col1:
        st.write("**Long-term Debt:**")
        st.write(f"€ {items_found['long_term_debt']:,.2f}" if not np.isnan(items_found.get('long_term_debt', np.nan)) else "N/A")
        
        st.write("**Shareholders Funds:**")
        st.write(f"€ {items_found['shareholders_funds']:,.2f}" if not np.isnan(items_found.get('shareholders_funds', np.nan)) else "N/A")
    
    with items_col2:
        st.write("**Operating Revenue:**")
        st.write(f"€ {items_found['operating_revenue']:,.2f}" if not np.isnan(items_found.get('operating_revenue', np.nan)) else "N/A")
        
        st.write("**EBITDA:**")
        st.write(f"€ {items_found['ebitda']:,.2f}" if not np.isnan(items_found.get('ebitda', np.nan)) else "N/A")
        
        st.write("**Cost of Employees:**")
        st.write(f"€ {items_found['cost_of_employees']:,.2f}" if not np.isnan(items_found.get('cost_of_employees', np.nan)) else "N/A")
    
    st.markdown("---")
    
    if category_code and dataset_df is not None:
        sector_percentiles = get_sector_percentiles(category_code, waccmap)
        
        st.subheader("📈 Company Metrics vs. Sector Benchmarks")
        
        display_metric_comparison(company_metrics, sector_percentiles, 'ltde', 'Metric 1: LTDE')
        display_metric_comparison(company_metrics, sector_percentiles, 'edamargin', 'Metric 2: EDAMARGIN')
        display_metric_comparison(company_metrics, sector_percentiles, 'fx', 'Metric 3: FX')
    else:
        st.info("📊 Sector benchmarks will display when dataset is uploaded")

def frame2_valuation(waccmap, company_row, company_metrics, items_found):
    """Frame 2: DCF Valuation Analysis"""
    st.subheader("💰 Frame 2: DCF Valuation & Analysis")
    
    if company_row is None:
        st.info("❌ Company dataset required")
        return
    
    dcf_result = DCF_automated(company_row, waccmap)
    
    st.write(f"**Company:** {company_row['company']}")
    st.markdown("---")
    
    val_col1, val_col2, val_col3 = st.columns(3)
    with val_col1:
        st.metric("Current EV (€)", f"{dcf_result['EV_current']:,.2f}")
    with val_col2:
        st.metric("DCF EV (€)", f"{dcf_result['EV_DCF']:,.2f}")
    with val_col3:
        st.metric("EV Growth (%)", f"{dcf_result['growth_expected']:.2%}")
    
    st.markdown("---")
    
    st.subheader("📋 DCF Parameters")
    
    param_col1, param_col2 = st.columns(2)
    with param_col1:
        st.write("**WACC:**")
        st.write(f"• Re: {dcf_result['params'].get('re', 'N/A'):.4f}" if dcf_result['params'].get('re') else "• Re: N/A")
        st.write(f"• Rd: {dcf_result['params'].get('rd', 'N/A'):.4f}" if dcf_result['params'].get('rd') else "• Rd: N/A")
        st.write(f"• WACC: {dcf_result['params'].get('wacc', 'N/A'):.4f}" if dcf_result['params'].get('wacc') else "• WACC: N/A")
    
    with param_col2:
        st.write("**Cash Flow:**")
        st.write(f"• Growth: {dcf_result['params'].get('g', 'N/A'):.4f}" if dcf_result['params'].get('g') else "• Growth: N/A")
        st.write(f"• FCF0: €{dcf_result['FCF0']:,.2f}" if not np.isnan(dcf_result['FCF0']) else "• FCF0: N/A")
    
    st.markdown("---")
    
    st.subheader("📈 5-Year Projection")
    
    fcf_data = {
        'Year': list(range(1, dcf_result['years'] + 1)),
        'FCF (€)': [f"{fcf:,.2f}" for fcf in dcf_result['FCFs']],
        'Discounted FCF (€)': [f"{dfcf:,.2f}" for dfcf in dcf_result['discounted_FCFs']]
    }
    
    st.dataframe(pd.DataFrame(fcf_data), use_container_width=True)
    
    return dcf_result

def frame3_predictability(dataset_df, waccmap, contacts_df, company_row, company_metrics, dcf_result):
    """Frame 3: Predictability Analysis with Decision Tree"""
    st.subheader("🎯 Frame 3: Predictability Classification")
    
    if company_row is None or dcf_result is None:
        st.warning("⚠️ Dataset and DCF required")
        return
    
    st.write(f"**Company:** {company_row['company']}")
    st.markdown("---")
    
    # Extract required parameters
    ev_growth = dcf_result['growth_expected']
    revenue = company_row.get('revenue', np.nan)
    edamargin = company_metrics.get('edamargin', np.nan)
    
    # Get sector data
    category_code = company_row.get('category_code', None)
    sector_percentiles = get_sector_percentiles(category_code, waccmap)
    nsellside = sector_percentiles.get('nsellside', np.nan)
    nsellside_p50 = sector_percentiles.get('nsellside_p50', np.nan)
    edamargin_p75 = sector_percentiles.get('edamargin', {}).get('p75', np.nan)
    
    # Get CEO age
    ceo_age = get_ceo_age(company_row, contacts_df)
    
    # Run decision tree
    leaf_value, category, path = predictability_decision_tree(
        ev_growth, nsellside, nsellside_p50, ceo_age, revenue, edamargin, edamargin_p75
    )
    
    st.subheader("🌳 Decision Tree Analysis")
    
    # Display input parameters
    st.write("**Input Parameters:**")
    
    input_col1, input_col2 = st.columns(2)
    with input_col1:
        st.write(f"• EV Growth: {ev_growth:.2%}")
        st.write(f"• Revenue: €{revenue:,.0f}" if not np.isnan(revenue) else "• Revenue: N/A")
        st.write(f"• EDAMARGIN: {edamargin:.4f}" if not np.isnan(edamargin) else "• EDAMARGIN: N/A")
    
    with input_col2:
        st.write(f"• N Sell Side: {nsellside:.0f}" if not np.isnan(nsellside) else "• N Sell Side: N/A")
        st.write(f"• CEO Age: {ceo_age:.0f}" if ceo_age is not None else "• CEO Age: N/A")
        st.write(f"• EDAMARGIN P75: {edamargin_p75:.4f}" if not np.isnan(edamargin_p75) else "• EDAMARGIN P75: N/A")
    
    st.markdown("---")
    
    # Display decision path
    st.subheader("📍 Decision Path")
    for i, step in enumerate(path, 1):
        st.write(f"**Step {i}:** {step}")
    
    st.markdown("---")
    
    # Display result
    st.subheader("🎯 Classification Result")
    
    result_col1, result_col2 = st.columns(2)
    with result_col1:
        st.metric("Leaf Value", leaf_value)
    with result_col2:
        st.metric("Category", category)
    
    # Category explanation
    st.markdown("---")
    st.info("""
    **Sell Side:** Low growth (EV < 15%)
    **Buy Side:** High growth, low sector activity
    **Financing Opportunity:** High growth with specific characteristics
    **Undetected:** High performing company
    """)

def frame4_placeholder():
    """Frame 4: Contacts"""
    st.subheader("📊 Frame 4: Contacts")
    st.info("🚧 Under Development")

def show_standalone_frames():
    """Display frames standalone"""
    st.subheader("📈 Company Analysis (Pre-Dataset)")
    st.info("💡 Upload financial statement for Frame 1")
    
    analysis_file = st.file_uploader("Upload Financial Statement (XLSX)", type="xlsx", key="standalone")
    
    if analysis_file:
        try:
            df_analysis = pd.read_excel(analysis_file)
            date_cols = extract_date_columns(df_analysis)
            
            if date_cols:
                items_found, extraction_note = extract_financial_statement_data(df_analysis, date_cols)
                
                if items_found:
                    company_metrics = calculate_ratios_from_financial_statement(items_found)
                    
                    if company_metrics:
                        company_name = st.text_input("Company name:", value="Company")
                        
                        tab1, tab2, tab3, tab4 = st.tabs(["Frame 1", "Frame 2", "Frame 3", "Frame 4"])
                        
                        with tab1:
                            frame1_analysis(None, None, company_name, company_metrics, extraction_note, items_found)
                        
                        with tab2:
                            st.warning("⚠️ Dataset required")
                        
                        with tab3:
                            st.warning("⚠️ Dataset, WACC, Contacts required")
                        
                        with tab4:
                            frame4_placeholder()
        
        except Exception as e:
            st.error(f"Error: {str(e)}")

def show_search(df, waccmap, contacts_df):
    """Display search interface"""
    st.subheader("🏢 Review Company")
    name_query = st.text_input("Search company")
    
    if not name_query:
        st.info("Enter company name")
        return
    
    filtered_df = df[df['company'].str.contains(name_query, case=False, na=False)]
    
    if filtered_df.empty:
        st.warning(f"No companies found")
        return
    
    st.write(f"Found {len(filtered_df)} company(ies)")
    
    for i, r in filtered_df.iterrows():
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Company:** {r['company']}")
            st.write(f"**Revenue:** €{r['revenue']:,.0f}")
        with col2:
            st.write(f"**Category:** {r['category_code']}")
            st.write(f"**Employees:** {r['employees']}")
        
        st.markdown("---")
        
        analysis_file = st.file_uploader(f"Upload FS for {r['company']}", type="xlsx", key=f"analysis_{i}")
        
        if analysis_file:
            try:
                df_analysis = pd.read_excel(analysis_file)
                date_cols = extract_date_columns(df_analysis)
                
                if date_cols:
                    items_found, extraction_note = extract_financial_statement_data(df_analysis, date_cols)
                    
                    if items_found:
                        company_metrics = calculate_ratios_from_financial_statement(items_found)
                        
                        if company_metrics:
                            tab1, tab2, tab3, tab4 = st.tabs(["Frame 1", "Frame 2", "Frame 3", "Frame 4"])
                            
                            dcf_result = None
                            
                            with tab1:
                                frame1_analysis(df, waccmap, r['company'], company_metrics, extraction_note, items_found)
                            
                            with tab2:
                                dcf_result = frame2_valuation(waccmap, r, company_metrics, items_found)
                            
                            with tab3:
                                if dcf_result:
                                    frame3_predictability(df, waccmap, contacts_df, r, company_metrics, dcf_result)
                                else:
                                    st.warning("⚠️ Complete Frame 2 first")
                            
                            with tab4:
                                frame4_placeholder()
            
            except Exception as e:
                st.error(f"Error: {str(e)}")

def main():
    st.set_page_config(page_title="Incrolink Agent", layout="wide")
    
    st.title("Incrolink Agent")
    try:
        st.logo("logoincrolink1.jpeg")
    except:
        pass
    
    st.markdown("**Automated DCF Valuation Platform**")
    st.markdown("---")
    
    st.sidebar.header("📁 Data Configuration")
    
    dataset_file = st.sidebar.file_uploader("Dataset (XLSX)", type="xlsx", key="dataset")
    wacc_file = st.sidebar.file_uploader("WACC Map (XLSX)", type="xlsx", key="wacc")
    contacts_file = st.sidebar.file_uploader("Contacts (XLSX) - Optional", type="xlsx", key="contacts")
    
    contacts_df = None
    if contacts_file:
        try:
            contacts_df = pd.read_excel(contacts_file)
            st.sidebar.success("✅ Contacts loaded")
        except:
            st.sidebar.error("❌ Contacts error")
    
    if not dataset_file or not wacc_file:
        st.info("📊 Early Mode: Upload FS for Frame 1")
        show_standalone_frames()
    else:
        try:
            df = pd.read_excel(dataset_file)
            waccmap = pd.read_excel(wacc_file)
            
            if validate_columns(df, "Dataset"):
                st.sidebar.metric("Companies", len(df))
                show_search(df, waccmap, contacts_df)
        
        except Exception as e:
            st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
