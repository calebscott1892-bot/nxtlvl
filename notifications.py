"""
NXTLVL notifications.

All notification sends are best-effort. A failed email or SMS is logged and
reported to admin test endpoints, but it never blocks booking creation.
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

logger = logging.getLogger("nxtlvl.notifications")

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "NXTLVL Training")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL") or "raquanbryant18@gmail.com"

TWILIO_SID = os.environ.get("TWILIO_SID", "")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN", "")
TWILIO_FROM = os.environ.get("TWILIO_FROM", "")
NOTIFY_PHONE = os.environ.get("NOTIFY_PHONE", "")

SITE_URL = os.environ.get("SITE_URL", "https://nxtlvl-theta.vercel.app").rstrip("/")
ADMIN_URL = f"{SITE_URL}/admin.html"
COACH_PHONE_DISPLAY = "+1 (910) 507-9984"
ZELLE_DISPLAY = "910-507-9984"
VENMO_HANDLE = "@Raquan-Bryant-1"
VENMO_URL = "https://venmo.com/Raquan-Bryant-1"


def notification_config_status() -> dict:
    return {
        "email_configured": bool(SMTP_USER and SMTP_PASS and NOTIFY_EMAIL),
        "sms_configured": bool(TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM and NOTIFY_PHONE),
        "site_url": SITE_URL,
        "smtp_from_name": SMTP_FROM_NAME,
        "notify_email": NOTIFY_EMAIL,
        "notify_phone": NOTIFY_PHONE,
        "notify_email_set": bool(NOTIFY_EMAIL),
        "notify_phone_set": bool(NOTIFY_PHONE),
    }


def _session_label(booking: dict) -> str:
    if booking["session_type"] == "solo":
        return "1-on-1 Session"
    return f"Small Group Session ({booking['group_size']} players)"


def _time_label(time_value: str) -> str:
    return {
        "08:00": "8:00 AM",
        "09:00": "9:00 AM",
        "10:00": "10:00 AM",
        "11:00": "11:00 AM",
        "12:00": "12:00 PM",
        "13:00": "1:00 PM",
    }.get(time_value, time_value)


def _booking_text(booking: dict) -> str:
    return (
        f"Name:   {booking['name']}\n"
        f"Email:  {booking['email']}\n"
        f"Phone:  {booking['phone']}\n"
        f"Type:   {_session_label(booking)}\n"
        f"Date:   {booking['preferred_date']}\n"
        f"Time:   {_time_label(booking['preferred_time'])}\n"
        f"Notes:  {booking.get('notes') or '-'}\n"
    )


def _send_email(to_email: str, subject: str, body: str) -> tuple[bool, str]:
    if not all([SMTP_USER, SMTP_PASS, to_email]):
        return False, "SMTP is not configured"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())

        logger.info("Email sent to %s", to_email)
        return True, "sent"
    except Exception as exc:
        logger.error("Email notification failed for %s: %s", to_email, exc)
        return False, str(exc)


def send_coach_email_notification(booking: dict) -> tuple[bool, str]:
    subject = f"New Booking Request - {booking['name']}"
    body = (
        "New booking request on NXTLVL Training:\n\n"
        f"{_booking_text(booking)}\n"
        f"Admin: {ADMIN_URL}\n"
    )
    return _send_email(NOTIFY_EMAIL, subject, body)


def send_customer_email_confirmation(booking: dict) -> tuple[bool, str]:
    subject = "NXTLVL booking request received"
    body = (
        f"Hi {booking['name']},\n\n"
        "Your NXTLVL training request has been received.\n\n"
        f"Session: {_session_label(booking)}\n"
        f"Date: {booking['preferred_date']}\n"
        f"Time: {_time_label(booking['preferred_time'])}\n\n"
        "Coach Raquan will review your request and reach out to confirm the session.\n"
        "Your spot is not secured until payment is received after confirmation.\n\n"
        "Payment options:\n"
        f"Zelle: {ZELLE_DISPLAY}\n"
        f"Venmo: {VENMO_HANDLE} ({VENMO_URL})\n\n"
        f"Questions or changes? Text {COACH_PHONE_DISPLAY}.\n\n"
        "NXTLVL Training\n"
    )
    return _send_email(booking["email"], subject, body)


def send_sms_notification(booking: dict) -> tuple[bool, str]:
    if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, NOTIFY_PHONE]):
        return False, "Twilio is not configured"

    body = (
        "New NXTLVL booking!\n"
        f"{booking['name']} - {_session_label(booking)}\n"
        f"{booking['preferred_date']} at {_time_label(booking['preferred_time'])}\n"
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

        logger.info("SMS sent to %s", NOTIFY_PHONE)
        return True, "sent"
    except Exception as exc:
        logger.error("SMS notification failed: %s", exc)
        return False, str(exc)


def notify_new_booking(booking: dict) -> dict:
    coach_email = send_coach_email_notification(booking)
    customer_email = send_customer_email_confirmation(booking)
    sms = send_sms_notification(booking)
    return {
        "coach_email": {"ok": coach_email[0], "message": coach_email[1]},
        "customer_email": {"ok": customer_email[0], "message": customer_email[1]},
        "sms": {"ok": sms[0], "message": sms[1]},
    }


def send_test_notifications() -> dict:
    test_booking = {
        "id": "test",
        "name": "NXTLVL Notification Test",
        "email": NOTIFY_EMAIL or SMTP_USER,
        "phone": NOTIFY_PHONE or COACH_PHONE_DISPLAY,
        "session_type": "solo",
        "group_size": 1,
        "preferred_date": "test-date",
        "preferred_time": "09:00",
        "notes": "This is an admin-triggered notification test.",
    }
    return notify_new_booking(test_booking)
