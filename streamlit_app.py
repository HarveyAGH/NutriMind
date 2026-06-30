import os
import requests
import streamlit as st

API_URL = os.getenv("NUTRIMIND_API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

st.set_page_config(page_title="NutriMind", page_icon="🥗", layout="centered")

st.markdown(
    """
<style>
[data-testid="stAppViewContainer"] { background: #0e1117; color: #e0e0e0; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: #1a1d23; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { color: #c0c0c0; }
h1 { color: #e0e0e0 !important; }
.stChatInputContainer { background: #1a1d23 !important; border-color: #333 !important; }
[data-testid="stChatInputTextArea"] { color: #e0e0e0 !important; }
[data-testid="stChatMessageContent"] { color: #e0e0e0 !important; }
[data-testid="stChatMessage"][aria-label="user"] [data-testid="stChatMessageContent"] { background: #1e3a5f !important; }
[data-testid="stChatMessage"][aria-label="assistant"] [data-testid="stChatMessageContent"] { background: #1a1d23 !important; }
footer { display: none; }
#MainMenu { visibility: hidden; }
.stAppDeployButton { display: none; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("🥗 NutriMind")
st.markdown(
    "Multi-agent AI nutrition assistant — stateful memory, longitudinal health analysis, and human-in-the-loop medical flagging."
)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "USER_#01"
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask about nutrition, log a meal, or get a meal plan..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
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
                    timeout=90,
                )
                resp.raise_for_status()
                reply = resp.json()["response"]
            except requests.exceptions.ConnectionError:
                reply = "Backend not reachable. Run `uv run uvicorn agent.app:api --host 0.0.0.0 --port 8000`."
            except Exception as e:
                reply = f"Error: {e}"

        st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})

with st.sidebar:
    st.image("nutrimind.png", width=40)
    st.markdown("### NutriMind")
    st.markdown("**Thread ID** `USER_#01`")
    st.markdown(f"**Messages** `{len(st.session_state.messages)}`")

    st.divider()

    st.markdown("### Agents")
    st.markdown(
        "- **Memory Agent** — User profiles, meal history\n"
        "- **Nutrition RAG Agent** — Evidence-based Q&A via FAISS + USDA\n"
        "- **Planning Agent** — Adaptive meal plans, goal drift detection, LLM-as-judge eval\n"
        "- **Intake Agent** — Meal logging, running macros, deficiency detection\n"
        "- **Insight Agent** — 14-day pattern analysis, medical flagging, streak tracking"
    )

    st.divider()

    st.markdown("### Tech Stack")
    st.markdown("LangGraph · FastAPI · PostgreSQL · AWS Bedrock · FAISS · LangSmith")

    st.divider()

    st.markdown(
        "Built by [Ahmed (Harvey)](https://github.com/HarveyAGH) — AI Agent Systems Engineer"
    )

    if st.button("Reset conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
