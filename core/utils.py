# core/utils.py
from sib_api_v3_sdk import Configuration, TransactionalEmailsApi, SendSmtpEmail, SendSmtpEmailSender, SendSmtpEmailTo
from sib_api_v3_sdk.api_client import ApiClient
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_otp_email(email, otp):
    configuration = Configuration()
    configuration.api_key['api-key'] = settings.BREVO_API_KEY

    api_instance = TransactionalEmailsApi(ApiClient(configuration))

    sender = SendSmtpEmailSender(
        name="Your App Name",  # or "Geeta Galaxy"
        email=settings.DEFAULT_FROM_EMAIL
    )

    to = [SendSmtpEmailTo(email=email)]

    send_smtp_email = SendSmtpEmail(
        sender=sender,
        to=to,
        subject="Your OTP Code",
        html_content=f"""
        <h2>Your OTP Code</h2>
        <p>Use this code to verify your email: <strong>{otp}</strong></p>
        <p>This code will expire in 10 minutes.</p>
        <p>If you didn't request this, please ignore this email.</p>
        """
    )

    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        logger.info(f"OTP email sent via Brevo API to {email}")
        print(f"[EMAIL SENT] OTP {otp} sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Brevo API error: {str(e)}")
        print(f"[EMAIL ERROR] Failed to send OTP to {email}: {str(e)}")
        return False