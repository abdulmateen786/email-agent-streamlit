"""Streamlit user interface for Email Agent."""

import os
import re
import uuid

import streamlit as st
from dotenv import load_dotenv
from agent import final_graph, resume_workflow, thread_config

load_dotenv()
st.set_page_config(
    page_title="Email Agent",
    page_icon="✉️",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {max-width: 1000px; padding-top: 2.3rem; padding-bottom: 3rem;}
      .hero {padding: 1.35rem 1.5rem; border: 1px solid rgba(128,128,128,.25);
             border-radius: 18px; margin-bottom: 1.2rem;}
      .hero p {margin-bottom: 0; opacity: .78;}
      .eyebrow {font-size: .78rem; font-weight: 700; letter-spacing: .12em;
                text-transform: uppercase; opacity: .7;}
      .email-preview {padding: 1rem 1.1rem; border: 1px solid rgba(128,128,128,.28);
                      border-radius: 12px; margin: .45rem 0 1rem 0;}
      .email-label {font-size: .78rem; text-transform: uppercase; letter-spacing: .07em;
                    opacity: .65; font-weight: 700; margin-bottom: .2rem;}
      div[data-testid="stForm"] {border: 1px solid rgba(128,128,128,.25);
                                   border-radius: 14px; padding: 1rem 1rem .5rem 1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def get_snapshot(thread_id: str):
    return final_graph.get_state(thread_config(thread_id))


def values_as_dict(snapshot) -> dict:
    values = snapshot.values or {}
    if hasattr(values, "model_dump"):
        return values.model_dump()
    return dict(values)


def valid_email(value: str) -> bool:
    value = value.strip()
    return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value))


def clear_workflow() -> None:
    st.session_state.pop("email_agent_thread_id", None)
    st.session_state.pop("email_agent_last_error", None)
    st.rerun()


def start_workflow(question: str) -> None:
    thread_id = uuid.uuid4().hex
    st.session_state.email_agent_thread_id = thread_id
    st.session_state.pop("email_agent_last_error", None)
    with st.spinner("Understanding your request and preparing the workflow…"):
        try:
            final_graph.invoke({"question": question.strip()}, config=thread_config(thread_id))
        except Exception as exc:
            st.session_state.email_agent_last_error = str(exc)
            st.session_state.pop("email_agent_thread_id", None)
    st.rerun()


def run_resume(thread_id: str, value: str) -> None:
    with st.spinner("Working on your email…"):
        try:
            resume_workflow(thread_id, value)
            st.session_state.pop("email_agent_last_error", None)
        except Exception as exc:
            st.session_state.email_agent_last_error = str(exc)
    st.rerun()


with st.sidebar:
    st.markdown("## ✉️ Email Agent")
    st.caption("AI-assisted professional email drafting")
    st.divider()
    st.markdown("**Configuration**")
    checks = [
        ("Groq API key", bool(os.getenv("GROQ_API_KEY", "").strip())),
        ("SMTP sender email", bool(os.getenv("SMTP_SENDER_EMAIL", "").strip())),
        ("SMTP app password", bool(os.getenv("SMTP_APP_PASSWORD", "").strip())),
    ]
    for label, ready in checks:
        st.write(f"{'✅' if ready else '⚪'} {label}")
    if not all(ready for _, ready in checks):
        st.info("Add missing values to `.env` using `.env.example` as a guide.")
    st.divider()
    st.caption("Emails are sent only after you explicitly approve the draft.")
    st.caption("Workflow state is held in memory while the app process is running.")

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">Your writing assistant</div>
      <h1 style="margin:.3rem 0 .35rem 0;">Email Agent</h1>
      <p>Describe who you need to contact and why. Review the AI-generated email before it is sent.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

thread_id = st.session_state.get("email_agent_thread_id")
last_error = st.session_state.get("email_agent_last_error")
if last_error:
    st.error(last_error)
    st.caption("Check your API key and SMTP settings in `.env`, then start a new email.")

snapshot = None
state = {}
if thread_id:
    try:
        snapshot = get_snapshot(thread_id)
        state = values_as_dict(snapshot)
    except Exception as exc:
        st.error(f"Could not load this workflow: {exc}")
        snapshot = None

pending_nodes = tuple(snapshot.next) if snapshot is not None else ()
pending_node = pending_nodes[0] if pending_nodes else None

