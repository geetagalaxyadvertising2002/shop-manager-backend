import logging
from rest_framework import viewsets, status
from rest_framework.response import Response
from django.utils import timezone
from .models import Category
from .serializers import CategorySerializer
from core.core_models import Shop

logger = logging.getLogger(__name__)

class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer

    def get_queryset(self):
        user = self.request.user

        shop = Shop.objects.filter(owner=user).first()

        if not shop:
            logger.warning(f"No shop found for user: {user}. Creating new shop...")

            shop = Shop.objects.create(
                owner=user,
                name=f"{user.username}'s Shop",
                address="Default Address",
                created_at=timezone.now(),
                updated_at=timezone.now()
            )

            logger.info(f"Created new shop: {shop.name}")

        logger.info(f"Using shop: {shop.name} for user: {user}")

        return Category.objects.filter(shop=shop)

    def perform_create(self, serializer):
        user = self.request.user
        shop = Shop.objects.filter(owner=user).first()

        if not shop:
            logger.warning(f"No shop found. Creating new shop for: {user}")

            shop = Shop.objects.create(
                owner=user,
                name=f"{user.username}'s Shop",
                address="Default Address",
                created_at=timezone.now(),
                updated_at=timezone.now()
            )

        serializer.save(shop=shop)
        logger.info(f"Category created for shop: {shop.name}")
