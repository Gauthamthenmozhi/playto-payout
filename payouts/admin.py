from django.contrib import admin
from .models import Payout

@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ['id', 'merchant', 'amount_paise', 'status', 'attempt_count', 'created_at', 'updated_at']
    list_filter = ['status', 'merchant']
