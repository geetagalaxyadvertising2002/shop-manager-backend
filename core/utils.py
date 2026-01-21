# core/utils.py
import random
from brevo_python import Configuration, TransactionalEmailsApi, SendSmtpEmail, SendSmtpEmailSender, SendSmtpEmailTo
from brevo_python import ApiClient  # Note: no .api_client submodule in most cases
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def generate_otp():
    return ''.join(random.choices('0123456789', k=6))

def send_otp_email(email, otp):
    configuration = Configuration()
    configuration.api_key['api-key'] = settings.BREVO_API_KEY

    # Create client without 'with'
    api_client = ApiClient(configuration)
    api_instance = TransactionalEmailsApi(api_client)

    sender = SendSmtpEmailSender(
        name="Geeta Galaxy",  # Or your app name
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
        logger.info(f"OTP email sent via Brevo to {email} - Message ID: {api_response.message_id}")
        print(f"[EMAIL SENT] OTP {otp} sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Brevo API error for {email}: {str(e)}")
        print(f"[EMAIL ERROR] Failed to send OTP to {email}: {str(e)}")
        return False
    finally:
        # Good practice: close the client to free resources
        api_client.close()