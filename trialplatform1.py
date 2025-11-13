import streamlit as st
import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from datetime import datetime
import pathlib
import requests
from io import BytesIO

# ============================================================================
# CUSTOM STYLING - Modern Design with White Sidebar & Shadow
# ============================================================================
def load_css(file_path):
    with open(file_path) as f:
        st.html(f"<style>{f.read()}</style>")

css_path = pathlib.Path("style.css")
load_css(css_path)

# ============================================================================
# DROPBOX URL CONFIGURATION - Embedded Data Sources
# ============================================================================
DROPBOX_URLS = {
    'financial_statements': 'https://www.dropbox.com/scl/fi/2f955nt6zbclfwz3nnz60/volkfs.xlsx?rlkey=0pln5j0rpxmk0542158w75nov&st=euznhfrn&dl=1',
    'dataset': 'https://www.dropbox.com/scl/fi/xp7lqxzym0ddwyjx1adeh/datasetincro1.xlsx?rlkey=a1zrwfo2d1mvi9got93wtj3zy&st=pd8cfono&dl=1',
    'portfolio': 'https://www.dropbox.com/scl/fi/ifa8h5qv593pd9x8q67l2/db.xlsx?rlkey=pux8db90ltdhfyb3gtbrto3zx&st=45s8uk9k&dl=1',
    'wacc': 'https://www.dropbox.com/scl/fi/x2u50g51sa8xuvf2ibjpg/wacc.xlsx?rlkey=sau1mzibsh7ndy6uwx76rvj2m&st=7eyj1pah&dl=1'
}

# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================
COLUMNS_REQUIRED = [
    "company", "nace", "ebit", "employees", "net income", "capex", "d&a",
    "changes in wc", "lt debt", "st debt", "sh equity", "capital equity", "cash", "category_code"
]

COLUMNS_PORTFOLIO = [
    "company", "nace", "ebit", "employees", "net income", "capex", "d&a",
    "changes in wc", "lt debt", "st debt", "sh equity", "capital equity", "cash", "category_code"
]

FINANCIAL_ITEMS = {
    'long_term_debt': 'Long term debt',
    'shareholders_funds': 'Shareholders funds',
    'operating_revenue': 'Operating revenue (Turnover)',
    'cost_of_employees': 'Costs of employees',
    'ebitda': 'EBITDA'
}

PREDICTABILITY_CATEGORIES = {
    "0": "low growth",
    "0,23": "good growth, low sell side operations",
    "0,43": "good financials and sector conditions, but Management too young",
    "0,54": "good company and sector conditions, but revenue is too small",
    "0,65": "optimal conditions, but margins are weak",
    "0,8": "optimal conditions"
}

# ============================================================================
# AUTO-LOAD FUNCTIONS - DROPBOX DATA INTEGRATION
# ============================================================================
def convert_dropbox_url(url):
    """Convert Dropbox share link to direct download link"""
    if '?dl=0' in url:
        return url.replace('?dl=0', '?dl=1')
    if '&dl=0' in url:
        return url.replace('&dl=0', '&dl=1')
    return url + '?dl=1' if '?dl=' not in url else url

def load_file_from_dropbox(dropbox_url):
    """Load Excel file directly from Dropbox URL"""
    try:
        url = convert_dropbox_url(dropbox_url)
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        excel_file = BytesIO(response.content)
        return pd.read_excel(excel_file)
    except Exception as e:
        st.error(f"Error loading file from Dropbox: {str(e)}")
        return None

