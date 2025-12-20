from rest_framework import serializers
from .models import AlertPayTransaction, AlertPayAccount


class AlertPayAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertPayAccount
        fields = "__all__"


class AlertPayTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertPayTransaction
        fields = "__all__"
