import streamlit as st
import pandas as pd
import requests
import os
import re
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()
API_KEY = os.getenv('API_KEY')
NZBN_SEARCH_URL = 'https://api.business.govt.nz/gateway/nzbn/v5/entities'
NZBN_ENTITY_URL = 'https://api.business.govt.nz/gateway/nzbn/v5/entities/{}'

def extract_company_name(cell_value):
    if not isinstance(cell_value, str):
        return ""
    # Split by comma, check each part for ending with "Limited"
    for part in reversed(cell_value.split(',')):
        part = part.strip()
        if re.search(r'Limited$', part, re.IGNORECASE):
            return part
    return cell_value.strip()



def get_nzbn_for_company(company_name):
    headers = {
        'Ocp-Apim-Subscription-Key': API_KEY,
        'Accept': 'application/json'
    }
    params = {
        'search-term': company_name,
        'page-size': 1
    }
    try:
        resp = requests.get(NZBN_SEARCH_URL, headers=headers, params=params, timeout=5)
        if resp.ok:
            items = resp.json().get('items', [])
            if items:
                return items[0].get('nzbn', ''), items[0].get('entityName', '')
    except Exception as e:
        st.error(f"Error searching NZBN for {company_name}: {e}")
    return '', ''

def get_directors_for_nzbn(nzbn):
    headers = {
        'Ocp-Apim-Subscription-Key': API_KEY,
        'Accept': 'application/json'
    }
    try:
        resp = requests.get(NZBN_ENTITY_URL.format(nzbn), headers=headers, timeout=10)
        if resp.ok:
            data = resp.json()
            directors = []
            for role in data.get('roles', []):
                if role.get('roleType') == 'Director' and role.get('roleStatus') == 'ACTIVE':
                    person = role.get('rolePerson', {})
                    name_parts = [person.get('firstName', ''), person.get('lastName', '')]
                    full_name = ' '.join(filter(None, name_parts))
                    if full_name.strip():
                        directors.append(full_name.title())
            return ", ".join(directors)
    except Exception as e:
        st.error(f"Error fetching directors for NZBN {nzbn}: {e}")
    return ''

st.title("Batch NZ Company Directors Lookup")

uploaded_file = st.file_uploader("Upload Excel file with a 'Name on the title' column", type=['xlsx', 'xls'])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    st.write("Uploaded data preview:", df.head())

    if 'Name on the title' not in df.columns:
        st.error("No 'Name on the title' column found in the uploaded file.")
    else:
        if st.button("Process Companies"):
            results = []
            for idx, row in df.iterrows():
                raw_name = str(row['Name on the title']).strip()
                company_name = extract_company_name(raw_name)
                if not company_name:
                    results.append({
                        "Original": raw_name,
                        "Extracted Company Name": "",
                        "NZBN": "",
                        "Matched Name": "",
                        "Directors": ""
                    })
                    continue

                nzbn, matched_name = get_nzbn_for_company(company_name)
                directors = get_directors_for_nzbn(nzbn) if nzbn else ""
                results.append({
                    "Original": raw_name,
                    "Extracted Company Name": company_name,
                    "NZBN": nzbn,
                    "Matched Name": matched_name,
                    "Directors": directors
                })
                st.write(f"Processed: {company_name} → {matched_name or 'Not found'}")

            results_df = pd.DataFrame(results)
            st.write("Results:", results_df)

            csv = results_df.to_csv(index=False)
            st.download_button(
                label="Download Results as CSV",
                data=csv,
                file_name='company_directors_results.csv',
                mime='text/csv'
            )

st.caption("Powered by NZBN API")
