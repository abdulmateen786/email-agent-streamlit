"""LangGraph workflow for the Email Agent Streamlit application."""

import os
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from send_email import send_mail

load_dotenv()


@lru_cache(maxsize=1)
def get_llm() -> ChatGroq:
    """Create the Groq client only when a model call is needed."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add your Groq API key to the .env file."
        )

    return ChatGroq(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        api_key=api_key,
    )


class EmailState(BaseModel):
    question: str = ""
    company_name: str = ""
    mail_reason: str = ""
    recipient_name: str = ""
    recipient_email: str = ""
    subject: str = ""
    body: str = ""
    feedback: str = ""
    feedback_count: int = 0
    response: str = ""


class UserDetails(BaseModel):
    company_name: str = Field(
        default="", description="Company the user wants to contact"
    )
    mail_reason: str = Field(
        default="", description="Purpose of sending the email"
    )
    recipient_name: str = Field(
        default="", description="Contact person's name, if provided"
    )
    recipient_email: str = Field(
        default="", description="Email address explicitly provided by the user"
    )


class DraftEmail(BaseModel):
    subject: str = Field(description="Professional email subject, maximum 40 words")
    body: str = Field(description="Professional email body, maximum 200 words")


def retriever_node(state: EmailState) -> dict:
    extractor = get_llm().with_structured_output(UserDetails)
    details = extractor.invoke(
        f"""
        Extract details from this user request:
        {state.question}

        Return company name, purpose, contact person's name, and recipient email address.
        Only extract an email address explicitly present in the request. Never invent an
        email address. If a field is unknown, return an empty string.
        """
    )

    updates = {
        "company_name": details.company_name,
        "mail_reason": details.mail_reason,
        "recipient_name": details.recipient_name,
        "recipient_email": details.recipient_email.strip(),
    }
    if not details.mail_reason.strip():
        updates["response"] = "Please provide the reason for sending the email."
    return updates


def route_after_retriever(
    state: EmailState,
) -> Literal["collect_email", "draft", "cancel"]:
    if not state.mail_reason.strip():
        return "cancel"
    if not state.recipient_email or "@" not in state.recipient_email:
        return "collect_email"
    return "draft"


def collect_email_node(state: EmailState) -> dict:
    email = interrupt(
        {
            "message": (
                f"Please enter the official email address for "
                f"{state.company_name or 'the recipient'}."
            )
        }
    )
    recipient_email = str(email).strip()
    updates = {"recipient_email": recipient_email}
    if not recipient_email or "@" not in recipient_email:
        updates["response"] = "Email not sent. A valid recipient email is required."
    return updates


def route_after_email(state: EmailState) -> Literal["draft", "cancel"]:
    if not state.recipient_email or "@" not in state.recipient_email:
        return "cancel"
    return "draft"


def draft_node(state: EmailState) -> dict:
    draft_llm = get_llm().with_structured_output(DraftEmail)

    if state.feedback.strip():
        prompt = f"""
        Revise the existing email using the user's feedback.

        Company: {state.company_name}
        Recipient: {state.recipient_name}
        Purpose: {state.mail_reason}
        Current subject: {state.subject}
        Current body: {state.body}
        User feedback: {state.feedback}

        Return an improved professional subject and body. Keep the body within 200 words.
        """
    else:
        prompt = f"""
        Write a professional email for the user.

        Company: {state.company_name}
        Recipient name: {state.recipient_name}
        Purpose: {state.mail_reason}

        Write a suitable subject and body. Keep the body within 200 words.
        Do not invent personal details or qualifications.
        Return only the structured email output.
        """

    draft = draft_llm.invoke(prompt)
    return {"subject": draft.subject, "body": draft.body}


def review_node(state: EmailState) -> dict:
    response = interrupt(
        {"message": "Approve the draft to send it, or provide feedback to revise it."}
    )
    answer = str(response).strip()

    if answer.lower() in ("yes", "y"):
        return {"feedback": ""}
    return {"feedback": answer, "feedback_count": state.feedback_count + 1}


def router(state: EmailState) -> Literal["draft", "send", "cancel"]:
    if not state.feedback.strip():
        return "send"
    if state.feedback_count >= 3:
        return "cancel"
    return "draft"


def cancel_node(state: EmailState) -> dict:
    if not state.response:
        return {"response": "Email not sent. Maximum feedback limit reached."}
    return {}


def send_node(state: EmailState) -> dict:
    if not state.recipient_email or "@" not in state.recipient_email:
        return {"response": "Email not sent: recipient email is missing or invalid."}

    try:
        response = str(send_mail(state.recipient_email, state.subject, state.body))
    except Exception as exc:
        response = f"Failed to send email: {exc}"
    return {"response": response}


def build_graph():
    graph = StateGraph(EmailState)
    graph.add_node("retriever", retriever_node)
    graph.add_node("collect_email", collect_email_node)
    graph.add_node("draft", draft_node)
    graph.add_node("review_node", review_node)
    graph.add_node("send", send_node)
    graph.add_node("cancel", cancel_node)

    graph.add_edge(START, "retriever")
    graph.add_conditional_edges(
        "retriever",
        route_after_retriever,
        {"collect_email": "collect_email", "draft": "draft", "cancel": "cancel"},
    )
    graph.add_conditional_edges(
        "collect_email",
        route_after_email,
        {"draft": "draft", "cancel": "cancel"},
    )
    graph.add_edge("draft", "review_node")
    graph.add_conditional_edges(
        "review_node",
        router,
        {"draft": "draft", "send": "send", "cancel": "cancel"},
    )
    graph.add_edge("send", END)
    graph.add_edge("cancel", END)

    return graph.compile(checkpointer=InMemorySaver())


# The checkpointer keeps each Streamlit session's interrupted workflow resumable.
final_graph = build_graph()


def thread_config(thread_id: str) -> dict:
    """Return the LangGraph config for a Streamlit workflow thread."""
    return {"configurable": {"thread_id": thread_id}}


def resume_workflow(thread_id: str, resume_value: str):
    """Resume a paused workflow with email input or human review feedback."""
    return final_graph.invoke(
        Command(resume=resume_value), config=thread_config(thread_id)
    )
