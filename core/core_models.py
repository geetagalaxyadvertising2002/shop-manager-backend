from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta


class User(AbstractUser):
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    # अगर आप पूरी तरह email पर शिफ्ट कर रहे हैं तो phone_number को हटा भी सकते हैं


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True, null=True)  # अगर email profile में भी रखना चाहें
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.username


class Shop(models.Model):
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.TextField(blank=True)
    description = models.TextField(blank=True, null=True)
    logo = models.URLField(max_length=500, null=True, blank=True)
    banner = models.URLField(max_length=500, null=True, blank=True)
    slug = models.SlugField(unique=True, blank=True, null=True)
    is_live = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class OTPCode(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='otp_codes',
        null=True,
        blank=True
    )
    email = models.EmailField(max_length=255)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=False, blank=False)  # null नहीं हो सकता
    is_used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # हर बार save होने पर अगर expires_at सेट नहीं है तो 10 मिनट बाद का समय डाल दो
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        """OTP अभी वैध है या नहीं"""
        return not self.is_used and timezone.now() <= self.expires_at

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = 'used' if self.is_used else 'valid'
        return f"{self.email} — {self.code} ({status})"