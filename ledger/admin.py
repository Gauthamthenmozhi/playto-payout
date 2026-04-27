from django.contrib import admin
from .models import Merchant, Transaction

@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'email', 'created_at']

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'merchant', 'type', 'amount_paise', 'description', 'created_at']
    list_filter = ['type', 'merchant']
