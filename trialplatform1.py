import streamlit as st
import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from datetime import datetime
import pathlib

# ============================================================================
# CUSTOM STYLING - Modern Design with White Sidebar & Shadow
# ============================================================================
def load_css(file_path):
    with open(file_path) as f:
        st.html(f"<style>{f.read()}</style>")
        
css_path= pathlib.Path("style.css")
load_css(css_path)
    

# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================
COLUMNS_REQUIRED = [
    "company", "nace", "ebit", "employees", "net income", "capex", "d&a",
    "changes in wc", "lt debt", "st debt", "sh equity", "capital equity", "cash", "category_code"
]

# Updated: Portfolio now has same structure as Dataset
COLUMNS_PORTFOLIO = [
    "company", "nace", "ebit", "employees", "net income", "capex", "d&a",
    "changes in wc", "lt debt", "st debt", "sh equity", "capital equity", "cash", "category_code"
]

# Financial statement line items to extract
FINANCIAL_ITEMS = {
    'long_term_debt': 'Long term debt',
    'shareholders_funds': 'Shareholders funds',
    'operating_revenue': 'Operating revenue (Turnover)',
    'cost_of_employees': 'Costs of employees',
    'ebitda': 'EBITDA'
}

# Predictability categories
PREDICTABILITY_CATEGORIES = {
    "0": "low growth",
    "0,23": "good growth, low sell side operations",
    "0,43": "good financials and sector conditions, but Management too young",
    "0,54": "good company and sector conditions, but revenue is too small",
    "0,65": "optimal conditions, but margins are weak",
    "0,8": "optimal conditions"
}

# ============================================================================
# UTILITY FUNCTIONS (ALL ALGORITHMS UNCHANGED)
# ============================================================================
def validate_columns(df, file_type="Dataset", required_cols=None):
    """Validate that the dataframe has all required columns"""
    if required_cols is None:
        required_cols = COLUMNS_REQUIRED
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.error(f"❌ {file_type} - Missing required columns: {', '.join(missing_cols)}")
        return False
    st.success(f"✅ {file_type} uploaded")
    return True

def extract_date_columns(df):
    """Extract date columns from dataframe (date format like 31/12/2024)"""
    date_cols = []
    for col in df.columns:
        if col == 'value':
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
    """Calculate LTDE, EDAMARGIN, FX ratios from extracted financial statement data"""
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

def calculate_metrics_from_dataset(company_row):
    """Calculate LTDE, FX, EDAMARGIN from dataset columns"""
    metrics = {}
    try:
        # LTDE: Long-term debt / Shareholders equity
        lt_debt = company_row.get('lt debt', np.nan)
        sh_equity = company_row.get('sh equity', np.nan)
        if not pd.isna(sh_equity) and sh_equity != 0 and not pd.isna(lt_debt):
            metrics['ltde'] = lt_debt / sh_equity
        else:
            metrics['ltde'] = np.nan
        
        # EDAMARGIN: EBITDA / Revenue (approximation using EBIT + D&A)
        ebit = company_row.get('ebit', np.nan)
        d_and_a = company_row.get('d&a', np.nan)
        
        # Since revenue is not in dataset, we calculate approximate EBITDA margin
        # We'll compute from available data or set to NaN
        metrics['edamargin'] = np.nan
        
        # FX: Cost of employees / Revenue (not directly in dataset, set to NaN)
        metrics['fx'] = np.nan
        
        return metrics
    except Exception as e:
        return {'ltde': np.nan, 'edamargin': np.nan, 'fx': np.nan}

def get_company_category_code(company_name, dataset_df):
    """Lookup company's category_code from dataset"""
    matching_companies = dataset_df[dataset_df['company'].str.contains(company_name, case=False, na=False)]
    if not matching_companies.empty:
        category_code = matching_companies.iloc[0]['category_code']
        return category_code
    return None

def get_sector_percentiles(category_code, waccmap):
    """Retrieve sector percentile ranges for LTDE, EDAMARGIN, FX"""
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
        # Add nsellside for Frame 3 predictability
        percentiles['nsellside_p50'] = row.get('nsellside50th', np.nan)
        percentiles['nsellside'] = row.get('nsellside', np.nan)
    return percentiles

