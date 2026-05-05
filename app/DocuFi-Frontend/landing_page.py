
import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
from bg_images import set_bg_from_local
from login_handler import login_page


API_URL = "http://localhost:8000"

#background image
set_bg_from_local("static/images/bgimg.jpg")

st.set_page_config(page_title="FinSolve Data Assistant", page_icon="🤖",layout="wide")

# -------------------------
# SESSION INIT
# -------------------------
if "auth" not in st.session_state:
    st.session_state.auth = None
if "role" not in st.session_state:
    st.session_state.role = None
if "page" not in st.session_state:
    st.session_state.page = "login"

# Fetch available roles from backend
def fetch_roles():
    try:
        res = requests.get(f"{API_URL}/roles", auth=HTTPBasicAuth(st.session_state.auth))
        if res.status_code == 200:
            return res.json().get("roles", [])
    except Exception as e:
        st.error(f"Error fetching roles: {e}")
    return []

# Two-column layout
left_col, right_col = st.columns([7,1])

# calling login page function to render login page if user is not authenticated
login_page(fetch_roles)

if st.session_state.page == "main":
    st.title("Welcome to FinSolve Data Assistant! 🤖")
    st.write("Your personal assistant for data insights and analysis. Please log in to access your personalized dashboard and start asking questions about your data.")

    username = st.session_state.username
    role = st.session_state.role

    with right_col:
        # st.subheader(f"Welcome, {username}! 👋")
        # st.write(f"Your role: **{role}**")
        st.markdown(f"**👤 User:** `{username}`  \n**🛡️ Role:** `{role}`")
        # -- Logout button --
        if st.button(" 🚪 Logout", key="logout_button"):
            st.session_state.auth = None
            st.session_state.role = None
            st.session_state.page = "login"
            st.rerun()
    
    # -- Main content area --
    # Dynamic rendering based on role
    with left_col:

        if role == "C-Level":
            st.write("You have global access")
            chat_tab, upload_tab, admin_tab = st.tabs(["💬 Chat", "🧾 Upload (C-Level)", "👤 Admin (C-Level)"])
        
        elif role == "General":
            st.write(f"You have access to documents and features related to the `{role}` role.")
            (chat_tab,) = st.tabs(["💬 Chat"])

        else:
            st.write(f"You have access to documents and features related to the `{role}` role.")
            st.markdown("You also have access to **General documents** (e.g., company policies, holidays, announcements)")
            (chat_tab,) = st.tabs(["💬 Chat"])

    # fetch current user role
    role = st.session_state.role

    if role.lower() == "c-level":

        ## Admin Tab for C-Level ##        [INCOMPLETE ADMIN TAB]
        with admin_tab:
            st.subheader("➕ Add User")
            username = st.text_input("Username", key="new_user_username")
            password = st.text_input("Password", key="new_user_password", type="password")
            role = st.selectbox("Assign Role", role)

    ## Chat Tab Funcationality ##
    with chat_tab:
        st.subheader("Ask questions about your data! 💬")
        question = st.text_input("Type your question here...", key="question_input")

        if st.button("Submit", key="submit_question"):
            if question.strip():
                res = requests.post(
                    f"{API_URL}/chat",
                    json={"question": question, "role": role},
                    auth=HTTPBasicAuth(st.session_state.auth)
                )

                st.markdown("**Answer:**")
                if res.status_code == 200:
                    st.success("✅ Answer:")

                    result = res.json()
                    st.write(result["answer"])
                    
                    if result.get("fallback"):
                        st.warning("The system had to use the RAG fallback to answer your question, which may indicate that the SQL query was blocked or failed. The answer may be less precise than a direct SQL response.")
                    
                    if result.get("sql"):
                        with st.expander("View Generated SQL Query"):
                            st.code(result["sql"], language="sql")
                else:
                    st.error(f"Error: {res.status_code}: {res.text}")

            else:
                st.warning("Please enter a question before submitting.")
    
        ## Upload Tab for C-Level ##
