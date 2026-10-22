# Email Agent — Streamlit Application

A Streamlit web interface for the Email Agent project. It uses LangGraph to extract the request details, create a professional email with Groq, ask for a missing recipient address when needed, and pause for human review before sending.

## Features

- Describe the email you want in natural language.
- Extracts company, purpose, contact name, and any recipient email explicitly included in the request.
- Asks for the recipient address if it was not provided.
- Generates a subject and a body (aiming for a maximum of 200 words).
- Lets you request revisions or explicitly approve the draft to send.
- Sends mail through Gmail SMTP with credentials loaded from environment variables.

## 1. Requirements

- Python 3.10 or newer
- A Groq API key
- A Gmail account configured to use an App Password (typically requires 2-Step Verification)

## 2. Install

Open a terminal in this project directory:

```bash
python -m venv .venv
```

Activate the environment:

**Windows PowerShell**

```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows Command Prompt**

```bat
.venv\Scripts\activate.bat
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

Install the packages:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Configure environment variables

Copy `.env.example` to a new file named `.env` in this folder, then fill in the values:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
SMTP_SENDER_EMAIL=your_sender_email@gmail.com
SMTP_APP_PASSWORD=your_google_app_password
```

- Create a Groq API key at <https://console.groq.com/keys>.
- For Gmail, use a Google App Password rather than your normal Google password. See Google's help page: <https://support.google.com/accounts/answer/185833>.
- Never share or commit `.env`. It is excluded by `.gitignore`.

## 4. Run the app

```bash
streamlit run app.py
```

Streamlit will print a local URL (usually `http://localhost:8501`) to open in your browser.

## How to use

1. Enter a natural-language description of the email.
2. Provide the recipient's email when asked, if it was not already included.
3. Review the recipient, subject, and body.
4. Choose **Revise draft** with feedback, or **Approve & send email** to send it.

The application does not send an email just because a draft was generated. It requires an explicit approval in the review step.

## Project files

- `app.py` — Streamlit UI and interactive workflow controls.
- `agent.py` — LangGraph workflow and LLM prompts.
- `send_email.py` — Gmail SMTP helper; reads all credentials from environment variables.
- `.env.example` — configuration template; copy it to `.env`.
- `requirements.txt` — Python dependencies.

## Security note

The original `send_email.py` supplied with the project contained a hard-coded Gmail app password. This Streamlit version does not include that password and reads SMTP credentials from `.env` instead. If the original password was real, revoke it in your Google Account and create a replacement App Password before using this app.

## Notes

- LangGraph uses an in-memory checkpointer in this version. Workflow state is not a durable database and may be lost when the app process restarts.
- The UI validates the email address format before resuming the workflow, but you should still verify the address is correct.
- If sending fails, verify Gmail SMTP access and the app-password configuration.