if thread_id and pending_node:
    left, right = st.columns([3, 1])
    with left:
        st.subheader("Current email workflow")
    with right:
        if st.button("Start new", use_container_width=True):
            clear_workflow()

    step_names = ["Understand request", "Draft email", "Review & send"]
    if pending_node == "collect_email":
        current_step = 1
    elif pending_node in ("draft", "review_node"):
        current_step = 2 if pending_node == "review_node" else 1
    else:
        current_step = 2
    progress_cols = st.columns(3)
    for i, (col, label) in enumerate(zip(progress_cols, step_names)):
        with col:
            marker = "✓" if i < current_step else ("●" if i == current_step else "○")
            st.markdown(f"**{marker} {label}**")

    if pending_node == "collect_email":
        company = state.get("company_name") or "the recipient"
        st.info(f"I need an email address before I can draft the message to **{company}**.")
        with st.form("recipient_email_form"):
            recipient_email = st.text_input(
                "Recipient email address",
                placeholder="name@company.com",
                value=state.get("recipient_email", ""),
            )
            email_submitted = st.form_submit_button(
                "Continue to draft", type="primary", use_container_width=True
            )
        if email_submitted:
            if not valid_email(recipient_email):
                st.error("Enter a valid email address, such as name@company.com.")
            else:
                run_resume(thread_id, recipient_email.strip())

    elif pending_node == "review_node":
        st.markdown("Review the details and email below. Nothing will be sent until you approve it.")
        info1, info2 = st.columns(2)
        with info1:
            st.markdown("**Company / recipient**")
            st.write(state.get("company_name") or "Not specified")
            st.markdown("**Contact person**")
            st.write(state.get("recipient_name") or "Not specified")
        with info2:
            st.markdown("**To**")
            st.write(state.get("recipient_email") or "Not specified")
            st.markdown("**Purpose**")
            st.write(state.get("mail_reason") or "Not specified")

        st.markdown('<div class="email-preview">', unsafe_allow_html=True)
        st.markdown('<div class="email-label">Subject</div>', unsafe_allow_html=True)
        st.markdown(f"**{state.get('subject', '')}**")
        st.markdown('<div class="email-label" style="margin-top:.9rem;">Email body</div>', unsafe_allow_html=True)
        st.text(state.get("body", ""))
        st.markdown("</div>", unsafe_allow_html=True)

        if state.get("feedback_count", 0):
            st.caption(f"Revision feedback submitted: {state.get('feedback_count', 0)}")
        with st.form("review_email_form"):
            feedback = st.text_area(
                "Revision instructions (optional unless revising)",
                placeholder="For example: make the tone warmer, shorten the second paragraph…",
                height=100,
            )
            send_clicked_col, revise_clicked_col = st.columns(2)
            with send_clicked_col:
                approve = st.form_submit_button(
                    "Approve & send email", type="primary", use_container_width=True
                )
            with revise_clicked_col:
                revise = st.form_submit_button("Revise draft", use_container_width=True)
        if approve:
            run_resume(thread_id, "YES")
        elif revise:
            if not feedback.strip():
                st.error("Enter feedback before asking for a revision.")
            else:
                run_resume(thread_id, feedback.strip())
    else:
        st.warning(f"The workflow is paused at an unexpected step: {pending_node}")
        if st.button("Start over", type="primary"):
            clear_workflow()

elif thread_id and snapshot is not None and not pending_nodes:
    response = str(state.get("response") or "Workflow completed.")
    if "successfully" in response.lower():
        st.success(response)
    elif "not sent" in response.lower() or "failed" in response.lower():
        st.error(response)
    else:
        st.info(response)

    with st.expander("Email workflow summary", expanded=True):
        st.write(f"**Company:** {state.get('company_name') or 'Not specified'}")
        st.write(f"**Recipient:** {state.get('recipient_email') or 'Not specified'}")
        if state.get("subject"):
            st.write(f"**Subject:** {state.get('subject')}")
        if state.get("body"):
            st.write(state.get("body"))
    if st.button("Create another email", type="primary"):
        clear_workflow()

else:
    st.subheader("What email do you need?")
    st.caption("Include the company, purpose, recipient name (if known), and recipient email (if you have it).")
    with st.form("new_email_form", clear_on_submit=False):
        question = st.text_area(
            "Describe your email",
            placeholder=(
                "Write a professional email to ABC Company asking about a software internship. "
                "The contact person is Sara and their email is sara@example.com."
            ),
            height=150,
        )
        start_clicked = st.form_submit_button(
            "Generate email draft", type="primary", use_container_width=True
        )
    if start_clicked:
        if not question.strip():
            st.error("Describe the email you want to write first.")
        elif not os.getenv("GROQ_API_KEY", "").strip():
            st.error("GROQ_API_KEY is not configured. Add it to your .env file, then restart Streamlit.")
        else:
            start_workflow(question)

st.divider()
st.caption("Please verify the recipient and review the wording carefully before approving any email.")
