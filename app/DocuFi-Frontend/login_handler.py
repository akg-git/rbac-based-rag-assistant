## ------------ ##
### LOGIN PAGE ###
## ------------ ##

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import ConnectionError, Timeout, RequestException
import streamlit as st
from bg_images import set_bg_from_local
from roles import fetch_roles

API_URL = "http://localhost:8000"

def login_page():

    #background image
    # set_bg_from_local("static/images/bgimage.jpg")
    def load_css():
        with open("assets/style.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    load_css()

    if st.session_state.page == "login":
        st.title("Welcome to FinSolve Data Assistant! 🤖")
        st.markdown("", unsafe_allow_html=True)

        # Display persistent error message if it exists
        if "login_error" in st.session_state and st.session_state.login_error:
            st.error(st.session_state.login_error)

        username = st.text_input("Username", key="user_name")
        password = st.text_input("Password", key="pass_word", type="password")

        if st.button("login", key="login_btn"):
            # Clear previous error before attempting new login
            st.session_state.login_error = None

            try:
                res = requests.get(f"{API_URL}/login", auth=HTTPBasicAuth(username, password))

                if res.status_code == 200:
                    data = res.json()
                    st.session_state.auth = (username, password)
                    st.session_state.username = username
                    st.session_state.password = password
                    st.session_state.role = data["role"]
                
                    # fetch roles once logged in successfully
                    st.session_state.roles = fetch_roles(API_URL, st.session_state.auth)

                    st.session_state.page = "main"
                    

                    return {
                        "success": True,
                        "username": username,
                        "password": password,
                        "role": data.get("role"),
                        "page": "main"
                    }
                
                elif res.status_code == 401:
                    # Unauthorized - Invalid credentials
                    st.session_state.login_error = "❌ Invalid Username/Password!! Try with correct credentials."
                    st.rerun()
                
                else:
                    # Other HTTP errors
                    try:
                        error_detail = res.json().get("detail", "Login failed")
                        st.session_state.login_error = f"❌ Login failed: {error_detail}"
                    except:
                        st.session_state.login_error = f"❌ Login failed with status code {res.status_code}"
                    
                    st.rerun()
        
            except (ConnectionError, Timeout):
                st.session_state.login_error = "❌ Cannot connect to server. Please ensure the backend server is running on http://localhost:8000"
                st.rerun()

            except RequestException as e:
                st.session_state.login_error = f"❌ Network error: {str(e)}"
                st.rerun()

            except Exception as e:
                st.session_state.login_error = f"❌ An unexpected error occurred: {str(e)}"
                st.rerun()