def get_percentile_position(value, percentiles_dict):
    """Calculate company's percentile position within sector range"""
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
    """Get CEO age from contacts file via companyID"""
    if contacts_df is None:
        return None
    if 'companyID' not in company_row.index:
        return None
    company_id = company_row['companyID']
    if 'companyID' not in contacts_df.columns:
        return None
    company_contacts = contacts_df[contacts_df['companyID'] == company_id]
    if company_contacts.empty:
        return None
    if 'CEO' in company_contacts.columns and 'age' in company_contacts.columns:
        ceo_row = company_contacts[company_contacts['CEO'].notna()]
        if not ceo_row.empty:
            try:
                return float(ceo_row.iloc[0]['age'])
            except:
                return None
    return None

def get_contacts_by_company_id(company_id, contacts_df):
    """Get all contacts for a company by companyID"""
    if contacts_df is None:
        return None
    if 'companyID' not in contacts_df.columns:
        return None
    company_contacts = contacts_df[contacts_df['companyID'] == company_id]
    return company_contacts if not company_contacts.empty else None

def get_contact_by_id(contact_id, contacts_df):
    """Get specific contact by contactID"""
    if contacts_df is None or 'contactID' not in contacts_df.columns:
        return None
    contact = contacts_df[contacts_df['contactID'] == contact_id]
    return contact.iloc[0] if not contact.empty else None

def get_related_contacts_by_relative(contact_id, contacts_df):
    """
    Get contacts that have relationship with given contact via 'relative' column
    Returns DataFrame of all contacts where relative == contact_id
    """
    if contacts_df is None:
        return None
    if 'contactID' not in contacts_df.columns or 'relative' not in contacts_df.columns:
        return None
    # Find all contacts where the 'relative' column equals the given contact_id
    related = contacts_df[contacts_df['relative'] == contact_id]
    return related if not related.empty else None

def predictability_decision_tree(ev_growth, nsellside, nsellside_p50, ceo_age, revenue, edamargin, edamargin_p75):
    """Decision tree for predictability classification"""
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

