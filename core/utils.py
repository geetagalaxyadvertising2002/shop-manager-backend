# core/utils.py
import random

def generate_otp():
    return ''.join(random.choices('0123456789', k=6))

# You can implement SMS sending later
# For now we'll just print OTP to console (development)
def send_otp_sms(phone, otp):
    print(f"[SMS SIMULATION] OTP {otp} sent to {phone}")
    # Later: integrate Twilio / MSG91 / Fast2SMS etc.
    return True