## ------------ ##
### LOGIN PAGE ###
## ------------ ##

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import ConnectionError, Timeout, RequestException
import streamlit as st
from roles import fetch_roles

API_URL = "http://localhost:8000"

def login_page():
    """
    Renders an enterprise-grade centered login screen for RAG Assistant.
    """
    # Centered container layout using columns
    _, col_center, _ = st.columns([1, 1.8, 1])

    with col_center:
        st.markdown(
            """
            <div style="text-align: center; padding: 2rem 1rem 1rem 1rem;">
                <div style="font-size: 3rem; margin-bottom: 0.5rem;">🤖</div>
                <h2 style="margin: 0; font-weight: 700; letter-spacing: -0.5px;">RAG Assistant</h2>
                <p style="color: #94a3b8; font-size: 0.95rem; margin-top: 0.4rem;">
                    Enterprise RBAC-Governed Intelligence & Document Analytics
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        with st.container(border=True):
            st.markdown("#### Sign In to Your Account")
            st.caption("Enter your credentials to access role-specific data & documents.")

            # Display persistent error message if it exists
            if "login_error" in st.session_state and st.session_state.login_error:
                st.error(st.session_state.login_error)

            username = st.text_input(
                "Username",
                placeholder="Enter your username",
                key="user_name"
            ).strip()

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="pass_word"
            ).strip()

            st.write("")
            login_clicked = st.button(" Sign In ", key="login_btn", use_container_width=True)

            if login_clicked:
                if not username or not password:
                    st.session_state.login_error = "⚠️ Please enter both username and password."
                    st.rerun()

                st.session_state.login_error = None

                try:
                    with st.spinner("Authenticating with enterprise server..."):
                        res = requests.get(
                            f"{API_URL}/login",
                            auth=HTTPBasicAuth(username, password),
                            timeout=10
                        )

                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.auth = (username, password)
                        st.session_state.username = username
                        st.session_state.password = password
                        st.session_state.role = data.get("role", "General")
                        
                        # Pre-fetch roles for C-Level admins
                        st.session_state.roles = fetch_roles(API_URL, st.session_state.auth)
                        st.session_state.page = "main"

                        return {
                            "success": True,
                            "username": username,
                            "password": password,
                            "role": data.get("role", "General"),
                            "page": "main"
                        }

                    elif res.status_code == 401:
                        st.session_state.login_error = "❌ Invalid Username or Password. Please check your credentials."
                        st.rerun()

                    else:
                        try:
                            error_detail = res.json().get("detail", "Login failed")
                            st.session_state.login_error = f"❌ Login failed: {error_detail}"
                        except Exception:
                            st.session_state.login_error = f"❌ Login failed with status code {res.status_code}"
                        st.rerun()

                except (ConnectionError, Timeout):
                    st.session_state.login_error = (
                        "❌ Cannot connect to backend server. "
                        "Please verify FastAPI is running at http://localhost:8000"
                    )
                    st.rerun()

                except RequestException as e:
                    st.session_state.login_error = f"❌ Network error: {str(e)}"
                    st.rerun()

                except Exception as e:
                    st.session_state.login_error = f"❌ An unexpected error occurred: {str(e)}"
                    st.rerun()

        # Security & RBAC informational footer
        st.markdown(
            """
            <div style="text-align: center; margin-top: 1.5rem; font-size: 0.78rem; color: #64748b;">
                🔒 Secured by Role-Based Access Control (RBAC) & End-to-End Audit Logging
            </div>
            """,
            unsafe_allow_html=True
        )

    return None