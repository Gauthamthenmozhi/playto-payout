from django.db import transaction, IntegrityError
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from ledger.models import Merchant, Transaction
from .models import Payout

class PayoutCreateView(APIView):
    def post(self, request):
        idempotency_key = request.headers.get('Idempotency-Key')
        if not idempotency_key:
            return Response({'error': 'Idempotency-Key header required'}, status=400)

        merchant_id = request.data.get('merchant_id')
        amount_paise = request.data.get('amount_paise')
        bank_account_id = request.data.get('bank_account_id')

        if not all([merchant_id, amount_paise, bank_account_id]):
            return Response({'error': 'merchant_id, amount_paise, bank_account_id required'}, status=400)

        # Fix #4: 24h expiry on idempotency key lookup
        expiry_cutoff = timezone.now() - timedelta(hours=24)

        # Fix #1: early return for existing non-expired key (fast path, no lock needed)
        existing = Payout.objects.filter(
            merchant_id=merchant_id,
            idempotency_key=idempotency_key,
            created_at__gte=expiry_cutoff
        ).first()
        if existing:
            return Response(self.serialize(existing))

        payout = None
        try:
            with transaction.atomic():
                # Fix #2: lock the Merchant row — all balance reads inside this block
                # are serialized. No other transaction can insert a debit for this
                # merchant until this atomic block commits.
                merchant = Merchant.objects.select_for_update().get(id=merchant_id)

                # Fix #2: compute balance inside the lock using a single DB aggregate.
                # select_for_update() on Merchant serializes all writers for this merchant.
                # The aggregate runs inside the same transaction, so no concurrent debit
                # can be inserted between the balance read and our debit write.
                agg = Transaction.objects.filter(merchant=merchant).aggregate(
                    credits=Sum('amount_paise', filter=Q(type='credit')),
                    debits=Sum('amount_paise', filter=Q(type='debit'))
                )
                balance = (agg['credits'] or 0) - (agg['debits'] or 0)

                if balance < int(amount_paise):
                    return Response({'error': 'Insufficient balance'}, status=400)

                Transaction.objects.create(
                    merchant=merchant,
                    amount_paise=int(amount_paise),
                    type='debit',
                    description='Payout hold'
                )

                # Fix #1: create inside atomic — unique_together on (merchant, idempotency_key)
                # makes a duplicate raise IntegrityError, which we catch below.
                payout = Payout.objects.create(
                    merchant=merchant,
                    amount_paise=int(amount_paise),
                    bank_account_id=bank_account_id,
                    idempotency_key=idempotency_key,
                    status='pending'
                )

        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=404)
        except IntegrityError:
            # Fix #1: second concurrent request with same key lost the race —
            # the unique_together constraint fired. Return the winner's payout.
            existing = Payout.objects.filter(
                merchant_id=merchant_id,
                idempotency_key=idempotency_key,
                created_at__gte=expiry_cutoff
            ).first()
            if existing:
                return Response(self.serialize(existing))
            return Response({'error': 'Duplicate request'}, status=409)

        from .tasks import process_payout
        process_payout.delay(str(payout.id))

        return Response(self.serialize(payout), status=201)

    def serialize(self, payout):
        return {
            'id': str(payout.id),
            'merchant_id': payout.merchant_id,
            'amount_paise': payout.amount_paise,
            'status': payout.status,
            'created_at': payout.created_at,
        }

class MerchantListView(APIView):
    def get(self, request):
        merchants = Merchant.objects.all().order_by('id')
        return Response([
            {'id': m.id, 'name': m.name, 'email': m.email}
            for m in merchants
        ])


class MerchantDetailView(APIView):
    def get(self, request, merchant_id):
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=404)

        # Fix #6: held_paise = sum of pending payout amounts (funds locked, not yet settled)
        held = Payout.objects.filter(
            merchant=merchant, status__in=['pending', 'processing']
        ).aggregate(total=Sum('amount_paise'))['total'] or 0

        payouts = Payout.objects.filter(merchant=merchant).order_by('-created_at')[:10]
        transactions = merchant.transactions.order_by('-created_at')[:10]

        return Response({
            'id': merchant.id,
            'name': merchant.name,
            'email': merchant.email,
            'balance_paise': merchant.get_balance(),
            'held_paise': held,
            'payouts': [self.serialize_payout(p) for p in payouts],
            'transactions': [self.serialize_tx(t) for t in transactions],
        })

    def serialize_payout(self, p):
        return {
            'id': str(p.id),
            'amount_paise': p.amount_paise,
            'status': p.status,
            'created_at': p.created_at,
        }

    def serialize_tx(self, t):
        return {
            'amount_paise': t.amount_paise,
            'type': t.type,
            'description': t.description,
            'created_at': t.created_at,
        }

class CreditAddView(APIView):

    def post(self, request):
        merchant_id = request.data.get('merchant_id')
        amount_paise = request.data.get('amount_paise')
        description = request.data.get('description', 'Customer payment')

        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response({'error': 'Merchant not found'}, status=404)

        Transaction.objects.create(
            merchant=merchant,
            amount_paise=int(amount_paise),
            type='credit',
            description=description
        )

        return Response({
            'message': 'Credit added',
            'new_balance_paise': merchant.get_balance()
        })