def load_all_data_from_dropbox():
    """Load all data files from Dropbox URLs"""
    with st.spinner("🔄 Loading data from Dropbox..."):
        data_dict = {}
        
        # Load Dataset
        st.write("📂 Loading Dataset...")
        dataset_df = load_file_from_dropbox(DROPBOX_URLS['dataset'])
        if dataset_df is not None:
            st.success("✅ Dataset loaded successfully")
            data_dict['dataset'] = dataset_df
        else:
            st.error("❌ Failed to load Dataset")
            return None
        
        # Load WACC
        st.write("📂 Loading WACC File...")
        wacc_df = load_file_from_dropbox(DROPBOX_URLS['wacc'])
        if wacc_df is not None:
            st.success("✅ WACC file loaded successfully")
            data_dict['wacc'] = wacc_df
        else:
            st.error("❌ Failed to load WACC")
            return None
        
        # Load Portfolio
        st.write("📂 Loading Portfolio...")
        portfolio_df = load_file_from_dropbox(DROPBOX_URLS['portfolio'])
        if portfolio_df is not None:
            st.success("✅ Portfolio loaded successfully")
            data_dict['portfolio'] = portfolio_df
        else:
            st.warning("⚠️ Portfolio not loaded (optional)")
            data_dict['portfolio'] = None
        
        # Load Financial Statements (optional)
        st.write("📂 Loading Financial Statements...")
        fs_df = load_file_from_dropbox(DROPBOX_URLS['financial_statements'])
        if fs_df is not None:
            st.success("✅ Financial Statements loaded successfully")
            data_dict['financial_statements'] = fs_df
        else:
            st.warning("⚠️ Financial Statements not loaded (optional)")
            data_dict['financial_statements'] = None
    
    return data_dict

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
        lt_debt = company_row.get('lt debt', np.nan)
        sh_equity = company_row.get('sh equity', np.nan)
        if not pd.isna(sh_equity) and sh_equity != 0 and not pd.isna(lt_debt):
            metrics['ltde'] = lt_debt / sh_equity
        else:
            metrics['ltde'] = np.nan
        
        ebit = company_row.get('ebit', np.nan)
        d_and_a = company_row.get('d&a', np.nan)
        metrics['edamargin'] = np.nan
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
    """Get contacts that have relationship with given contact via 'relative' column"""
    if contacts_df is None:
        return None
    if 'contactID' not in contacts_df.columns or 'relative' not in contacts_df.columns:
        return None
    
    related = contacts_df[contacts_df['relative'] == contact_id]
    return related if not related.empty else None

def predictability_decision_tree(ev_growth, nsellside, nsellside_p50, ceo_age, revenue, edamargin, edamargin_p75):
    """Decision tree for predictability classification"""
    path = []
    
    path.append(f"EV Growth: {ev_growth:.2%}")
    if ev_growth < 0.15:
        return "0", PREDICTABILITY_CATEGORIES["0"], path
    
    path.append(f"N Sell Side: {nsellside} vs P50: {nsellside_p50}")
    if not np.isnan(nsellside) and not np.isnan(nsellside_p50) and nsellside < nsellside_p50:
        return "0,23", PREDICTABILITY_CATEGORIES["0,23"], path
    
    path.append(f"CEO Age: {ceo_age}")
    if ceo_age is not None and not np.isnan(ceo_age) and ceo_age < 60:
        return "0,43", PREDICTABILITY_CATEGORIES["0,43"], path
    
    path.append(f"Revenue: €{revenue:,.0f}")
    if not np.isnan(revenue) and revenue < 90000000:
        return "0,54", PREDICTABILITY_CATEGORIES["0,54"], path
    
    path.append(f"EDAMARGIN: {edamargin:.4f} vs P75: {edamargin_p75:.4f}")
    if not np.isnan(edamargin) and not np.isnan(edamargin_p75) and edamargin < edamargin_p75:
        return "0,65", PREDICTABILITY_CATEGORIES["0,65"], path
    
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

def DCF_automated(company_row, waccmap):
    """Automated DCF Valuation (PLACEHOLDER - Unchanged Logic)"""
    try:
        category_code = company_row.get('category_code')
        category_data = waccmap[waccmap['category_code'].astype(str) == str(category_code)]
        
        if not category_data.empty:
            row = category_data.iloc[0]
            wacc = row.get('wacc', 0.08)
            growth_rate = row.get('growth', 0.03)
        else:
            wacc = 0.08
            growth_rate = 0.03
        
        ebit = company_row.get('ebit', 0)
        ebit = float(ebit) if ebit else 0
        
        fcf0 = ebit * 0.75
        
        ev_current = company_row.get('sh equity', 0)
        ev_current = float(ev_current) if ev_current else 0
        
        if wacc > growth_rate:
            fcf1 = fcf0 * (1 + growth_rate)
            ev_dcf = fcf1 / (wacc - growth_rate)
        else:
            ev_dcf = fcf0
        
        growth_expected = (ev_dcf - ev_current) / ev_current if ev_current != 0 else 0
        
        return {
            'EV_current': ev_current,
            'EV_DCF': ev_dcf,
            'FCF0': fcf0,
            'growth_expected': growth_expected,
            'params': {
                're': row.get('re', 0.08) if not category_data.empty else 0.08,
                'rd': row.get('rd', 0.04) if not category_data.empty else 0.04,
                'wacc': wacc,
                'g': growth_rate
            }
        }
    except Exception as e:
        return {
            'EV_current': 0,
            'EV_DCF': 0,
            'FCF0': 0,
            'growth_expected': 0,
            'params': {'re': 0.08, 'rd': 0.04, 'wacc': 0.08, 'g': 0.03}
        }

