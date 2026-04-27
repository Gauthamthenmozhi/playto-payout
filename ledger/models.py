from django.db import models
from django.db.models import Sum

class Merchant(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_balance(self):
        credits = self.transactions.filter(
            type='credit'
        ).aggregate(Sum('amount_paise'))['amount_paise__sum'] or 0

        debits = self.transactions.filter(
            type='debit'
        ).aggregate(Sum('amount_paise'))['amount_paise__sum'] or 0

        return credits - debits

    def __str__(self):
        return self.name

class Transaction(models.Model):
    TYPES = [('credit', 'Credit'), ('debit', 'Debit')]

    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.PROTECT,
        related_name='transactions'
    )
    amount_paise = models.BigIntegerField()
    type = models.CharField(max_length=10, choices=TYPES)
    description = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type} - {self.amount_paise} paise"