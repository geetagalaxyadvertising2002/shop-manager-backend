# core/otp_views.py
import requests
from django.conf import settings
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny


class SendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get("phone_number")
        if not phone:
            return Response({"error": "Phone number is required"}, status=400)

        # Store OTP internally only for verification (MSG91 will generate the SMS OTP)
        otp = 1111  # placeholder, not sent to MSG91
        cache.set(f"otp_{phone}", otp, timeout=300)

        # MSG91 OTP Widget API endpoint
        url = "https://control.msg91.com/api/v5/otp"

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authkey": settings.MSG91_AUTH_KEY,  # AUTH KEY goes in HEADER only
        }

        payload = {
            "mobile": f"91{phone}",
            "template_id": settings.MSG91_TEMPLATE_ID,
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            print("📤 MSG91 PAYLOAD:", payload)
            print("📩 MSG91 RESPONSE:", response.status_code, response.text)

            if response.status_code == 200:
                return Response(
                    {"success": f"OTP sent successfully to {phone}"}, status=200
                )

            return Response(
                {"error": "Failed to send OTP", "response": response.text},
                status=response.status_code,
            )

        except Exception as e:
            return Response({"error": str(e)}, status=500)


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get("phone_number")
        otp = request.data.get("otp")

        if not phone or not otp:
            return Response(
                {"error": "Phone number and OTP required"}, status=400
            )

        cached_otp = cache.get(f"otp_{phone}")

        if cached_otp and str(cached_otp) == str(otp):
            cache.delete(f"otp_{phone}")
            return Response(
                {"verified": True, "message": "OTP verified successfully ✅"}
            )

        return Response(
            {"verified": False, "message": "Invalid or expired OTP ❌"},
            status=400,
        )
