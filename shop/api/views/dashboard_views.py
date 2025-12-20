from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum
from django.db.models.functions import TruncDate, ExtractHour
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, serializers

# Models
from core.core_models import Shop
from shop.models.sale import Sale
from shop.models.models import Product
from shop.models import purchase_models, expense_models


# ✅ Serializer for consistent API response
class DashboardSerializer(serializers.Serializer):
    profile_strength = serializers.IntegerField()
    total_sales = serializers.FloatField()
    today_sales = serializers.FloatField()
    total_purchases = serializers.FloatField()
    total_expenses = serializers.FloatField()
    monthly_sales = serializers.ListField(child=serializers.FloatField())
    monthly_purchases = serializers.ListField(child=serializers.FloatField())
    notifications = serializers.ListField(child=serializers.CharField(), required=False)


# ✅ Main Dashboard Summary
class DashboardSummaryView(APIView):
    """
    GET /api/dashboard/summary/
    Returns: Profile strength, total/today sales, purchases, expenses, monthly charts, and notifications.
    """
    permission_classes = [IsAuthenticated]

    # 🔹 Profile strength calculator
    def calculate_profile_strength(self, shop: Shop) -> int:
        if not shop:
            return 0
        checks = [
            bool(shop.name),
            bool(getattr(shop, 'shop_logo', None)),
            bool(getattr(shop, 'description', None)),
            bool(getattr(shop, 'address', None)),
            bool(getattr(shop, 'phone_number', None)),
            bool(getattr(shop, 'gst_number', None)),
            getattr(shop, 'is_live', False),
        ]
        per = 100 // len(checks)
        score = sum(per for c in checks if c)
        return min(100, score)

    # 🔹 Generate totals for last N days
    def get_last_n_days_totals(self, model, shop, days=30, date_field='sale_date'):
        if not model:
            return [0.0] * days

        today = timezone.localdate()
        start = today - timedelta(days=days - 1)

        qs = (
            model.objects.filter(
                shop=shop,
                **{f"{date_field}__date__gte": start, f"{date_field}__date__lte": today}
            )
            .annotate(day=TruncDate(date_field, tzinfo=timezone.get_current_timezone()))
            .values('day')
            .annotate(total=Sum('total_amount'))
        )

        totals = {entry['day']: float(entry['total'] or 0) for entry in qs}

        daily = []
        for i in range(days):
            d = start + timedelta(days=i)
            daily.append(float(totals.get(d, 0)))
        return daily

    # 🔹 Main GET logic
    def get(self, request, format=None):
        try:
            shop = Shop.objects.filter(owner=request.user).first()
            if not shop:
                return Response({"error": "No shop found for this user."},
                                status=status.HTTP_404_NOT_FOUND)

            profile_strength = self.calculate_profile_strength(shop)

            # Totals
            total_sales = (
                Sale.objects.filter(shop=shop)
                .aggregate(total=Sum('total_amount'))['total'] or 0.0
            )
            today_local = timezone.localdate()
            today_sales = (
                Sale.objects.filter(shop=shop, sale_date__date=today_local)
                .aggregate(total=Sum('total_amount'))['total'] or 0.0
            )

            Purchase = getattr(purchase_models, 'Purchase', None)
            Expense = getattr(expense_models, 'Expense', None)

            total_purchases = (
                Purchase.objects.filter(shop=shop).aggregate(total=Sum('total_amount'))['total']
                if Purchase else 0.0
            ) or 0.0

            total_expenses = (
                Expense.objects.filter(shop=shop).aggregate(total=Sum('amount'))['total']
                if Expense else 0.0
            ) or 0.0

            # Monthly Trends
            monthly_sales = self.get_last_n_days_totals(Sale, shop, days=30, date_field='sale_date')
            monthly_purchases = (
                self.get_last_n_days_totals(Purchase, shop, days=30, date_field='created_at')
                if Purchase else [0.0] * 30
            )

            # Notifications (Low Stock)
            low_stock_products = Product.objects.filter(
                shop=shop, stock_quantity__lte=10
            ).values('name', 'stock_quantity')[:10]
            notifications = [
                f"Low stock: {p['name']} ({p['stock_quantity']} left)"
                for p in low_stock_products
            ]

            payload = {
                'profile_strength': profile_strength,
                'total_sales': float(total_sales),
                'today_sales': float(today_sales),
                'total_purchases': float(total_purchases),
                'total_expenses': float(total_expenses),
                'monthly_sales': monthly_sales,
                'monthly_purchases': monthly_purchases,
                'notifications': notifications,
            }

            return Response(DashboardSerializer(payload).data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"Failed to fetch dashboard: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ✅ New Hourly Sales View for Graph
class TodaySalesHourlyView(APIView):
    """
    GET /api/sales/today/
    Returns hourly total sales for current day (Asia/Kolkata timezone)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            shop = Shop.objects.filter(owner=request.user).first()
            if not shop:
                return Response({"error": "No shop found for this user."},
                                status=status.HTTP_404_NOT_FOUND)

            tz = timezone.get_current_timezone()
            today_start = timezone.now().astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)

            # ⏰ Hourly aggregation
            qs = (
                Sale.objects.filter(
                    shop=shop,
                    sale_date__gte=today_start,
                    sale_date__lt=today_end
                )
                .annotate(hour=ExtractHour('sale_date'))
                .values('hour')
                .annotate(total=Sum('total_amount'))
                .order_by('hour')
            )

            hourly_data = [
                {"hour": int(entry['hour']), "total": float(entry['total'] or 0)}
                for entry in qs
            ]

            # Ensure all 24h slots (0–23)
            hours_complete = []
            totals_by_hour = {d["hour"]: d["total"] for d in hourly_data}
            for h in range(24):
                hours_complete.append({"hour": h, "total": totals_by_hour.get(h, 0.0)})

            return Response(hours_complete, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