def create_filtered_search(db, portfolio_df, nace_mapping, waccmap, contacts_df):
    """Create filtered search interface for deal matching with sell side and monitored categories"""
    st.subheader("🔍 Search for Deals - Match Portfolio Companies")
    
    # Step 1: Select search category
    st.write("**Step 1: Select Search Category**")
    search_category = st.radio(
        "Choose your search focus:",
        options=["Sell Side", "Follow On Monitored"],
        horizontal=True,
        help="Sell Side: Companies for acquisition opportunities | Follow On Monitored: Work in progress"
    )
    
    if search_category == "Follow On Monitored":
        st.info("🚧 **Follow On Monitored** - This feature is currently work in progress. Please check back later!")
        return None
    
    st.markdown("---")
    
    # Step 2: Select investment style
    st.write("**Step 2: Select Investment Style**")
    investment_style = st.radio(
        "Choose your preferred investment style:",
        options=["Top Picks", "Add On", "Good Deals"],
        horizontal=True,
        help="Top Picks: >20% growth | Good Deals: 0-20% growth | Add On: Additional opportunities"
    )
    
    st.markdown("---")
    
    # Step 3: Process Sell Side Logic
    st.write("**Step 3: Analyzing Sell Side Opportunities...**")
    
    # Calculate metrics for all companies in db
    with st.spinner("Calculating financial metrics for all companies..."):
        db_with_metrics = db.copy()
        
        # Calculate ltde, fx, edamargin for each company
        metrics_list = []
        for idx, row in db_with_metrics.iterrows():
            metrics = calculate_metrics_from_dataset(row)
            metrics_list.append(metrics)
        
        metrics_df = pd.DataFrame(metrics_list)
        db_with_metrics['ltde'] = metrics_df['ltde']
        db_with_metrics['fx'] = metrics_df['fx']
        db_with_metrics['edamargin'] = metrics_df['edamargin']
        
        # Compute weighted score: 0.5*ltde + 0.35*fx + 0.15*edamargin
        db_with_metrics['weighted_score'] = (
            0.5 * db_with_metrics['ltde'].fillna(0) + 
            0.35 * db_with_metrics['fx'].fillna(0) + 
            0.15 * db_with_metrics['edamargin'].fillna(0)
        )
        
        # Extract 90th percentile companies -> list_b
        percentile_90 = db_with_metrics['weighted_score'].quantile(0.90)
        list_b = db_with_metrics[db_with_metrics['weighted_score'] >= percentile_90].copy()
        
        st.success(f"✅ Identified {len(list_b)} companies at or above 90th percentile (weighted score: {percentile_90:.4f})")
    
    st.markdown("---")
    
    # Step 4: Match with portfolio companies
    st.write("**Step 4: Matching with Portfolio Companies**")
    st.write(f"**Portfolio Companies:** {len(portfolio_df)} companies")
    
    # list_a: portfolio companies
    list_a = portfolio_df.copy()
    
    # Match based on category_code
    list_c = []
    buyer_fit_messages = []
    
    for idx_a, company_a in list_a.iterrows():
        # Get category_code for portfolio company
        category_a = company_a.get('category_code', None)
        
        if category_a is None:
            continue
        
        # Find matching companies in list_b by category_code
        matched_b = list_b[list_b['category_code'] == category_a]
        
        for idx_b, company_b in matched_b.iterrows():
            # Revenue comparison (using 'ebit' as proxy for financial capacity)
            ebit_a = company_a.get('ebit', 0)
            ebit_b = company_b.get('ebit', 0)
            
            if ebit_a >= ebit_b:
                buyer_fit_msg = f"Company **{company_a['company']}** is a good buyer fit for **{company_b['company']}**"
            else:
                buyer_fit_msg = f"Company **{company_b['company']}** is a good buyer fit for **{company_a['company']}**"
            
            buyer_fit_messages.append(buyer_fit_msg)
            list_c.append({
                'portfolio_company': company_a['company'],
                'target_company': company_b['company'],
                'category_code': category_a,
                'portfolio_ebit': ebit_a,
                'target_ebit': ebit_b,
                'buyer_fit': buyer_fit_msg,
                'target_data': company_b
            })
    
    if not list_c:
        st.warning("⚠️ No matches found between portfolio and 90th percentile companies.")
        return None
    
    st.success(f"✅ Found {len(list_c)} potential matches")
    
    # Display buyer fit messages
    with st.expander("📊 View Buyer Fit Analysis"):
        for msg in buyer_fit_messages[:10]:  # Show first 10
            st.info(msg)
    
    st.markdown("---")
    
    # Step 5: Calculate DCF for list_c companies
    st.write("**Step 5: Running DCF Valuation for Matched Companies...**")
    
    dcf_results = []
    for item in list_c:
        target_data = item['target_data']
        try:
            dcf_result = DCF_automated(target_data, waccmap)
            growth_expected = dcf_result['growth_expected']
            
            # Classify based on growth
            if growth_expected < 0:
                classification = "Bit Overvalued"
            elif 0 <= growth_expected < 0.20:
                classification = "Good Deal"
            else:  # growth_expected >= 0.20
                classification = "Top Pick"
            
            item['dcf_result'] = dcf_result
            item['growth_expected'] = growth_expected
            item['classification'] = classification
            dcf_results.append(item)
        except Exception as e:
            st.warning(f"Could not calculate DCF for {item['target_company']}: {str(e)}")
            continue
    
    if not dcf_results:
        st.error("❌ No DCF results available")
        return None
    
    st.success(f"✅ DCF calculated for {len(dcf_results)} companies")
    
    st.markdown("---")
    
    # Step 6: Filter by investment style
    st.write(f"**Step 6: Filtering by Investment Style: {investment_style}**")
    
    if investment_style == "Top Picks":
        filtered_results = [r for r in dcf_results if r['classification'] == "Top Pick"]
    elif investment_style == "Good Deals":
        filtered_results = [r for r in dcf_results if r['classification'] == "Good Deal"]
    else:  # Add On
        filtered_results = dcf_results  # Show all for now
    
    if not filtered_results:
        st.warning(f"⚠️ No companies match the '{investment_style}' criteria.")
        return None
    
    st.success(f"✅ Found {len(filtered_results)} companies matching '{investment_style}'")
    
    # Step 7: Display results and ask user
    st.markdown("---")
    st.subheader("🎯 Recommended Opportunities")
    
    company_names = [r['target_company'] for r in filtered_results]
    companies_str = ", ".join(company_names[:5])
    if len(company_names) > 5:
        companies_str += f", and {len(company_names) - 5} more"
    
    st.info(f"**Companies such as {companies_str}, seem to match your preferences. Do you want to know more about them?**")
    
    user_choice = st.radio(
        "Your choice:",
        options=["Yes", "No"],
        horizontal=True,
        key="user_interest_choice"
    )
    
    if user_choice == "No":
        st.success("✅ Ok, I'll keep them monitored for you!")
        return None
    
    # Step 8: If Yes, show detailed analysis
    st.markdown("---")
    st.subheader("📊 Detailed Company Analysis")
    
    # Let user select which company to analyze
    selected_idx = st.selectbox(
        "Select a company for detailed analysis:",
        range(len(filtered_results)),
        format_func=lambda i: f"{filtered_results[i]['target_company']} - {filtered_results[i]['classification']} ({filtered_results[i]['growth_expected']:.2%} growth)"
    )
    
    selected_result = filtered_results[selected_idx]
    target_company_row = selected_result['target_data']
    dcf_result = selected_result['dcf_result']
    
    st.write(f"**Analyzing: {selected_result['target_company']}**")
    st.write(f"**Classification:** {selected_result['classification']}")
    st.write(f"**Expected Growth:** {selected_result['growth_expected']:.2%}")
    
    st.markdown("---")
    
    # Ask for financial statement upload for detailed analysis
    st.write("**Upload Financial Statement for In-Depth Analysis:**")
    analysis_file = st.file_uploader(
        f"Upload Financial Statement (XLSX) for {selected_result['target_company']}",
        type="xlsx",
        key="detailed_analysis_upload",
        help="Upload financial statement with Value column and date columns (format: 31/12/2024)"
    )
    
    if analysis_file:
        try:
            df_analysis = pd.read_excel(analysis_file)
            st.info("📂 File uploaded successfully")
            
            date_cols = extract_date_columns(df_analysis)
            if date_cols:
                st.write(f"**Latest year:** {date_cols[0]}")
                
                items_found, extraction_note = extract_financial_statement_data(df_analysis, date_cols)
                
                if items_found:
                    company_metrics = calculate_ratios_from_financial_statement(items_found)
                    
                    if company_metrics:
                        # Run full analysis in tabs
                        tab1, tab2, tab3, tab4 = st.tabs([
                            "Frame 1: FS Analysis",
                            "Frame 2: Valuation",
                            "Frame 3: Predictable",
                            "Frame 4: Contacts"
                        ])
                        
                        with tab1:
                            frame1_analysis(db, waccmap, selected_result['target_company'], 
                                          company_metrics, extraction_note, items_found)
                        
                        with tab2:
                            frame2_valuation(waccmap, target_company_row, company_metrics, items_found)
                        
                        with tab3:
                            frame3_predictability(db, waccmap, contacts_df, target_company_row, 
                                                company_metrics, dcf_result)
                        
                        with tab4:
                            frame4_contacts(target_company_row, contacts_df)
                    else:
                        st.error("Could not calculate ratios from extracted data")
                else:
                    st.warning("Could not extract financial statement items")
            else:
                st.error("No date columns found")
        
        except Exception as e:
            st.error(f"Error loading analysis file: {str(e)}")
    else:
        st.info("💡 Upload a financial statement file to run complete analysis")
    
    return selected_result

