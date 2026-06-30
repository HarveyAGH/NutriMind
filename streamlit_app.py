import os
import sys
import requests
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agent"))

API_URL = os.getenv("NUTRIMIND_API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

st.set_page_config(page_title="NutriMind", page_icon="🥗", layout="centered")

st.title("🥗 NutriMind")
st.markdown("Multi-agent AI nutrition assistant")

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
                    timeout=60,
                )
                resp.raise_for_status()
                reply = resp.json()["response"]
            except Exception as e:
                reply = f"Error: {e}"

        st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})

if st.sidebar.button("Reset conversation"):
    st.session_state.messages = []
    st.session_state.thread_id = "USER_#01"
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### About")
st.sidebar.markdown(
    "NutriMind is a multi-agent AI nutrition assistant built with LangGraph. "
    "It can answer nutrition questions, log meals, track macros, "
    "detect deficiencies, generate meal plans, and analyze long-term patterns."
)
