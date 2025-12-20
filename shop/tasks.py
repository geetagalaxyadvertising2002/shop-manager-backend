from celery import shared_task
from django.utils import timezone
from shop.models import PendingSale
from django.core.mail import send_mail
import logging

logger = logging.getLogger(__name__)

@shared_task
def notify_due_sales():
    due_sales = PendingSale.objects.filter(
        status='PENDING',
        scheduled_time__lte=timezone.now()
    )
    for sale in due_sales:
        try:
            send_mail(
                subject=f"Scheduled Sale Reminder: {sale.product.name}",
                message=f"Your sale of {sale.quantity} units of {sale.product.name} was scheduled for {sale.scheduled_time}. Please confirm or cancel.",
                from_email='noreply@shopmanager.com',
                recipient_list=[sale.shop.owner.email],
                fail_silently=False,
            )
            logger.info(f"Notification sent for pending sale {sale.id}")
        except Exception as e:
            logger.error(f"Failed to send notification for pending sale {sale.id}: {str(e)}")