def frame1_analysis(dataset_df, waccmap, company_name, company_metrics, extraction_note, items_found):
    """Frame 1: Analysis with metrics calculation and sector comparison"""
    st.subheader("📊 Frame 1: Financial Metrics Analysis")
    
    category_code = get_company_category_code(company_name, dataset_df) if dataset_df is not None else None
    
    st.write(f"**Analysis for:** {company_name}")
    st.write(f"**Data Source:** {extraction_note}")
    
    if category_code:
        st.write(f"**Category Code:** {category_code}")
    else:
        if dataset_df is not None:
            st.warning(f"⚠️ Category code not found for {company_name} in dataset")
    
    st.markdown("---")
    
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
    
    if category_code and dataset_df is not None:
        sector_percentiles = get_sector_percentiles(category_code, waccmap)
        
        st.subheader("📈 Company Metrics vs. Sector Benchmarks")
        st.write(f"*Comparing against {category_code} sector (10th, 25th, 50th, 75th, 90th percentiles)*")
        st.markdown("---")
        
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

def frame2_valuation(waccmap, company_row, company_metrics, items_found):
    """Frame 2: DCF Valuation & Analysis"""
    st.subheader("💰 Frame 2: Valuation")
    
    if company_row is None:
        st.info("❌ Company dataset information not available")
        return None
    
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
    
    return dcf_result

