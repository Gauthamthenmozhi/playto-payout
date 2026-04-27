import uuid
import threading
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from ledger.models import Merchant, Transaction
from payouts.models import Payout


class IdempotencyTest(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Test Merchant",
            email="test@merchant.com"
        )
        Transaction.objects.create(
            merchant=self.merchant,
            amount_paise=1000000,
            type='credit',
            description='Test credit'
        )

    def test_same_key_returns_same_response(self):
        key = str(uuid.uuid4())
        
        response1 = self.client.post(
            '/api/v1/payouts/',
            {
                'merchant_id': self.merchant.id,
                'amount_paise': 100000,
                'bank_account_id': 'ACC123',
            },
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=key
        )

        response2 = self.client.post(
            '/api/v1/payouts/',
            {
                'merchant_id': self.merchant.id,
                'amount_paise': 100000,
                'bank_account_id': 'ACC123',
            },
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=key
        )

        # Same payout ID return ஆகணும்
        self.assertEqual(response1.json()['id'], response2.json()['id'])
        # Only one payout created ஆகணும்
        self.assertEqual(Payout.objects.count(), 1)
        print("✅ Idempotency test passed!")


class ConcurrencyTest(TransactionTestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Test Merchant 2",
            email="test2@merchant.com"
        )
        Transaction.objects.create(
            merchant=self.merchant,
            amount_paise=10000,  # ₹100
            type='credit',
            description='Test credit'
        )

    def test_concurrent_payouts(self):
        results = []

        def make_payout():
            response = self.client.post(
                '/api/v1/payouts/',
                {
                    'merchant_id': self.merchant.id,
                    'amount_paise': 6000,  # ₹60
                    'bank_account_id': 'ACC123',
                },
                content_type='application/json',
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
            )
            results.append(response.status_code)

        # 2 simultaneous requests
        t1 = threading.Thread(target=make_payout)
        t2 = threading.Thread(target=make_payout)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # One success, one fail
        self.assertIn(201, results)
        self.assertIn(400, results)
        print("✅ Concurrency test passed!")