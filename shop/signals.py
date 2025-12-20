# shop/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import random
import logging

from shop.models.sale import Sale
from shop.models import Invoice, InvoiceItem, CashbookEntry

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Sale)
def create_invoice_for_sale(sender, instance, created, **kwargs):
    """
    Jab bhi Sale create hoti hai, automatic Invoice aur InvoiceItem ban jaye.
    (Agar pehle se invoice na bana ho)
    """
    try:
        if not created:
            return  # only for new sales

        # Check if invoice already exists for same sale
        existing_invoice = Invoice.objects.filter(
            shop=instance.shop,
            total_amount=instance.total_amount,
            created_at__date=timezone.now().date()
        ).first()

        if existing_invoice:
            logger.info(f"Sale {instance.id} already linked to invoice {existing_invoice.id}")
            return

        # Create invoice number
        invoice_number = f"INV-{random.randint(10000, 99999)}"

        # Create Invoice
        invoice = Invoice.objects.create(
            shop=instance.shop,
            invoice_number=invoice_number,
            total_amount=instance.total_amount,
            is_online=instance.is_online,
            customer_name=getattr(instance.customer, "name", instance.customer_name or "Walk-in Customer"),
            note="Auto-generated from Sale",
            created_at=timezone.now()
        )

        # Create InvoiceItem
        InvoiceItem.objects.create(
            invoice=invoice,
            product=instance.product,
            quantity=instance.quantity,
            unit_price=instance.unit_price
        )

        logger.info(f"✅ Auto-invoice created for sale {instance.id} → Invoice {invoice.invoice_number}")

    except Exception as e:
        logger.error(f"❌ Error creating invoice for sale {instance.id}: {str(e)}", exc_info=True)

CashbookEntry.objects.create(
    shop=instance.shop,
    entry_type='IN',
    amount=instance.total_amount,
    note=f"Sale: {instance.product.name}",
    is_online=getattr(instance, 'is_online', False)
)