def frame3_predictability(dataset_df, waccmap, contacts_df, company_row, company_metrics, dcf_result):
    """Frame 3: Predictability Analysis with Decision Tree"""
    st.subheader("🎯 Frame 3: Predictable")
    
    if company_row is None or dcf_result is None:
        st.warning("⚠️ Dataset and DCF analysis required")
        return
    
    st.write(f"**Company:** {company_row['company']}")
    st.markdown("---")
    
    # Extract required parameters
    ev_growth = dcf_result['growth_expected']
    revenue = company_row.get('net income', np.nan)  # Use net income as proxy for revenue
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
    st.write("**Input Parameters:**")
    input_col1, input_col2 = st.columns(2)
    
    with input_col1:
        st.write(f"• EV Growth: {ev_growth:.2%}")
        st.write(f"• Net Income: €{revenue:,.0f}" if not np.isnan(revenue) else "• Net Income: N/A")
        st.write(f"• EDAMARGIN: {edamargin:.4f}" if not np.isnan(edamargin) else "• EDAMARGIN: N/A")
    
    with input_col2:
        st.write(f"• N Sell Side: {nsellside:.0f}" if not np.isnan(nsellside) else "• N Sell Side: N/A")
        st.write(f"• CEO Age: {ceo_age:.0f}" if ceo_age is not None else "• CEO Age: N/A")
        st.write(f"• EDAMARGIN P75: {edamargin_p75:.4f}" if not np.isnan(edamargin_p75) else "• EDAMARGIN P75: N/A")
    
    st.markdown("---")
    
    st.subheader("📍 Decision Path")
    for i, step in enumerate(path, 1):
        st.write(f"**Step {i}:** {step}")
    
    st.markdown("---")
    
    st.subheader("🎯 Classification Result")
    result_col1, result_col2 = st.columns(2)
    
    with result_col1:
        st.metric("Leaf Value", leaf_value)
    with result_col2:
        st.metric("Category", category)
    
    st.markdown("---")
    
    st.info("""
    **Sell Side:** Low growth (EV < 15%)
    **Buy Side:** High growth, low sector activity
    **Financing Opportunity:** High growth with specific characteristics
    **Undetected:** High performing company
    """)

