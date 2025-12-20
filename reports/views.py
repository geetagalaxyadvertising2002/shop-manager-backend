# reports/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from shop.models import Sale, Product
from django.db.models import Sum
from datetime import timedelta
from django.utils import timezone


class SalesReportView(APIView):
    def get(self, request):
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        # Default: पिछले 30 दिन (आज सहित)
        today = timezone.now().date()

        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({"error": "Invalid start_date format. Use YYYY-MM-DD."}, status=400)
        else:
            start_date = today - timedelta(days=29)  # 30 days total (including today)

        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({"error": "Invalid end_date format. Use YYYY-MM-DD."}, status=400)
        else:
            end_date = today  # ← आज की date शामिल होगी!

        # Sale records filter (shop-wise + date range)
        sales = Sale.objects.filter(
            shop__owner=request.user,
            sale_date__date__gte=start_date,
            sale_date__date__lte=end_date
        )

        # Aggregations
        total_sales_agg = sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        online_sales_agg = sales.filter(is_online=True).aggregate(Sum('total_amount'))['total_amount__sum'] or 0

        total_sales = float(total_sales_agg)
        online_sales = float(online_sales_agg)
        offline_sales = float(total_sales_agg - online_sales_agg)

        # Product-wise breakdown
        product_sales = sales.values('product__name').annotate(
            total_quantity=Sum('quantity'),
            total_amount=Sum('total_amount')
        ).order_by('-total_amount')

        # Customer-wise breakdown (only if customer exists)
        customer_sales = sales.filter(customer__isnull=False)\
            .values('customer__name')\
            .annotate(
                total_quantity=Sum('quantity'),
                total_amount=Sum('total_amount')
            )\
            .order_by('-total_amount')

        return Response({
            'total_sales': total_sales,
            'online_sales': online_sales,
            'offline_sales': offline_sales,
            'product_sales': list(product_sales),
            'customer_sales': list(customer_sales),
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
        })


class StockReportView(APIView):
    def get(self, request):
        products = Product.objects.filter(shop__owner=request.user)
        low_stock = products.filter(stock_quantity__lte=10)

        low_stock_list = [
            {
                'name': p.name,
                'stock_quantity': p.stock_quantity,
                'id': p.id  # optional: frontend में use हो सकता है
            }
            for p in low_stock.order_by('stock_quantity')
        ]

        return Response({
            'total_products': products.count(),
            'low_stock_products': low_stock_list,
            'low_stock_count': len(low_stock_list),
        })