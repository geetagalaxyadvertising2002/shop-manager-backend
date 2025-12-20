import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from customers.models import Customer, Khata
from customers.serializers import CustomerSerializer, KhataSerializer
from core.core_models import Shop

logger = logging.getLogger(__name__)


# ===================== CUSTOMER VIEWSET =====================
class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return customers linked to current user's shop."""
        try:
            shop = Shop.objects.filter(owner=self.request.user).first()
            if not shop:
                logger.warning(f"No Shop found for user: {self.request.user}")
                return Customer.objects.none()
            return Customer.objects.filter(shop=shop)
        except Exception as e:
            logger.error(f"Error in get_queryset: {e}", exc_info=True)
            return Customer.objects.none()

    def perform_create(self, serializer):
        """Attach customer to current user's shop on creation."""
        try:
            shop = Shop.objects.filter(owner=self.request.user).first()
            if not shop:
                raise APIException(detail="No shop associated with this user.", code=400)
            serializer.save(shop=shop)
            logger.info(f"Customer created for user: {self.request.user}, shop: {shop}")
        except Exception as e:
            logger.error(f"Error creating customer: {str(e)}", exc_info=True)
            raise APIException(detail=f"Failed to create customer: {str(e)}", code=500)

    # ✅ Send Payment Reminder (SMS/WhatsApp placeholder)
    @action(detail=True, methods=['post'])
    def send_reminder(self, request, pk=None):
        customer = self.get_object()
        message = f"Hello {customer.name}, you have a pending due of ₹{customer.due_amount} for {customer.shop.name}."
        # 🔹 TODO: Integrate with MSG91 or Twilio API
        logger.info(f"Reminder sent to {customer.phone_number}: {message}")
        return Response({
            "status": "success",
            "message": f"Reminder sent to {customer.name} ({customer.phone_number})"
        }, status=status.HTTP_200_OK)

    # ✅ Quick “Payment Received”
    @action(detail=True, methods=['post'])
    def payment_received(self, request, pk=None):
        customer = self.get_object()
        amount = float(request.data.get("amount", 0))
        if amount <= 0:
            return Response({"error": "Amount must be greater than 0"}, status=400)
        customer.due_amount = max(0, float(customer.due_amount) - amount)
        customer.save()
        logger.info(f"Payment received ₹{amount} from {customer.name}")
        return Response({
            "status": "success",
            "message": f"Payment of ₹{amount} marked as received from {customer.name}",
            "remaining_due": customer.due_amount
        }, status=status.HTTP_200_OK)

    # ✅ Quick “Payment Given”
    @action(detail=True, methods=['post'])
    def payment_given(self, request, pk=None):
        customer = self.get_object()
        amount = float(request.data.get("amount", 0))
        if amount <= 0:
            return Response({"error": "Amount must be greater than 0"}, status=400)
        customer.due_amount += amount
        customer.save()
        logger.info(f"Payment given ₹{amount} to {customer.name}")
        return Response({
            "status": "success",
            "message": f"Payment of ₹{amount} marked as given to {customer.name}",
            "total_due": customer.due_amount
        }, status=status.HTTP_200_OK)

    # ✅ Summary API (for Party Tab header: “You will give ₹X / You will get ₹Y”)
    @action(detail=False, methods=['get'])
    def summary(self, request):
        shop = Shop.objects.filter(owner=self.request.user).first()
        if not shop:
            return Response({"error": "Shop not found"}, status=404)
        customers = Customer.objects.filter(shop=shop)
        total_you_will_get = sum([c.due_amount for c in customers if c.due_amount > 0])
        total_you_will_give = sum([-c.due_amount for c in customers if c.due_amount < 0])
        return Response({
            "you_will_get": total_you_will_get,
            "you_will_give": total_you_will_give
        })


# ===================== KHATA VIEWSET =====================
class KhataViewSet(viewsets.ModelViewSet):
    serializer_class = KhataSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return khata entries for current shop."""
        try:
            shop = Shop.objects.filter(owner=self.request.user).first()
            if not shop:
                logger.warning(f"No Shop found for user: {self.request.user}")
                return Khata.objects.none()
            return Khata.objects.filter(customer__shop=shop)
        except Exception as e:
            logger.error(f"Error fetching Khata queryset: {e}", exc_info=True)
            return Khata.objects.none()

    def perform_create(self, serializer):
        """Create khata entry linked with customer's shop."""
        try:
            shop = Shop.objects.filter(owner=self.request.user).first()
            if not shop:
                raise APIException(detail="No shop associated with this user.", code=400)
            serializer.save()
            logger.info(f"Khata created for user: {self.request.user}, shop: {shop}")
        except Exception as e:
            logger.error(f"Error creating khata: {str(e)}", exc_info=True)
            raise APIException(detail=f"Failed to create khata: {str(e)}", code=500)