def frame4_contacts(company_row, contacts_df):
    """Frame 4: Contact Linkage and Network Matching"""
    st.subheader("📇 Frame 4: Contacts")
    
    if company_row is None:
        st.warning("⚠️ Company data required")
        return
    
    if contacts_df is None:
        st.warning("⚠️ Contacts file required")
        return
    
    st.write(f"**Company:** {company_row['company']}")
    st.markdown("---")
    
    # Get companyID
    company_id = company_row.get('companyID', None)
    if company_id is None:
        st.error("❌ No companyID found in company data")
        return
    
    # Lookup contacts for this company
    company_contacts = get_contacts_by_company_id(company_id, contacts_df)
    
    if company_contacts is None or company_contacts.empty:
        st.warning(f"⚠️ No contacts found for company ID: {company_id}")
        return
    
    st.write(f"**Found {len(company_contacts)} contact(s)**")
    
    # Select contact
    contact_idx = st.selectbox(
        "Select a contact:",
        range(len(company_contacts)),
        format_func=lambda i: f"{company_contacts.iloc[i].get('name', 'Unknown')} - {company_contacts.iloc[i].get('role', 'Unknown')}"
    )
    
    selected_contact = company_contacts.iloc[contact_idx]
    contact_name = selected_contact.get('name', 'Unknown')
    contact_role = selected_contact.get('role', 'Unknown')
    contact_id = selected_contact.get('contactID', None)
    
    st.markdown("---")
    st.success(f"✅ I found a match for **{contact_name}** - **{contact_role}**")
    st.markdown("---")
    
    # ACTION FRAME 1: Contact Linkage
    st.subheader("🔗 Frame 1: Contact Linkage")
    st.write("**Choose a communication channel:**")
    
    col1, col2, col3 = st.columns(3)
    
    # LinkedIn button
    has_linkedin = pd.notna(selected_contact.get('linkedin', None)) and selected_contact.get('linkedin', '').strip() != ''
    with col1:
        if st.button("💼 Chat on LinkedIn", disabled=not has_linkedin, key="linkedin_btn"):
            st.markdown("---")
            message_option = st.radio("What would you like to do?", ["Send Message", "Get Link"], key="linkedin_option")
            if message_option == "Send Message":
                st.info("""
                **Preset Introduction Message:**
                Hi {name},
                I found your profile through my professional network and I'm impressed with your background in {role}.
                I'd like to discuss potential opportunities for collaboration.
                Looking forward to connecting!
                """)
                if st.button("📤 Send Message", key="send_linkedin_msg"):
                    st.success("✅ Message sent via LinkedIn!")
            elif message_option == "Get Link":
                linkedin_url = selected_contact.get('linkedin', '')
                st.markdown(f"**[Here]({linkedin_url})** is the LinkedIn profile link")
                st.success("✅ Link ready to share!")
    
    # Mobile button
    has_mobile = pd.notna(selected_contact.get('mobile', None)) and selected_contact.get('mobile', '').strip() != ''
    with col2:
        if st.button("📱 Call", disabled=not has_mobile, key="mobile_btn"):
            mobile = selected_contact.get('mobile', 'N/A')
            st.markdown("---")
            st.write(f"**Phone Number:** {mobile}")
            st.info("☎️ Ready to call!")
    
    # Email button
    has_email = pd.notna(selected_contact.get('email', None)) and selected_contact.get('email', '').strip() != ''
    with col3:
        if st.button("✉️ Send Email", disabled=not has_email, key="email_btn"):
            st.markdown("---")
            email_option = st.radio("What would you like to do?", ["Write Introduction", "Show Email"], key="email_option")
            if email_option == "Write Introduction":
                st.info("""
                **Preset Introduction Email:**
                Subject: Professional Opportunity
                
                Dear {name},
                I hope this message finds you well.
                I've reviewed your professional profile and believe there may be valuable synergies between our organizations.
                I'd appreciate the opportunity to discuss potential collaboration.
                Please let me know your availability for a brief call.
                
                Best regards
                """)
                if st.button("📧 Send Email", key="send_email"):
                    st.success("✅ Email sent!")
            elif email_option == "Show Email":
                email = selected_contact.get('email', 'N/A')
                st.write(f"**Email:** {email}")
                st.info("✉️ Email ready to use!")
    
    if not has_linkedin and not has_mobile and not has_email:
        st.warning("⚠️ No contact information available for this contact")
    
    st.markdown("---")
    
    # ACTION FRAME 2: Network Match
    st.subheader("🌐 Frame 2: Network Match")
    st.write(f"**Looking up network connections for:** {contact_name}")
    
    if contact_id is None:
        st.warning("⚠️ Contact ID not found")
    else:
        # Check for related contacts (network match)
        related_contacts = get_related_contacts_by_relative(contact_id, contacts_df)
        
        if related_contacts is not None and not related_contacts.empty:
            st.success(f"✅ I found {len(related_contacts)} match(es) already in your contact list!")
            st.markdown("---")
            
            for idx, (row_idx, related) in enumerate(related_contacts.iterrows()):
                related_name = related.get('name', 'Unknown')
                related_role = related.get('role', 'Unknown')
                related_linkedin = related.get('linkedin', '')
                related_mobile = related.get('mobile', '')
                related_email = related.get('email', '')
                
                st.write(f"**{related_name}** - {related_role}")
                st.info(f"📇 Contact Info: {related_email} | {related_mobile}")
                
                should_contact = st.radio(
                    f"Should we contact {related_name}?",
                    ["No", "Yes"],
                    key=f"contact_related_{idx}"
                )
                
                if should_contact == "Yes":
                    st.write("**Choose a communication channel:**")
                    related_col1, related_col2, related_col3 = st.columns(3)
                    
                    has_linkedin_rel = pd.notna(related_linkedin) and related_linkedin.strip() != ''
                    with related_col1:
                        if st.button(f"💼 LinkedIn - {related_name}", disabled=not has_linkedin_rel, key=f"linkedin_related_{idx}"):
                            if related_linkedin:
                                st.markdown(f"**[Here]({related_linkedin})**")
                                st.success("✅ LinkedIn link ready!")
                    
                    has_mobile_rel = pd.notna(related_mobile) and related_mobile.strip() != ''
                    with related_col2:
                        if st.button(f"📱 Call - {related_name}", disabled=not has_mobile_rel, key=f"mobile_related_{idx}"):
                            st.write(f"**Phone:** {related_mobile}")
                            st.success("☎️ Ready to call!")
                    
                    has_email_rel = pd.notna(related_email) and related_email.strip() != ''
                    with related_col3:
                        if st.button(f"✉️ Email - {related_name}", disabled=not has_email_rel, key=f"email_related_{idx}"):
                            st.write(f"**Email:** {related_email}")
                            st.success("✉️ Email ready!")
                
                st.markdown("---")
        else:
            st.info("ℹ️ No network matches found in your contact list.")
            st.write("**Suggested Events to Expand Your Network:**")
            
            # Display sample events
            events_col1, events_col2, events_col3 = st.columns(3)
            sample_events = {
                "E001": {"name": "London Tech Summit 2025", "date": "2025-03-15", "industry": "Technology"},
                "E002": {"name": "Financial Innovation Forum", "date": "2025-04-22", "industry": "Finance"},
                "E003": {"name": "Healthcare Sector Conference", "date": "2025-05-10", "industry": "Healthcare"},
                "E004": {"name": "Manufacturing Excellence Summit", "date": "2025-06-05", "industry": "Manufacturing"},
                "E005": {"name": "Retail & E-Commerce Forum", "date": "2025-07-20", "industry": "Retail"},
                "E006": {"name": "Industrial Leaders Convention", "date": "2025-08-15", "industry": "Industrial"},
            }
            
            with events_col1:
                for event_id, event_info in list(sample_events.items())[:2]:
                    st.write(f"📅 **{event_info['name']}**")
                    st.write(f"📍 {event_info['date']}")
                    st.write(f"🏢 {event_info['industry']}")
                    st.markdown("---")
            
            with events_col2:
                for event_id, event_info in list(sample_events.items())[2:4]:
                    st.write(f"📅 **{event_info['name']}**")
                    st.write(f"📍 {event_info['date']}")
                    st.write(f"🏢 {event_info['industry']}")
                    st.markdown("---")
            
            with events_col3:
                for event_id, event_info in list(sample_events.items())[4:]:
                    st.write(f"📅 **{event_info['name']}**")
                    st.write(f"📍 {event_info['date']}")
                    st.write(f"🏢 {event_info['industry']}")
                    st.markdown("---")

