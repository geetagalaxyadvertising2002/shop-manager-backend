import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.authtoken.models import Token
from django.db import IntegrityError
from core.core_models import User, Profile, Shop
from django.http import JsonResponse
from django.core.management import call_command
from .serializers import UserSerializer, ProfileSerializer, ShopSerializer

logger = logging.getLogger(__name__)


# ✅ USER REGISTRATION
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = UserSerializer(data=request.data)
            if not serializer.is_valid():
                logger.debug(f"Serializer errors: {serializer.errors}")
                return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            user = serializer.save()

            Profile.objects.create(
             user=user,
             phone_number=request.data.get('phone_number', '')
           )

            token, _ = Token.objects.get_or_create(user=user)

            logger.info(f"User registered: {user.username}")

            return Response({
                'token': token.key,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'phone_number': user.phone_number,
                }
            }, status=status.HTTP_201_CREATED)

        except IntegrityError as e:
            logger.error(f"Registration database error: {str(e)}", exc_info=True)
            return Response({'error': f'Database error: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Registration error: {str(e)}", exc_info=True)
            return Response({'error': f'Server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ✅ PROFILE MANAGEMENT
class ProfileView(APIView):
    def get(self, request):
        try:
            profile = Profile.objects.get(user=request.user)
            serializer = ProfileSerializer(profile)
            return Response(serializer.data)
        except Profile.DoesNotExist:
            logger.warning(f"No profile found for user: {request.user}")
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request):
        try:
            profile = Profile.objects.get(user=request.user)
            serializer = ProfileSerializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                logger.info(f"Profile updated for user: {request.user}")
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Profile.DoesNotExist:
            logger.warning(f"Profile not found while updating for user: {request.user}")
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error updating profile: {str(e)}", exc_info=True)
            return Response({"error": f"Failed to update profile: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ✅ SHOP CREATION (Standalone API - Optional, ViewSet bhi handle karta hai)
class ShopCreateView(APIView):
    def post(self, request):
        try:
            if Shop.objects.filter(owner=request.user).exists():
                logger.warning(f"User {request.user} already has a shop.")
                return Response({"error": "User already has a shop"}, status=status.HTTP_400_BAD_REQUEST)

            serializer = ShopSerializer(data=request.data)
            if serializer.is_valid():
                shop = serializer.save(owner=request.user)
                logger.info(f"Shop created for user: {request.user}, ID: {shop.id}")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating shop: {str(e)}", exc_info=True)
            return Response({"error": f"Failed to create shop: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ✅ MAIN SHOP VIEWSET - YE SAB HANDLE KARTA HAI
class ShopViewSet(viewsets.ModelViewSet):
    serializer_class = ShopSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        logger.debug(f"ShopViewSet - User: {user} (ID: {user.id if user.is_authenticated else 'Anonymous'}), Authenticated: {user.is_authenticated}")

        if user.is_authenticated and user.is_staff:
            logger.debug("Admin/Staff - Returning ALL shops")
            return Shop.objects.all().order_by('-created_at')

        elif user.is_authenticated:
            logger.debug(f"Normal authenticated user (ID: {user.id}) - Returning ONLY their shop")
            return Shop.objects.filter(owner=user)

        else:
            logger.debug("Unauthenticated - Returning only LIVE shops")
            return Shop.objects.filter(is_live=True).order_by('-created_at')


    def perform_create(self, serializer):
        """Ek user ka sirf ek shop - agar pehle se hai to update kar do"""
        user = self.request.user
        existing_shop = Shop.objects.filter(owner=user).first()

        if existing_shop:
            # Update existing shop
            updated = self.get_serializer(existing_shop, data=self.request.data, partial=True)
            updated.is_valid(raise_exception=True)
            updated.save()
            logger.info(f"Existing shop updated for user: {user}")
        else:
            # Create new shop
            serializer.save(owner=user)
            logger.info(f"New shop created for user: {user}")

    def perform_update(self, serializer):
        serializer.save()
        logger.info(f"Shop updated by user: {self.request.user}")

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Shop ko live kar do (public website pe dikhega)"""
        try:
            shop = self.get_object()
            if shop.owner != request.user:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            shop.is_live = True
            shop.save()
            public_url = f'https://corestore.netlify.app/shop.html?slug={shop.slug}'

            logger.info(f"Shop published: {shop.name} - {public_url}")
            return Response({
                'status': 'live',
                'message': 'Shop published successfully',
                'public_url': public_url
            })
        except Exception as e:
            logger.error(f"Error publishing shop: {e}")
            return Response({'error': 'Failed to publish shop'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def toggle_live(self, request, pk=None):
        """Live/Unlive toggle"""
        try:
            shop = self.get_object()
            if shop.owner != request.user:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            shop.is_live = not shop.is_live
            shop.save()
            status_msg = "Shop is now LIVE" if shop.is_live else "Shop is now HIDDEN"

            logger.info(f"{status_msg} - {shop.name}")
            return Response({
                'is_live': shop.is_live,
                'message': status_msg
            })
        except Exception as e:
            logger.error(f"Error toggling live state: {e}")
            return Response({'error': 'Failed to toggle live state'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ✅ ADMIN - ALL USERS LIST
class AdminUserListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        users = User.objects.all().order_by('-date_joined')
        data = []

        for user in users:
            shop = Shop.objects.filter(owner=user).first()
            data.append({
                "id": user.id,
                "username": user.username,
                "phone_number": getattr(user, 'phone_number', ''),
                "date_joined": user.date_joined,
                "is_active": user.is_active,
                "has_shop": bool(shop),
                "shop_name": shop.name if shop else None,
            })

        return Response({
            "total_users": users.count(),
            "users": data
        })

def run_makemigrations(request):
    key = request.GET.get("key")
    if key != "super-system-secret-12345":
        return JsonResponse({"error": "Unauthorized"}, status=403)

    call_command("makemigrations")
    return JsonResponse({"status": "makemigrations done"})


def run_migrate(request):
    key = request.GET.get("key")
    if key != "super-system-secret-12345":
        return JsonResponse({"error": "Unauthorized"}, status=403)

    call_command("migrate")
    return JsonResponse({"status": "migrate done"})

# ✅ HEALTH CHECK API
class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "status": "ok",
            "message": "Server is healthy 🚀"
        }, status=status.HTTP_200_OK)