# ============================================================================
# DISPLAY FUNCTIONS (FRAMES 1-4)
# ============================================================================
def show_search(db, waccmap, contacts_df):
    """Show company search interface (PLACEHOLDER - can be extended)"""
    st.subheader("🔍 Search Companies")
    st.write("Enter company details to search")

# ============================================================================
# MAIN APPLICATION
# ============================================================================
def main():
    st.set_page_config(page_title="Incrolink", layout="wide")
    
    st.title("Back at it!")
    
    st.markdown("---")
    
    # ===== AUTO-LOAD DATA BUTTON =====
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("🚀 let's dat-it-up!", key="auto_load_btn", use_container_width=True):
            st.session_state.auto_load = True
    
    st.markdown("---")
    
    # Check if auto-load was triggered
    if st.session_state.get('auto_load', False):
        data_dict = load_all_data_from_dropbox()
        
        if data_dict:
            st.session_state.dataset_df = data_dict.get('dataset')
            st.session_state.waccmap = data_dict.get('wacc')
            st.session_state.portfolio_df = data_dict.get('portfolio')
            st.session_state.fs_df = data_dict.get('financial_statements')
            st.session_state.auto_load = False  # Reset flag
        else:
            st.stop()
    
    # Manual Upload Section (Backup)
    with st.sidebar:
        st.header("📁 Data Management")
        
        upload_method = st.radio(
            "Choose upload method:",
            ["Auto-Load from Dropbox", "Manual Upload"],
            key="upload_method"
        )
        
        if upload_method == "Manual Upload":
            st.subheader("📤 Upload Files Manually")
            
            dataset_file = st.file_uploader(
                "Upload Dataset (XLSX)",
                type="xlsx",
                key="dataset_uploader",
                help="Excel file with company data"
            )
            
            wacc_file = st.file_uploader(
                "Upload WACC File (XLSX)",
                type="xlsx",
                key="wacc_uploader",
                help="Excel file with WACC and percentile data"
            )
            
            portfolio_file = st.file_uploader(
                "Upload Portfolio (XLSX) - Optional",
                type="xlsx",
                key="portfolio_uploader",
                help="Excel file with portfolio companies"
            )
            
            contacts_file = st.file_uploader(
                "Upload Contacts (XLSX) - Optional",
                type="xlsx",
                key="contacts_uploader",
                help="Upload contacts file"
            )
            
            if dataset_file and wacc_file:
                st.session_state.dataset_df = pd.read_excel(dataset_file)
                st.session_state.waccmap = pd.read_excel(wacc_file)
                st.session_state.portfolio_df = pd.read_excel(portfolio_file) if portfolio_file else None
            
            if contacts_file:
                st.session_state.contacts_df = pd.read_excel(contacts_file)
    
    # Main Application Logic
    dataset_df = st.session_state.get('dataset_df')
    waccmap = st.session_state.get('waccmap')
    
    if dataset_df is not None and waccmap is not None:
        if validate_columns(dataset_df, "Dataset"):
            st.sidebar.metric("Companies Loaded", len(dataset_df))
            st.sidebar.metric("Categories", dataset_df['category_code'].nunique())
            
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
                show_search(dataset_df, waccmap, st.session_state.get('contacts_df'))
    else:
        st.info("👈 Click the 'let's data this up!' button to auto-load data from Dropbox, or upload files manually in the sidebar.")
    
    # Help Section
    with st.expander("📋 Required Columns Reference"):
        st.write("**Dataset must include:**")
        for col in COLUMNS_REQUIRED:
            st.text(f"• {col}")
        
        st.write("**WACC file must include percentile columns:**")
        st.write("• ltde10th, ltde25th, ltde50th, ltde75th, ltde90th")
        st.write("• edamarg10th, edamarg25th, edamarg50th, edamarg75th, edamarg90th")
        st.write("• fx10th, fx25th, fx50th, fx75th, fx90th")
        st.write("• nsellside, nsellside50th (for Frame 3 predictability)")

if __name__ == "__main__":
    main()






