def show_search(df, waccmap, contacts_df):
    """Display search interface and run analysis"""
    st.subheader("🏢 Review Company - Evaluate Individual Company")
    
    name_query = st.text_input("Search company name (case-insensitive, substring allowed)")
    
    if not name_query:
        st.info("Enter a company name to search")
        return
    
    filtered_df = df[df['company'].str.contains(name_query, case=False, na=False)]
    
    if filtered_df.empty:
        st.warning(f"No companies found matching '{name_query}'")
        return
    
    st.write(f"Found {len(filtered_df)} company(ies)")
    
    for i, r in filtered_df.iterrows():
        st.markdown("---")
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
        
        st.markdown("---")
        
        st.subheader("📈 Company Analysis Review")
        analysis_file = st.file_uploader(
            f"Upload Financial Statement (XLSX) for {r['company']}",
            type="xlsx",
            key=f"analysis_upload_{i}",
            help="Upload financial statement with Value column and date columns (format: 31/12/2024)"
        )
        
        if analysis_file:
            try:
                df_analysis = pd.read_excel(analysis_file)
                st.info("📂 File structure detected:")
                
                date_cols = extract_date_columns(df_analysis)
                if date_cols:
                    st.write(f"**Latest year:** {date_cols[0]}")
                    
                    items_found, extraction_note = extract_financial_statement_data(df_analysis, date_cols)
                    
                    if items_found:
                        company_metrics = calculate_ratios_from_financial_statement(items_found)
                        
                        if company_metrics:
                            dcf_result_tab = None
                            tab1, tab2, tab3, tab4 = st.tabs([
                                "Frame 1: FS analysis",
                                "Frame 2: Valuation",
                                "Frame 3: Predictable",
                                "Frame 4: Contacts"
                            ])
                            
                            with tab1:
                                frame1_analysis(df, waccmap, r['company'], company_metrics, extraction_note, items_found)
                            
                            with tab2:
                                dcf_result_tab = frame2_valuation(waccmap, r, company_metrics, items_found)
                            
                            with tab3:
                                if dcf_result_tab:
                                    frame3_predictability(df, waccmap, contacts_df, r, company_metrics, dcf_result_tab)
                                else:
                                    st.warning("⚠️ Complete Frame 2 DCF analysis first")
                            
                            with tab4:
                                frame4_contacts(r, contacts_df)
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

