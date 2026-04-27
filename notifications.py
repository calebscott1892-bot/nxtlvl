"""
NXTLVL Notifications — email + SMS alerts for new bookings.

All functions are best-effort: errors are logged but never raised so a
notification failure can never break the booking flow.

Environment variables
─────────────────────
Email (Gmail SMTP recommended):
  SMTP_HOST      default: smtp.gmail.com
  SMTP_PORT      default: 587
  SMTP_USER      your Gmail address (e.g. nxtlvlcoach@gmail.com)
  SMTP_PASS      Gmail App Password (not your regular password)
  NOTIFY_EMAIL   address to send alerts to (e.g. Raquanbryant18@gmail.com)

SMS (Twilio):
  TWILIO_SID     Twilio Account SID
  TWILIO_TOKEN   Twilio Auth Token
  TWILIO_FROM    Twilio phone number (e.g. +19105550000)
  NOTIFY_PHONE   Coach's phone number (e.g. +19105079984)
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

logger = logging.getLogger("nxtlvl.notifications")

# ── Config from environment ─────────────────────────────────────────────────
SMTP_HOST    = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT    = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER    = os.environ.get("SMTP_USER", "")
SMTP_PASS    = os.environ.get("SMTP_PASS", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "")

TWILIO_SID   = os.environ.get("TWILIO_SID", "")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN", "")
TWILIO_FROM  = os.environ.get("TWILIO_FROM", "")
NOTIFY_PHONE = os.environ.get("NOTIFY_PHONE", "")


# ── Helpers ─────────────────────────────────────────────────────────────────

def _session_label(booking: dict) -> str:
    if booking["session_type"] == "solo":
        return "1-on-1"
    return f"Group ({booking['group_size']})"


def _booking_text(booking: dict) -> str:
    return (
        f"Name:   {booking['name']}\n"
        f"Email:  {booking['email']}\n"
        f"Phone:  {booking['phone']}\n"
        f"Type:   {_session_label(booking)}\n"
        f"Date:   {booking['preferred_date']}\n"
        f"Time:   {booking['preferred_time']}\n"
        f"Notes:  {booking.get('notes') or '—'}\n"
    )


# ── Email ────────────────────────────────────────────────────────────────────

def send_email_notification(booking: dict) -> None:
    """Send a new-booking alert email. Skips silently if SMTP env vars are missing."""
    if not all([SMTP_USER, SMTP_PASS, NOTIFY_EMAIL]):
        logger.debug("Email notification skipped — SMTP not configured")
        return

    try:
        subject = f"New Booking Request — {booking['name']}"
        body = (
            f"New booking request on NXTLVL Training:\n\n"
            f"{_booking_text(booking)}\n"
            f"Log in to confirm or cancel:\n"
            f"https://nxtlvltraining.com/admin.html"
        )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_USER
        msg["To"]      = NOTIFY_EMAIL
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, NOTIFY_EMAIL, msg.as_string())

        logger.info("Email notification sent to %s", NOTIFY_EMAIL)

    except Exception as exc:
        logger.error("Email notification failed: %s", exc)


# ── SMS (Twilio) ─────────────────────────────────────────────────────────────

def send_sms_notification(booking: dict) -> None:
    """Send a new-booking SMS via Twilio REST. Skips silently if env vars are missing."""
    if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, NOTIFY_PHONE]):
        logger.debug("SMS notification skipped — Twilio not configured")
        return

    body = (
        f"New NXTLVL booking!\n"
        f"{booking['name']} — {_session_label(booking)}\n"
        f"{booking['preferred_date']} at {booking['preferred_time']}\n"
        f"Ph: {booking['phone']}"
    )

    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                url,
                auth=(TWILIO_SID, TWILIO_TOKEN),
                data={"From": TWILIO_FROM, "To": NOTIFY_PHONE, "Body": body},
            )
            resp.raise_for_status()

        logger.info("SMS notification sent to %s", NOTIFY_PHONE)

    except Exception as exc:
        logger.error("SMS notification failed: %s", exc)


# ── Public entry point ───────────────────────────────────────────────────────

def notify_new_booking(booking: dict) -> None:
    """Fire email + SMS for a new booking. Always best-effort, never raises."""
    send_email_notification(booking)
    send_sms_notification(booking)
