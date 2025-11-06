import streamlit as st
import pandas as pd
import time

# 1. Smooth logo transition
def logo_animation():
    import streamlit.components.v1 as components
    st.set_page_config(page_title="Incrolink Platform", page_icon="🟢", layout="wide")
    # This uses CSS for fade-in animation
    st.markdown("""
        <style>
        .logo-wrap { 
            display: flex; justify-content: center; margin-top: 50px; 
        }
        .logo-img {
            opacity: 0;
            animation: fadeIn 2s ease-in forwards;
        }
        @keyframes fadeIn {
            to { opacity: 1; }
        }
        </style>
        <div class='logo-wrap'>
            <img src='logoincrolink1.png' class='logo-img' width='220' />
        </div>
        """, unsafe_allow_html=True)
    time.sleep(2)
    st.markdown("---")

# 2. Single contact search (professionals1.xlsx as source)
def show_contact_search():
    st.title("Incrolink Contact Lookup")

    uploaded = st.file_uploader("Upload professionals1.xlsx for contact info", type=["xlsx"])
    if uploaded:
        df = pd.read_excel(uploaded)
        st.success(f"Loaded {len(df)} contacts.")
        name = st.text_input("Enter full name to search:", key="search_name")
        if name:
            match = df[df.apply(lambda row: name.lower() in str(row).lower(), axis=1)]
            if not match.empty:
                st.subheader("Contact Information")
                st.write(match)
            else:
                st.warning("No contact found matching that name.")
    else:
        st.info("Please upload professionals1.xlsx.")

def main():
    logo_animation()
    show_contact_search()

if __name__ == "__main__":
    main()
