import json
from datetime import datetime
import streamlit as st
import requests
from requests.auth import HTTPBasicAuth

# -----------------------
# STREAMLIT PAGE CONFIG
# -----------------------
st.set_page_config(
    page_title="RAG Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

from ui_theme import apply_custom_theme, get_role_badge_html, get_mode_chip_html
from login_handler import login_page
from roles import fetch_roles
from ui_utility_page import verify_user_with_role

API_URL = "http://localhost:8000"

# Apply custom enterprise CSS styling
apply_custom_theme()

# ----------------------------------------------------
# SESSION STATE INITIALIZATION
# ----------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "auth" not in st.session_state:
    st.session_state.auth = None
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None
if "roles" not in st.session_state:
    st.session_state.roles = []
if "page" not in st.session_state:
    st.session_state.page = "login"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "delete_confirm" not in st.session_state:
    st.session_state.delete_confirm = False
if "delete_user_data" not in st.session_state:
    st.session_state.delete_user_data = {"username": "", "role": ""}
if "login_error" not in st.session_state:
    st.session_state.login_error = None
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "add_user_v" not in st.session_state:
    st.session_state.add_user_v = 0
if "del_user_v" not in st.session_state:
    st.session_state.del_user_v = 0
if "role_v" not in st.session_state:
    st.session_state.role_v = 0
if "upload_v" not in st.session_state:
    st.session_state.upload_v = 0
if "admin_status_msg" not in st.session_state:
    st.session_state.admin_status_msg = None
if "upload_status_msg" not in st.session_state:
    st.session_state.upload_status_msg = None

# ----------------------------------------------------
# AUTHENTICATION ROUTING
# ----------------------------------------------------
if not st.session_state.logged_in:

    # # calling login page function to render login page if user is not authenticated
    auth_response = login_page()
    if auth_response and auth_response.get("success"):
        st.session_state.logged_in = True
        st.session_state.username = auth_response["username"]
        st.session_state.auth = (auth_response["username"], auth_response["password"])
        st.session_state.role = auth_response["role"]
        st.session_state.page = "main"
        st.session_state.roles = fetch_roles(API_URL, st.session_state.auth)

        st.success("Login successful")
        st.rerun()

# ----------------------------------------------------
# MAIN APPLICATION VIEW
# ----------------------------------------------------
if st.session_state.logged_in and st.session_state.page == "main":
    username = st.session_state.get("username", "User")
    role = st.session_state.get("role", "General")
    role_lower = role.lower() if role else "general"

    # Ensure roles are loaded
    if not st.session_state.roles:
        st.session_state.roles = fetch_roles(API_URL, st.session_state.auth)

    # ------------------------------------------------
    # SIDEBAR: Profile, Controls, & Quick Prompts
    # ------------------------------------------------
    with st.sidebar:
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 1rem;">
                <span style="font-size: 2rem;">🤖</span>
                <div>
                    <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700;">RAG Assistant</h3>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # User Profile Card
        with st.container(border=True):
            st.markdown(f"**👤 User:** `{username}`")
            st.markdown(f"**Access Level:** {get_role_badge_html(role)}", unsafe_allow_html=True)
            
            if role_lower == "c-level":
                st.caption("🌐 **Global Access:** All SQL tables, private executive documents, & administrative controls.")
            elif role_lower == "general":
                st.caption("📄 **General Access:** Company policies, handbook, announcements & public documents.")
            else:
                st.caption(f"📁 **Departmental Access:** `{role}` departmental data, documents, plus General policies.")

        st.divider()

        # Session & Chat Controls
        st.markdown("##### ⚙️ Conversation Controls")
        
        col_clear, col_export = st.columns(2)
        with col_clear:
            if st.button("🗑️ Clear Chat", use_container_width=True, help="Reset conversation history for this session"):
                st.session_state.messages = []
                st.session_state.pending_prompt = None
                st.rerun()

        with col_export:
            if st.session_state.messages:
                chat_json = json.dumps(st.session_state.messages, indent=2)
                st.download_button(
                    label="📥 Export",
                    data=chat_json,
                    file_name=f"finsolve_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True,
                    help="Download session conversation log as JSON"
                )
            else:
                st.button("📥 Export", disabled=True, use_container_width=True)

        # Quick Suggested Prompts based on Role (static)
        st.divider()
        st.markdown("##### 💡 Quick Questions")
        suggested_queries = []
        if role_lower == "c-level":
            suggested_queries = [
                "Show total revenue and profit summary",
                "List all departmental employees and their roles",
                "What is our executive corporate travel policy?",
                "Show top 5 highest expenses this year"
            ]
        elif "fin" in role_lower:
            suggested_queries = [
                "What was the total expenditure in Q3?",
                "Show recent budget allocation by department",
                "Summarize financial reimbursement rules"
            ]
        elif "hr" in role_lower:
            suggested_queries = [
                "What are the official paid leaves for this year?",
                "Show employee headcounts per department",
                "Summarize health insurance benefits"
            ]
        else:
            suggested_queries = [
                "What is the company remote work policy?",
                "What are the upcoming official holidays?",
                "How do I submit an IT support request?"
            ]

        for q in suggested_queries:
            if st.button(f"👉 {q}", key=f"quick_{hash(q)}", use_container_width=True):
                st.session_state.pending_prompt = q
                st.rerun()

        st.divider()
        # System Health Status & Logout
        st.markdown(
            '<div style="font-size: 0.78rem; color: #10b981; margin-bottom: 0.75rem;">● Server Connected (localhost:8000)</div>',
            unsafe_allow_html=True
        )

        if st.button("🚪 Sign Out", key="logout_btn", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.auth = None
            st.session_state.username = None
            st.session_state.role = None
            st.session_state.roles = []
            st.session_state.messages = []
            st.session_state.pending_prompt = None
            st.session_state.page = "login"

            st.success("Logged out successfully!")
            st.rerun()

    # ------------------------------------------------
    # MAIN WORKSPACE: Header & Tabs
    # ------------------------------------------------
    st.title("DocuFi - Natural Language to Enterprise Insights")
    st.markdown(
        f"Conversational analytics with **Context Memory** and **Role-Based Access Control ({role})**."
    )

    # Dynamic Tabs based on Role
    if role_lower == "c-level":
        chat_tab, upload_tab, admin_tab = st.tabs([
            "💬 Conversational Chatbot",
            "📤 Document Upload (C-Level)",
            "🛡️ RBAC Administration (C-Level)"
        ])
    else:
        chat_tab, = st.tabs(["💬 Conversational Chatbot"])
        upload_tab = None
        admin_tab = None

    # ====================================================
    # CHATBOT WINDOW (CONVERSATIONAL INTERFACE)
    # ====================================================
    with chat_tab:
        # Message Display Container
        chat_container = st.container()

        # Render empty state banner if no messages yet
        if not st.session_state.messages:
            with chat_container:
                st.markdown(
                    f"""
                    <div class="hero-banner">
                        <h4 style="margin-top: 0; color: #6366f1;">👋 Welcome, {username}!</h4>
                        <p style="margin-bottom: 0.5rem; font-size: 0.95rem; color: #cbd5e1;">
                            I am your intelligent assistant. I can query relational databases via SQL and retrieve information from company documentation via semantic search with full RBAC protection.
                        </p>
                        <div style="font-size: 0.85rem; color: #94a3b8;">
                            • <strong>Multi-turn memory active:</strong> You can ask follow-up questions referencing previous answers.<br>
                            • <strong>Type below</strong> or click one of the quick suggestions from the sidebar to start!
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # Render message history
        with chat_container:
            for msg in st.session_state.messages:
                role_type = msg.get("role", "user")
                avatar_icon = "👤" if role_type == "user" else "🤖"

                with st.chat_message(role_type, avatar=avatar_icon):
                    if role_type == "assistant":
                        # Display execution mode chip
                        mode = msg.get("mode")
                        if mode:
                            st.markdown(get_mode_chip_html(mode), unsafe_allow_html=True)

                        # Display context memory indicator if applicable
                        if msg.get("contextualized_question"):
                            st.caption(f"🧠 *Context Reformulation: \"{msg['contextualized_question']}\"*")

                        # Display answer
                        st.markdown(msg.get("content", ""))

                        # Fallback warning
                        if msg.get("fallback"):
                            st.info("ℹ️ SQL query was not possible for this question; answered via Document RAG.")

                        # SQL query expander
                        if msg.get("sql"):
                            with st.expander("🔍 View Generated SQL Query"):
                                st.code(msg["sql"], language="sql")

                        # Document sources expander
                        if msg.get("sources"):
                            with st.expander("📚 Referenced Document Sources"):
                                for src in msg["sources"]:
                                    st.markdown(f"- `{src}`")

                        # Timestamp
                        if msg.get("timestamp"):
                            st.markdown(f"<div class='chat-timestamp'>{msg['timestamp']}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(msg.get("content", ""))
                        if msg.get("timestamp"):
                            st.markdown(f"<div class='chat-timestamp'>{msg['timestamp']}</div>", unsafe_allow_html=True)

        # ----------------------
        # CHAT INPUT PROCESSING
        # ----------------------
        user_prompt = st.chat_input("Ask a question about policies, or company metrics...")
        
        # Check if a quick suggestion prompt was triggered from sidebar
        if st.session_state.pending_prompt:
            user_prompt = st.session_state.pending_prompt
            st.session_state.pending_prompt = None

        if user_prompt and user_prompt.strip():
            clean_prompt = user_prompt.strip()
            timestamp = datetime.now().strftime("%I:%M %p")

            # 1. Append user message to session state
            st.session_state.messages.append({
                "role": "user",
                "content": clean_prompt,
                "timestamp": timestamp
            })

            # Display user message immediately
            with st.chat_message("user", avatar="👤"):
                st.markdown(clean_prompt)
                st.markdown(f"<div class='chat-timestamp'>{timestamp}</div>", unsafe_allow_html=True)

            # 2. Build history payload for Context Memory (last 6 turns)
            history_payload = []
            for m in st.session_state.messages[:-1][-6:]:
                history_payload.append({
                    "role": m["role"],
                    "content": m["content"]
                })

            # 3. Call backend with loading spinner
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Analyzing request, checking RBAC boundaries, and retrieving insights..."):
                    try:
                        res = requests.post(
                            f"{API_URL}/chat",
                            json={
                                "question": clean_prompt,
                                "history": history_payload
                            },
                            auth=HTTPBasicAuth(*st.session_state.auth),
                            timeout=60
                        )

                        if res.status_code == 200:
                            result = res.json()
                            answer_text = result.get("answer", "No answer received.")
                            mode = result.get("mode", "RAG")
                            sql_text = result.get("sql")
                            fallback = result.get("fallback", False)
                            sources = result.get("sources", [])
                            contextualized = result.get("contextualized_question")

                            assistant_msg = {
                                "role": "assistant",
                                "content": answer_text,
                                "mode": mode,
                                "sql": sql_text,
                                "fallback": fallback,
                                "sources": sources,
                                "contextualized_question": contextualized,
                                "timestamp": datetime.now().strftime("%I:%M %p")
                            }
                            st.session_state.messages.append(assistant_msg)
                            st.rerun()

                        elif res.status_code == 403:
                            err_msg = "🚫 **Access Denied:** You are not authorized to view the requested data according to your assigned role."
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": err_msg,
                                "mode": "RBAC Denied",
                                "timestamp": datetime.now().strftime("%I:%M %p")
                            })
                            st.rerun()

                        else:
                            try:
                                detail = res.json().get("detail", res.text)
                            except Exception:
                                detail = res.text
                            err_msg = f"⚠️ **Backend Error ({res.status_code}):** {detail}"
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": err_msg,
                                "mode": "Error",
                                "timestamp": datetime.now().strftime("%I:%M %p")
                            })
                            st.rerun()

                    except requests.exceptions.Timeout:
                        st.error("⏳ Request timed out. The backend server took too long to respond.")
                    except requests.exceptions.ConnectionError:
                        st.error("❌ Connection failed. Ensure the FastAPI backend is running on http://localhost:8000")
                    except Exception as e:
                        st.error(f"❌ An unexpected error occurred: {str(e)}")

    # ====================================================
    # DOCUMENT UPLOAD TAB (FOR C-LEVEL ONLY)
    # ====================================================
    if upload_tab and role_lower == "c-level":
        with upload_tab:
            col_u_title, col_u_refresh = st.columns([5, 1.2])
            with col_u_title:
                st.subheader("📤 Secure Document Ingestion")
                st.caption("Upload documents to be indexed into ChromaDB vector store with RBAC tag enforcement.")
            with col_u_refresh:
                st.write("")
                if st.button("🔄 Refresh Form", key="btn_refresh_upload", use_container_width=True, help="Clear uploaded file and reload roles"):
                    st.session_state.upload_v += 1
                    st.session_state.roles = fetch_roles(API_URL, st.session_state.auth)
                    st.session_state.upload_status_msg = None
                    st.rerun()

            # Display persistent success/status message if set from previous run
            if st.session_state.upload_status_msg:
                status_type, status_text = st.session_state.upload_status_msg
                if status_type == "success":
                    st.success(status_text)
                st.session_state.upload_status_msg = None

            with st.container(border=True):
                avail_roles = st.session_state.roles or fetch_roles(API_URL, st.session_state.auth) or ["C-Level", "Finance", "HR", "Sales", "General"]
                
                col_u1, col_u2 = st.columns([1, 2])
                with col_u1:
                    target_role = st.selectbox(
                        "Target Role for Access Control",
                        avail_roles,
                        key=f"upload_role_select_{st.session_state.upload_v}",
                        help="Only users with this role (and C-Level) will be permitted to retrieve chunks from this document."
                    )
                with col_u2:
                    doc_file = st.file_uploader(
                        "Select Document (.csv, .md, .txt)",
                        type=["csv", "md", "txt"],
                        key=f"upload_file_widget_{st.session_state.upload_v}"
                    )

                if st.button("🚀 Ingest & Embed Document", key="btn_upload_doc"):
                    if not doc_file:
                        st.warning("⚠️ Please select a file before uploading.")
                    else:
                        with st.spinner(f"Ingesting '{doc_file.name}' for role '{target_role}'..."):
                            try:
                                res = requests.post(
                                    f"{API_URL}/upload-docs",
                                    files={"file": (doc_file.name, doc_file.getvalue())},
                                    data={"role": target_role},
                                    auth=HTTPBasicAuth(*st.session_state.auth),
                                    timeout=60
                                )

                                if res.ok:

                                    st.session_state.upload_v += 1
                                    st.session_state.upload_status_msg = (
                                        "success",
                                        f"✅ Successfully uploaded and indexed **{doc_file.name}** for role `{target_role}`!"
                                    )
                                    st.rerun()
                                else:

                                    err_text = res.json().get("detail", res.text) if res.text else "Upload failed"
                                    st.error(f"❌ Upload Error ({res.status_code}): {err_text}")
                            except Exception as e:
                                st.error(f"❌ Network or processing error: {str(e)}")

    # ====================================================
    # RBAC ADMINISTRATION TAB (FOR C-LEVEL ONLY)
    # ====================================================
    if admin_tab and role_lower == "c-level":
        with admin_tab:
            col_adm_title, col_adm_refresh = st.columns([5, 1.2])
            with col_adm_title:
                st.subheader("🛡️ Enterprise RBAC User & Role Administration")
                st.caption("Manage user access credentials, role mappings, and custom authorization groups.")
            with col_adm_refresh:
                st.write("")
                if st.button("🔄 Refresh Dashboard", key="btn_refresh_admin", use_container_width=True, help="Clear all input fields and re-sync roles with database"):
                    st.session_state.add_user_v += 1
                    st.session_state.del_user_v += 1
                    st.session_state.role_v += 1
                    st.session_state.delete_confirm = False
                    st.session_state.delete_user_data = {"username": "", "role": ""}
                    st.session_state.roles = fetch_roles(API_URL, st.session_state.auth)
                    st.session_state.admin_status_msg = None
                    st.rerun()

            # Display persistent success message if set from previous action
            if st.session_state.admin_status_msg:
                status_type, status_text = st.session_state.admin_status_msg
                if status_type == "success":
                    st.success(status_text)
                st.session_state.admin_status_msg = None

            avail_roles = st.session_state.roles or fetch_roles(API_URL, st.session_state.auth) or ["C-Level", "Finance", "HR", "Sales", "General"]

            # Two Column Admin Panel: Add User & Delete User
            col_add, col_del = st.columns(2)

            with col_add:
                with st.container(border=True):
                    st.markdown("##### ➕ Provision New User")
                    new_u = st.text_input("New Username", key=f"admin_add_username_{st.session_state.add_user_v}").strip()
                    new_p = st.text_input("Password", type="password", key=f"admin_add_password_{st.session_state.add_user_v}").strip()
                    new_r = st.selectbox("Assign Role", avail_roles, key=f"admin_add_role_{st.session_state.add_user_v}")

                    if st.button("Create User Account", key="btn_create_user", use_container_width=True):
                        if not new_u or not new_p:
                            st.warning("Please provide both username and password.")
                        else:
                            with st.spinner("Provisioning user details..."):
                                res = requests.post(
                                    f"{API_URL}/create-user",
                                    data={"username": new_u, "password": new_p, "role": new_r},
                                    auth=HTTPBasicAuth(*st.session_state.auth),
                                    timeout=10
                                )
                                if res.ok:

                                    st.session_state.add_user_v += 1
                                    st.session_state.admin_status_msg = (
                                        "success",
                                        f"✅ User `{new_u}` successfully created with role `{new_r}`!"
                                    )
                                    st.rerun()
                                else:
                                    err = res.json().get("detail", res.text) if res.text else "Creation failed"
                                    st.error(f"❌ User Creation Failed: {err}")

            with col_del:
                with st.container(border=True):
                    st.markdown("##### 🗑️ Revoke User Access")
                    del_r = st.selectbox("Select User's Role", avail_roles, key=f"admin_del_role_{st.session_state.del_user_v}")
                    del_u = st.text_input("Username to Delete", key=f"admin_del_username_{st.session_state.del_user_v}").strip()

                    if st.button("Check & Prepare Deletion", key="btn_del_check", use_container_width=True):
                        if del_u:
                            verification = verify_user_with_role(del_u, del_r, st.session_state.auth)
                            if verification["exists"]:
                                st.session_state.delete_user_data = {"username": del_u, "role": del_r}
                                st.session_state.delete_confirm = True
                            else:
                                st.error(verification["message"])
                        else:
                            st.warning("Please enter a username.")

            # Deletion Confirmation Dialog Box
            if st.session_state.delete_confirm:
                with st.container(border=True):
                    st.warning("⚠️ **Confirm Account Deletion**")
                    st.markdown(
                        f"Are you sure you want to permanently delete user **`{st.session_state.delete_user_data['username']}`** "
                        f"with role **`{st.session_state.delete_user_data['role']}`**? This action cannot be undone."
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("🚨 Yes, Permanently Delete", key="confirm_delete_btn", use_container_width=True):
                            deleted_user = st.session_state.delete_user_data["username"]
                            res = requests.post(
                                f"{API_URL}/delete-user",
                                data={
                                    "username": deleted_user,
                                    "role": st.session_state.delete_user_data["role"]
                                },
                                auth=HTTPBasicAuth(*st.session_state.auth),
                                timeout=10
                            )
                            if res.ok:

                                st.session_state.del_user_v += 1
                                st.session_state.delete_confirm = False
                                st.session_state.delete_user_data = {"username": "", "role": ""}
                                st.session_state.admin_status_msg = (
                                    "success",
                                    f"✅ User `{deleted_user}` deleted successfully!"
                                )
                                st.rerun()
                            else:
                                err = res.json().get("detail", res.text) if res.text else "Deletion failed"
                                st.error(f"❌ Deletion failed: {err}")
                    with c2:
                        if st.button("❌ Cancel", key="cancel_delete_btn", use_container_width=True):
                            st.session_state.delete_confirm = False
                            st.session_state.delete_user_data = {"username": "", "role": ""}
                            st.rerun()

            ## CREATE ROLE FUNCTIONALITY
            st.divider()
            with st.container(border=True):
                st.markdown("##### 👥 Create New Authorization Role")
                col_r1, col_r2 = st.columns([2, 1])
                with col_r1:
                    new_role_name = st.text_input(
                        "New Role Name",
                        placeholder="e.g., Compliance, Marketing, Operations",
                        key=f"admin_new_role_input_{st.session_state.role_v}"
                    ).strip()
                with col_r2:
                    st.write("")
                    st.write("")
                    if st.button("Add New Role", key="btn_add_role", use_container_width=True):
                        if not new_role_name:
                            st.warning("Please enter a role name.")
                        else:
                            res = requests.post(
                                f"{API_URL}/create-role",
                                data={"role_name": new_role_name},
                                auth=HTTPBasicAuth(*st.session_state.auth),
                                timeout=10
                            )
                            if res.ok:

                                st.session_state.role_v += 1
                                st.session_state.roles = fetch_roles(API_URL, st.session_state.auth)
                                st.session_state.admin_status_msg = (
                                    "success",
                                    f"✅ Role `{new_role_name}` created successfully!"
                                )
                                st.rerun()
                            else:
                                err = res.json().get("detail", res.text) if res.text else "Role creation failed"
                                st.error(f"❌ Role creation failed: {err}")
