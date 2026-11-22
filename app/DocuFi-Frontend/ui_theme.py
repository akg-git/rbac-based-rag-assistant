import streamlit as st

def apply_custom_theme():
    """
    Applies custom enterprise CSS styling within Streamlit application boundaries.
    Enhances typography, cards, chat bubbles, sidebar, and status badges.
    """
    custom_css = """
    <style>
    /* Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Main container styling */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        max-width: 1200px !important;
    }

    /* Modern Card Container */
    .stCard {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        backdrop-filter: blur(10px);
    }

    /* Role Pill Badges */
    .role-badge {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .role-c-level {
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
        color: #ffffff !important;
        box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
    }
    .role-finance {
        background: linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%);
        color: #ffffff !important;
    }
    .role-hr {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: #ffffff !important;
    }
    .role-sales {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        color: #ffffff !important;
    }
    .role-general {
        background: #334155;
        color: #e2e8f0 !important;
    }

    /* Mode Pill Badges */
    .mode-chip {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 6px;
        margin-bottom: 6px;
    }
    .mode-sql {
        background-color: rgba(59, 130, 246, 0.15);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }
    .mode-rag {
        background-color: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .mode-fallback {
        background-color: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }

    /* Context memory tag */
    .context-tag {
        font-size: 0.7rem;
        color: #94a3b8;
        background: rgba(148, 163, 184, 0.1);
        border: 1px dashed rgba(148, 163, 184, 0.25);
        border-radius: 4px;
        padding: 2px 6px;
        margin-left: 6px;
    }

    /* Timestamp tag */
    .chat-timestamp {
        font-size: 0.68rem;
        color: #64748b;
        margin-top: 4px;
        text-align: right;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }
    [data-testid="stSidebar"] .stButton button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
    }

    /* Chat input styling */
    [data-testid="stChatInput"] {
        border-radius: 12px;
    }

    /* Buttons styling */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }

    /* Hero welcome banner */
    .hero-banner {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(14, 165, 233, 0.05) 100%);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


def get_role_badge_html(role: str) -> str:
    """Returns styled HTML badge for user role."""
    r_lower = role.lower() if role else "general"
    css_class = "role-general"
    if "c-level" in r_lower:
        css_class = "role-c-level"
    elif "fin" in r_lower:
        css_class = "role-finance"
    elif "hr" in r_lower:
        css_class = "role-hr"
    elif "sales" in r_lower:
        css_class = "role-sales"
    return f'<span class="role-badge {css_class}">🛡️ {role}</span>'


def get_mode_chip_html(mode: str) -> str:
    """Returns styled HTML chip for query execution mode."""
    if not mode:
        return ""
    m_lower = mode.lower()
    if "fallback" in m_lower:
        return f'<span class="mode-chip mode-fallback">⚡ {mode}</span>'
    elif "sql" in m_lower:
        return f'<span class="mode-chip mode-sql">🗄️ {mode}</span>'
    elif "rag" in m_lower:
        return f'<span class="mode-chip mode-rag">📄 {mode}</span>'
    return f'<span class="mode-chip mode-sql">{mode}</span>'
