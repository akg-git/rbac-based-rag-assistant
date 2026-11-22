import streamlit as st
import requests
from requests.auth import HTTPBasicAuth

def fetch_roles(API_URL: str, auth) -> list[str]:
    """Load authorized roles safely into list."""
    if not auth:
        return []
    try:
        role_res = requests.get(
            f"{API_URL}/roles", 
            auth=HTTPBasicAuth(*auth),
            timeout=8
        )
        if role_res.status_code == 200:
            return role_res.json().get("roles", [])
        return []
    except Exception as e:
        st.error(f"Error fetching roles: {e}")
        return []