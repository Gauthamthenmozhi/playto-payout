import uuid
from django.db import models

class Payout(models.Model):
    STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    merchant = models.ForeignKey(
        'ledger.Merchant',
        on_delete=models.PROTECT,
        related_name='payouts'
    )
    amount_paise = models.BigIntegerField()
    bank_account_id = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    idempotency_key = models.CharField(max_length=200)
    attempt_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['merchant', 'idempotency_key']

    def __str__(self):
        return f"{self.merchant.name} - {self.amount_paise} paise - {self.status}"