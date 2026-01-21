# core/utils.py
import random
import logging
from django.conf import settings

from brevo_python import (
    Configuration,
    ApiClient,
    TransactionalEmailsApi,
    SendSmtpEmail,
    SendSmtpEmailSender,
    SendSmtpEmailTo,
)

logger = logging.getLogger(__name__)


def generate_otp(length=6):
    """Generate a numeric OTP of specified length."""
    return ''.join(random.choices('0123456789', k=length))


def send_otp_email(email: str, otp: str) -> bool:
    """
    Send OTP verification email using Brevo (Sendinblue) Transactional API.
    
    Returns True if email was sent successfully, False otherwise.
    """
    if not settings.BREVO_API_KEY:
        logger.error("BREVO_API_KEY is not set in settings")
        print("[EMAIL ERROR] BREVO_API_KEY missing")
        return False

    configuration = Configuration()
    configuration.api_key['api-key'] = settings.BREVO_API_KEY

    api_client = ApiClient(configuration)
    api_instance = TransactionalEmailsApi(api_client)

    sender = SendSmtpEmailSender(
        name="Geeta Galaxy",  # Change to your brand/app name if needed
        email=settings.DEFAULT_FROM_EMAIL,
    )

    recipient = SendSmtpEmailTo(email=email)

    email_content = SendSmtpEmail(
        sender=sender,
        to=[recipient],
        subject="Your OTP Code",
        html_content=f"""
        <h2>Your OTP Code</h2>
        <p>Use this code to verify your email:</p>
        <h1 style="font-size: 36px; letter-spacing: 8px; margin: 20px 0;">{otp}</h1>
        <p>This code is valid for <strong>10 minutes</strong>.</p>
        <p>If you didn't request this OTP, please ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <small>Geeta Galaxy - Your trusted platform</small>
        """,
    )

    try:
        response = api_instance.send_transac_email(email_content)
        logger.info(
            f"OTP email sent successfully to {email} | Message ID: {response.message_id}"
        )
        print(f"[EMAIL SENT] OTP {otp} sent to {email}")
        return True

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to send OTP email to {email}: {error_msg}")
        print(f"[EMAIL ERROR] Failed to send OTP to {email}: {error_msg}")
        return False

    finally:
        # No explicit close() needed - ApiClient handles cleanup automatically
        # We just let Python GC handle it
        pass