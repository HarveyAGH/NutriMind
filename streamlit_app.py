import os
import requests
import streamlit as st

API_URL = os.getenv("NUTRIMIND_API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

st.set_page_config(page_title="NutriMind", page_icon="🥗", layout="centered")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }

[data-testid="stAppViewContainer"] { background: #fafafa; }
[data-testid="stHeader"] { background: transparent; }

/* Chat messages */
[data-testid="stChatMessage"] { padding: 0.15rem 0; }

[data-testid="stChatMessageContent"] {
    padding: 0.7rem 1rem !important;
    font-size: 0.95rem;
    line-height: 1.6;
}

/* User bubble */
[data-testid="stChatMessage"][aria-label="user"] [data-testid="stChatMessageContent"] {
    background: #e3f2fd !important;
    color: #0d47a1;
    border-radius: 20px 20px 4px 20px;
}

/* Assistant bubble */
[data-testid="stChatMessage"][aria-label="assistant"] [data-testid="stChatMessageContent"] {
    background: white !important;
    color: #1a1a2e;
    border-radius: 20px 20px 20px 4px;
    border: 1px solid #f0f0f0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}

/* Fix inline code in messages */
[data-testid="stChatMessageContent"] code {
    background: #f1f3f5;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-size: 0.85rem;
}

/* Chat input container */
.stChatInputContainer {
    background: white !important;
    border: 1px solid #e0e0e0 !important;
    border-radius: 14px !important;
    padding: 0.15rem 0.15rem 0.15rem 1rem !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
}

[data-testid="stChatInputTextArea"] { font-size: 0.95rem !important; }

/* Hide hamburger, footer, status */
header[data-testid="stHeader"] > div:first-child { display: none; }
footer { display: none !important; }
#MainMenu { visibility: hidden; }
.stAppDeployButton { display: none; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: white;
    border-right: 1px solid #f0f0f0;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: #adb5bd;
    font-weight: 600;
    margin-bottom: 0.5rem;
}

/* Metric cards in sidebar */
.metric-card {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 0.6rem 0.8rem;
    margin-bottom: 0.4rem;
}
.metric-label { font-size: 0.75rem; color: #868e96; margin-bottom: 0.15rem; }
.metric-value { font-size: 1rem; font-weight: 600; color: #212529; }

/* Feature items */
.feature-item {
    padding: 0.35rem 0;
    font-size: 0.9rem;
    color: #495057;
}

/* Empty state */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem 1rem;
    text-align: center;
}
.empty-state-icon { font-size: 3rem; margin-bottom: 1rem; }
.empty-state-title { font-size: 1.2rem; font-weight: 600; color: #212529; margin-bottom: 0.5rem; }
.empty-state-text { font-size: 0.9rem; color: #868e96; max-width: 400px; line-height: 1.6; }

/* Status badge */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.8rem;
    padding: 0.25rem 0.6rem;
    border-radius: 20px;
    font-weight: 500;
}
.status-badge.online { background: #d3f9d8; color: #2b8a3e; }
.status-badge.offline { background: #ffe3e3; color: #c92a2a; }

/* Suggestion pills */
.suggestion-container {
    margin: 0.5rem 0 1rem 0;
}
.suggestion-pill {
    display: inline-block;
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 20px;
    padding: 0.35rem 1rem;
    font-size: 0.85rem;
    color: #495057;
    cursor: pointer;
    margin: 0.25rem 0.25rem;
    transition: all 0.15s ease;
    user-select: none;
}
.suggestion-pill:hover {
    background: #e3f2fd;
    border-color: #90caf9;
    color: #1565c0;
}
</style>
"""

SUGGESTIONS = [
    "How many calories in 100g chicken breast?",
    "Log 2 scrambled eggs for breakfast",
    "Create a meal plan for muscle gain",
    "What are my macros so far today?",
    "Analyze my nutrition over the past 2 weeks",
    "Set up my profile for weight loss",
]

st.markdown(CSS, unsafe_allow_html=True)

header = st.empty()
with header.container():
    hcol1, hcol2 = st.columns([0.07, 0.93])
    with hcol1:
        st.image("nutrimind.png", width=40)
    with hcol2:
        st.markdown(
            "<p style='margin:0;font-size:1.3rem;font-weight:700;color:#212529;'>NutriMind</p>"
            "<p style='margin:-0.2rem 0 0 0;font-size:0.82rem;color:#868e96;'>"
            "Multi-agent nutrition assistant</p>",
            unsafe_allow_html=True,
        )

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "USER_#01"
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if not st.session_state.messages:
    st.markdown(
        "<div class='empty-state'>"
        "<div class='empty-state-icon'>🥗</div>"
        "<div class='empty-state-title'>Ask me anything about nutrition</div>"
        "<div class='empty-state-text'>"
        "Track meals, check your daily macros, get evidence-based nutrition advice, "
        "or generate personalized meal plans."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='suggestion-container'><p style='font-size:0.85rem;color:#868e96;margin-bottom:0.3rem;'>Try asking:</p>",
        unsafe_allow_html=True,
    )
    pills_cols = st.columns(3)
    for i, s in enumerate(SUGGESTIONS):
        with pills_cols[i % 3]:
            st.markdown(
                f"<div class='suggestion-pill'>{s}</div>", unsafe_allow_html=True
            )
    st.markdown("</div>", unsafe_allow_html=True)

if prompt := st.chat_input("Ask about nutrition, log a meal, or get a meal plan..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("Thinking...")
        try:
            headers = {"X-API-Key": API_KEY} if API_KEY else {}
            resp = requests.post(
                f"{API_URL}/chat",
                json={
                    "message": prompt,
                    "thread_id": st.session_state.thread_id,
                },
                headers=headers,
                timeout=90,
            )
            resp.raise_for_status()
            reply = resp.json()["response"]
        except requests.exceptions.ConnectionError:
            reply = (
                "I can't reach the backend server. Make sure it's running:\n\n"
                "```bash\nuv run uvicorn agent.app:api --host 0.0.0.0 --port 8000\n```"
            )
        except Exception as e:
            reply = f"Sorry, something went wrong: {e}"

        placeholder.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})

with st.sidebar:
    st.image("nutrimind.png", width=32)
    st.markdown(
        "<p style='font-size:1.1rem;font-weight:600;margin:0.3rem 0 0.8rem 0;'>NutriMind</p>",
        unsafe_allow_html=True,
    )

    try:
        healthy = requests.get(f"{API_URL}/health", timeout=3).ok
    except Exception:
        healthy = False
    badge = "🟢 Online" if healthy else "🔴 Offline"
    st.markdown(
        f"<div style='margin-bottom:1rem'><span class='status-badge {'online' if healthy else 'offline'}'>{badge}</span></div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='metric-card'>"
        f"<div class='metric-label'>Thread</div>"
        f"<div class='metric-value' style='font-size:0.85rem;font-family:monospace;'>{st.session_state.thread_id}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='metric-card'>"
        f"<div class='metric-label'>Messages</div>"
        f"<div class='metric-value'>{len(st.session_state.messages)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown("### Agents")
    agents = [
        ("🧠", "Memory", "Profile & history"),
        ("📚", "Nutrition RAG", "Evidence-based Q&A"),
        ("📋", "Planning", "Meal plans & drift detection"),
        ("🥘", "Intake", "Meal logging & macros"),
        ("📊", "Insight", "14-day patterns & flags"),
    ]
    for emoji, name, desc in agents:
        st.markdown(
            f"<div class='feature-item'>{emoji} <strong>{name}</strong> — {desc}</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    st.markdown("### About")
    st.markdown(
        "<p style='font-size:0.82rem;color:#868e96;line-height:1.6;'>"
        "Built with LangGraph, FastAPI, PostgreSQL, and AWS Bedrock. "
        "Routes queries through a supervisor to five specialist agents — "
        "each with dedicated tools for RAG retrieval, USDA lookups, "
        "goal drift detection, and LLM-as-judge evaluation.</p>",
        unsafe_allow_html=True,
    )

    if st.button("New conversation", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.rerun()
