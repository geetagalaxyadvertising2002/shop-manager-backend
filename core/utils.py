# utils.py
from django.core.mail import send_mail
from django.conf import settings
import random

def generate_otp():
    return ''.join(random.choices('0123456789', k=6))

def send_otp_email(email, otp):
    subject = 'Your OTP Code'
    message = f'Your OTP is {otp}. It is valid for 10 minutes.'
    html_message = f"""
    <h2>Your OTP Code</h2>
    <p>Use this code to verify your email: <strong>{otp}</strong></p>
    <p>This code will expire in 10 minutes.</p>
    <p>If you didn't request this, please ignore this email.</p>
    """

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        print(f"[EMAIL SENT] OTP {otp} sent to {email}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send OTP to {email}: {str(e)}")
        return False