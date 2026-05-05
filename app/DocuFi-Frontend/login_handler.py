## ------------ ##
### LOGIN PAGE ###
## ------------ ##

import requests
from requests.auth import HTTPBasicAuth
import streamlit as st
from bg_images import set_bg_from_local

API_URL = "http://localhost:8000"

def login_page(user_roles):

    #background image
    # set_bg_from_local("static/images/bgimage.jpg")
    def load_css():
        with open("assets/style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    load_css()

    if st.session_state.page == "login":
        st.title("Welcome to FinSolve Data Assistant! 🤖")
        st.markdown("", unsafe_allow_html=True)

        username = st.text_input("Username", key="username")
        password = st.text_input("Password", key="password", type="password")

        if st.button("login", key="login_btn"):

            res = requests.get(f"{API_URL}/login", auth=HTTPBasicAuth(username, password))

            if res.status_code == 200:
                data = res.json()
                st.session_state.auth = (username, password)
                st.session_state.username = username
                st.session_state.password = password
                st.session_state.role = data["role"]
            
                # fetch roles once logged in successfully
                st.session_state.roles = user_roles

                st.session_state.page = "main"
                st.rerun()
            else:
                try:
                    error_detail = res.json().get("detail", "Login failed")
                    st.error(f"Login failed: {error_detail}")
                except:
                    st.error("Server Error. Please check FastAPI logs")




