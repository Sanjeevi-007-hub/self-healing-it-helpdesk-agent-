"""
Self-Healing IT Helpdesk Agent — Streamlit UI.

    streamlit run app.py
"""

import uuid

import streamlit as st

from src import memory
from src.orchestrator import HelpdeskAgent
from src.rag import build_index

st.set_page_config(page_title="Self-Healing IT Helpdesk Agent", page_icon="🛠️", layout="centered")


@st.cache_resource
def get_kb():
    return build_index()


if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "chat" not in st.session_state:
    st.session_state.chat = []  # list of (role, text)
if "pending" not in st.session_state:
    st.session_state.pending = None  # holds an AgentResponse awaiting confirm/feedback

kb = get_kb()
agent = HelpdeskAgent(kb, st.session_state.session_id)

st.title("🛠️ Self-Healing IT Helpdesk Agent")
st.caption(
    "RAG + Tool-Calling + Memory, gated by a confidence score that decides "
    "whether the agent fixes it itself, asks first, or escalates to a human."
)

with st.sidebar:
    st.subheader("How it decides")
    st.markdown(
        f"- **≥ {int(80)}% confidence** → fixes it automatically (safe actions only)\n"
        f"- **45–79% confidence** → proposes the fix, waits for your OK\n"
        f"- **< 45% confidence** → asks a clarifying question or opens a ticket\n"
    )
    st.subheader("Recent tickets")
    for t in memory.recent_tickets(8):
        st.markdown(f"`{t[0]}` — {t[2]} ({t[3]:.0%}) — *{t[4]}*")

for role, text in st.session_state.chat:
    with st.chat_message(role):
        st.markdown(text)

# Confirm / feedback controls for the last agent turn, if any
if st.session_state.pending:
    resp = st.session_state.pending
    cols = st.columns(2)
    if resp.awaiting_confirmation:
        if cols[0].button("✅ Yes, go ahead"):
            confirmed = agent.confirm(resp.kb_article_id, None, "user-confirmed fix", resp.confidence)
            st.session_state.chat.append(("assistant", confirmed.message))
            st.session_state.pending = confirmed if confirmed.kb_article_id else None
            st.rerun()
        if cols[1].button("❌ No, open a ticket instead"):
            from src import tools
            ticket = tools.run_tool("create_ticket", summary="User declined proposed fix", priority="medium")
            st.session_state.chat.append(("assistant", f"No problem — ticket {ticket['ticket_id']} opened for a human agent."))
            st.session_state.pending = None
            st.rerun()
    elif resp.kb_article_id and resp.decision in ("auto_remediate", "confirmed"):
        st.write("Did this resolve your issue?")
        if cols[0].button("👍 Yes, fixed"):
            agent.submit_feedback(resp.kb_article_id, True)
            st.session_state.chat.append(("assistant", "Great, glad that worked! Logged for future accuracy."))
            st.session_state.pending = None
            st.rerun()
        if cols[1].button("👎 No, still broken"):
            agent.submit_feedback(resp.kb_article_id, False)
            st.session_state.chat.append(("assistant", "Sorry about that — I've lowered my confidence in this fix and opened a follow-up ticket."))
            from src import tools
            tools.run_tool("create_ticket", summary="Auto-fix did not resolve issue", priority="high")
            st.session_state.pending = None
            st.rerun()

if prompt := st.chat_input("Describe your IT issue..."):
    st.session_state.chat.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    response = agent.handle(prompt)

    with st.chat_message("assistant"):
        st.markdown(response.message)
        with st.expander("Agent reasoning (debug)"):
            st.json(response.debug)

    st.session_state.chat.append(("assistant", response.message))
    st.session_state.pending = response
    st.rerun()
