import streamlit as st
import requests
from requests.auth import HTTPBasicAuth

# Load roles into session state if not present
def fetch_roles(API_URL, auth):
    try:
        role_res = requests.get(
            f"{API_URL}/roles", 
            auth=HTTPBasicAuth(*auth)
        )
        if role_res.status_code == 200:
            return role_res.json().get("roles", [])
    except Exception as e:
        st.error(f"Error fetching roles: {e}")
        return []