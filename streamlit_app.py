import os
import requests
import streamlit as st

API_URL = os.getenv("NUTRIMIND_API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

st.set_page_config(page_title="NutriMind", page_icon="🥗", layout="centered")

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stChatMessage {
    background: transparent !important;
}

[data-testid="stChatMessageContent"] p {
    font-size: 0.95rem;
    line-height: 1.6;
}

[data-testid="stChatMessage"] {
    padding-bottom: 0.25rem;
}

[data-testid="stChatMessage"][aria-label="user"] [data-testid="stChatMessageContent"] {
    background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
    color: #1b5e20;
    padding: 0.75rem 1rem;
    border-radius: 18px 18px 4px 18px;
    max-width: 80%;
    margin-left: auto;
    border: 1px solid rgba(76, 175, 80, 0.15);
}

[data-testid="stChatMessage"][aria-label="assistant"] [data-testid="stChatMessageContent"] {
    background: #ffffff;
    color: #1a1a2e;
    padding: 0.75rem 1rem;
    border-radius: 18px 18px 18px 4px;
    max-width: 85%;
    border: 1px solid rgba(0,0,0,0.06);
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

h1 {
    font-weight: 800 !important;
    letter-spacing: -0.5px;
}

.suggestion-btn button {
    border-radius: 20px !important;
    border: 1px solid #4caf50 !important;
    color: #4caf50 !important;
    background: white !important;
    font-size: 0.85rem !important;
    padding: 0.3rem 0.8rem !important;
    transition: all 0.2s ease;
}

.suggestion-btn button:hover {
    background: #4caf50 !important;
    color: white !important;
    border-color: #4caf50 !important;
}

[data-testid="stSidebar"] {
    background: #f8f9fa;
    border-right: 1px solid #e9ecef;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #6c757d;
    font-weight: 600;
}

.stChatInputContainer {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 16px;
    padding: 0.25rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

[data-testid="stChatInputTextArea"] {
    border: none !important;
    font-size: 0.95rem;
}

[data-testid="stStatusWidget"] {
    display: none;
}

footer { display: none; }
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

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

header_col1, header_col2 = st.columns([0.12, 0.88])
with header_col1:
    st.image("nutrimind.png", width=52)
with header_col2:
    st.markdown(
        "<h1 style='margin: 0; padding: 0; font-size: 1.8rem;'>NutriMind</h1>"
        "<p style='margin: -0.25rem 0 0 0; color: #6c757d; font-size: 0.9rem;'>"
        "Multi-agent AI nutrition assistant — stateful memory, longitudinal analysis, and human-in-the-loop medical flagging</p>",
        unsafe_allow_html=True,
    )

st.divider()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "USER_#01"
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    avatar = "🥗" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

if not st.session_state.messages:
    st.markdown(
        "<p style='color: #6c757d; font-size: 0.85rem; margin-bottom: 0.5rem;'>Try asking:</p>",
        unsafe_allow_html=True,
    )
    cols = st.columns(3)
    for i, suggestion in enumerate(SUGGESTIONS):
        with cols[i % 3]:
            st.markdown(f"<div class='suggestion-btn'>", unsafe_allow_html=True)
            if st.button(suggestion, key=f"sug_{i}", use_container_width=True):
                prompt = suggestion

if prompt := st.chat_input("Ask about nutrition, log a meal, or get a meal plan..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🥗"):
        with st.spinner("Thinking..."):
            try:
                headers = {"X-API-Key": API_KEY} if API_KEY else {}
                resp = requests.post(
                    f"{API_URL}/chat",
                    json={
                        "message": prompt,
                        "thread_id": st.session_state.thread_id,
                    },
                    headers=headers,
                    timeout=60,
                )
                resp.raise_for_status()
                reply = resp.json()["response"]
            except requests.exceptions.ConnectionError:
                reply = "Could not connect to the API server. Make sure the backend is running (`uv run uvicorn agent.app:api --host 0.0.0.0 --port 8000`)."
            except Exception as e:
                reply = f"Error: {e}"

        st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})

with st.sidebar:
    st.image("nutrimind.png", width=40)
    st.markdown("### NutriMind")

    status_emoji = "🟢" if requests.get(f"{API_URL}/health", timeout=5).ok else "🔴"
    st.markdown(f"**API Status** {status_emoji}")
    st.markdown(f"**Thread ID** `{st.session_state.thread_id}`")
    st.markdown(f"**Messages** `{len(st.session_state.messages)}`")

    st.divider()

    st.markdown("### Features")
    st.markdown(
        """
- 🧠 **Memory Agent** — Profile & meal history
- 📚 **Nutrition RAG** — Evidence-based Q&A
- 📋 **Planning Agent** — Adaptive meal plans
- 🥘 **Intake Agent** — Meal logging & macros
- 📊 **Insight Agent** — 14-day pattern analysis
        """
    )

    st.divider()

    st.markdown("### About")
    st.markdown(
        "Built with LangGraph, FastAPI, PostgreSQL, and AWS Bedrock. "
        "Routes queries through a supervisor to specialist agents — "
        "each with dedicated tools for RAG retrieval, USDA lookups, "
        "goal drift detection, and LLM-as-judge evaluation."
    )

    if st.button("🔄 Reset conversation", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.rerun()
