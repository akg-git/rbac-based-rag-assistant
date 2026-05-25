
import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
from bg_images import set_bg_from_local
from login_handler import login_page
from roles import fetch_roles

API_URL = "http://localhost:8000"

#background image
set_bg_from_local("static/images/bgimg.jpg")

st.set_page_config(page_title="FinSolve Data Assistant", page_icon="🤖",layout="wide")

# -------------------------
# SESSION INIT
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "auth" not in st.session_state:
    st.session_state.auth = None
if "role" not in st.session_state:
    st.session_state.role = None
if "page" not in st.session_state:
    st.session_state.page = "login"

# st.session_state.auth = (username, password) if st.session_state.auth else None

if not st.session_state.logged_in:

    # # calling login page function to render login page if user is not authenticated
    auth_response = login_page()

    if auth_response:

        if auth_response["success"]:

            st.session_state["logged_in"] = True
            st.session_state["username"] = auth_response["username"]
            st.session_state["password"] = auth_response["password"]
            st.session_state["role"] = auth_response["role"]
            st.session_state["page"] = auth_response["page"]

            st.success("Login successful")
            st.rerun()

        else:
            st.rerun()

if st.session_state.page == "main" and st.session_state.logged_in:
    st.title("Welcome to FinSolve Data Assistant! 🤖")
    st.write("Your personal assistant for data insights and analysis. Please log in to access your personalized dashboard and start asking questions about your data.")

    # Two-column layout (for user info and tabs)
    left_col, right_col = st.columns([7,1])

    username = st.session_state.get("username")
    role = st.session_state.get("role")

    with right_col:
        # st.subheader(f"Welcome, {username}! 👋")
        # st.write(f"Your role: **{role}**")
        st.markdown(f"**👤 User:** `{username}`  \n**🛡️ Role:** `{role}`")
        # -- Logout button --
        if st.button(" 🚪 Logout", key="logout_button"):
            st.session_state.logged_in = False
            st.session_state.auth = None
            st.session_state.username = None
            st.session_state.role = None
            st.session_state.page = "login"
            st.success("Logged out successfully!")
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

        ## Admin Tab for C-Level ##
        with admin_tab:

            get_available_roles = fetch_roles(API_URL, st.session_state.auth)

            ## ADD USER FUNCTIONALITY
            st.subheader("➕ Add User")
            username = st.text_input("Username", key="new_user_username").strip()
            password = st.text_input("Password", key="new_user_password", type="password").strip()
            role = st.selectbox("Assign Role", get_available_roles, key="new_user_role")

            if st.button("Create User", key="create-usr-btn"):

                res = requests.post(
                    f"{API_URL}/create-user",
                    data = {
                        "username": username,
                        "password": password,
                        "role": role
                    },
                    auth = HTTPBasicAuth(*st.session_state.auth)
                )

                if res.ok:
                    st.success(f"User '{username}' created with role '{role}'. ")
                else:
                    st.error(f"Error while creating user: {res.status_code} - {res.text}")
                    st.error(res.json().get("detail", "User creation failed!!"))

            ## CREATE ROLE FUNCTIONALITY
            st.subheader("🧑‍💻 Create New Role")
            new_role = st.text_input("Role Name", key="new-role-name").strip()

            if st.button("Add Role", key="add-role-btn"):
                
                res = requests.post(
                    f"{API_URL}/create-role",
                    data={"role_name": new_role},
                    auth=HTTPBasicAuth(*st.session_state.auth)
                )

                if res.ok:
                    st.success(res.json()["message"])
                    st.session_state.roles = fetch_roles(API_URL, st.session_state.auth)
                    st.rerun() 
                    st.success(f"Role - '{new_role}' created successfully.")
                else:
                    st.error(f"Error while creating new role: {res.status_code} - {res.text}")
                    st.error(res.json().get("detail", "Role creation failed!!"))
            
            ## UPDATE ROLE FUNCTIONALITY

        ## Upload Tab for C-Level ##
        with upload_tab:
            st.subheader("📤 Upload Documents")

            get_role = requests.get(
                f"{API_URL}/roles",
                auth=HTTPBasicAuth(*st.session_state.auth)
            )

            roles = st.session_state.roles
            selected_role = st.selectbox("Select Role for Document Access", roles, key="upload-doc-role")
            doc_file = st.file_uploader("Choose a document to upload [.md or .csv]", type=["csv", "md"], key="doc-uploader")

            if st.button("Upload Document", key="upload-doc-btn"):
                res = requests.post(
                    f"{API_URL}/upload-docs",
                    files={"file": doc_file},
                    data={"role":selected_role},
                    auth=HTTPBasicAuth(*st.session_state.auth)
                )

                if res.ok:
                    st.success("✅ Document uploaded successfully!")
                else:
                    st.error(f"Error uploading document: {res.status_code} - {res.text}")
                    st.error(res.json().get("detail", "Document upload failed!!"))



    ## Chat Tab Funcationality ##
    with chat_tab:
        st.subheader("Ask questions about your data! 💬")
        question = st.text_input("Type your question here...", key="question_input")

        if st.button("Submit", key="submit_question"):
            if question.strip():
                res = requests.post(
                    f"{API_URL}/chat",
                    json={"question": question, "role": role},
                    auth=HTTPBasicAuth(*st.session_state.auth)
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
    
        
