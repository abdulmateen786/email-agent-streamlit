"""SMTP delivery helper. Credentials are read from environment variables."""

import os
import smtplib
from email.message import EmailMessage


def send_mail(recipient_email: str, subject: str, body: str) -> str:
    sender_email = os.getenv("SMTP_SENDER_EMAIL", "").strip()
    sender_password = os.getenv("SMTP_APP_PASSWORD", "").replace(" ", "").strip()

    if not sender_email or not sender_password:
        raise RuntimeError(
            "SMTP credentials are missing. Set SMTP_SENDER_EMAIL and "
            "SMTP_APP_PASSWORD in your .env file."
        )
    if not recipient_email or "@" not in recipient_email:
        raise ValueError("A valid recipient email address is required.")

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender_email, sender_password)
        server.send_message(msg)

    return "Email sent successfully!"
