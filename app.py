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

def format_directors_with_original_order(cell_value, get_nzbn_for_company, get_directors_for_nzbn):
    parts = [p.strip() for p in cell_value.split(',')]
    result_parts = []
    limited_companies = {p for p in parts if re.search(r'Limited', p, re.IGNORECASE)}

    for part in parts:
        if part in limited_companies:
            nzbn, _ = get_nzbn_for_company(part)
            directors = get_directors_for_nzbn(nzbn) if nzbn else "Not found"
            result_parts.append(f"{part} - Director: {directors}")
        else:
            result_parts.append(part)
    return ", ".join(result_parts)




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

uploaded_file = st.file_uploader("Upload Excel file with a 'Owners Name(s)' column", type=['xlsx', 'xls'])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    st.write("Uploaded data preview:", df.head())

    if 'Owners Name(s)' not in df.columns:
        st.error("No 'Owners Name(s)' column found in the uploaded file.")
    else:
        if st.button("Process Companies"):
            results = []
            for idx, row in df.iterrows():
                raw_name = str(row['Owners Name(s)']).strip()
                unit_value = row.get('Unit', '')
                result_string = format_directors_with_original_order(raw_name, get_nzbn_for_company,
                                                                     get_directors_for_nzbn)
                results.append({
                    "Unit": unit_value,
                    "Original": raw_name,
                    "Directors": result_string})

            results_df = pd.DataFrame(results)
            results_df = results_df[['Unit', 'Original', 'Directors']]

            st.write("Results:", results_df)

            csv = results_df.to_csv(index=False)
            st.download_button(
                label="Download Results as CSV",
                data=csv,
                file_name='company_directors_results.csv',
                mime='text/csv'
            )

st.caption("Powered by NZBN API")
