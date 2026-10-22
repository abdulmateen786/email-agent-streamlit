"""Read settings from local environment or Streamlit Community Cloud secrets."""

import os
from dotenv import load_dotenv

load_dotenv()


def get_setting(name: str, default: str = "") -> str:
    """Return a setting, preferring environment variables over Streamlit secrets."""
    value = os.getenv(name, "")
    if value and value.strip():
        return value.strip()

    try:
        import streamlit as st

        value = st.secrets.get(name, default)
        if value is not None and str(value).strip():
            return str(value).strip()
    except Exception:
        # Secrets may not be configured while running locally.
        pass

    return default