def main():
    st.markdown("""
    """, unsafe_allow_html=True)
    st.set_page_config(page_title="Incrolink Agent", layout="wide", initial_sidebar_state="expanded")
    st.title("Incrolink Agent")
    
    try:
        st.logo("iconincro.png", size="medium", icon_image="iconincro.png")
    except:
        pass
    
    st.markdown("---")
    
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
        help="Upload portfolio companies for deal matching (now with same structure as Dataset)"
    )
    
    contacts_file = st.sidebar.file_uploader(
        "Upload Contacts (XLSX) - Optional",
        type="xlsx",
        key="contacts_uploader",
        help="Upload contacts file with companyID, contactID, name, role, linkedin, mobile, email, relative columns (optional)"
    )
    
    contacts_df = None
    if contacts_file:
        try:
            contacts_df = pd.read_excel(contacts_file)
            st.sidebar.success("✅ Contacts file loaded")
        except:
            st.sidebar.error("❌ Error loading contacts file")
    
    if dataset_file and wacc_file:
        try:
            df = pd.read_excel(dataset_file)
            waccmap = pd.read_excel(wacc_file)
            
            if validate_columns(df, "Dataset"):
                st.sidebar.metric("Companies Loaded", len(df))
                st.sidebar.metric("Categories", df['category_code'].nunique())
                
                st.markdown("---")
                
                st.subheader("🎯 Select Workflow Mode")
                workflow_mode = st.radio(
                    "Choose your analysis mode:",
                    options=["Review Company", "Search for Deals"],
                    horizontal=True,
                    help="Review Company: Evaluate individual companies | Search for Deals: Match portfolio companies"
                )
                
                st.markdown("---")
                
                if workflow_mode == "Review Company":
                    show_search(df, waccmap, contacts_df)
                
                elif workflow_mode == "Search for Deals":
                    if portfolio_file is None:
                        st.warning("⚠️ Portfolio file is required for deal matching. Please upload it in the sidebar.")
                    else:
                        try:
                            portfolio_df = pd.read_excel(portfolio_file)
                            if validate_columns(portfolio_df, "Portfolio", COLUMNS_PORTFOLIO):
                                st.sidebar.metric("Portfolio Companies", len(portfolio_df))
                                
                                selected_result = create_filtered_search(df, portfolio_df, None, waccmap, contacts_df)
                        
                        except Exception as e:
                            st.error(f"Error loading portfolio file: {str(e)}")
            else:
                st.stop()
        
        except Exception as e:
            st.error(f"Error loading files: {str(e)}")
    else:
        st.info("👈 Please upload your data files in the sidebar to proceed.")
        
        with st.expander("📋 Required Columns Reference"):
            st.write("**Dataset must include:**")
            for col in COLUMNS_REQUIRED:
                st.text(f"• {col}")
            
            st.write("**Portfolio file (now requires SAME columns as Dataset):**")
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
            st.write("• nsellside, nsellside50th (for Frame 3 predictability)")
            
            st.write("**Contacts file (optional) format:**")
            st.write("• companyID, contactID, name, role, linkedin, mobile, email, relative")

if __name__ == "__main__":
    main()



















