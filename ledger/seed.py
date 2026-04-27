import os
import sys
import django

# Ensure project root is on sys.path so playto_payout settings can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'playto_payout.settings')
django.setup()

from ledger.models import Merchant, Transaction

# பழைய data delete பண்ணு
Transaction.objects.all().delete()
Merchant.objects.all().delete()

# Merchants create பண்ணு
m1 = Merchant.objects.create(
    name='Ravi Designs',
    email='ravi@designs.com'
)

m2 = Merchant.objects.create(
    name='Priya Freelancer',
    email='priya@freelancer.com'
)

m3 = Merchant.objects.create(
    name='Kumar Agency',
    email='kumar@agency.com'
)

# Credits add பண்ணு (customer payments simulate பண்றோம்)
Transaction.objects.create(
    merchant=m1,
    amount_paise=500000,  # ₹5000
    type='credit',
    description='Payment from US client - Invoice #001'
)
Transaction.objects.create(
    merchant=m1,
    amount_paise=300000,  # ₹3000
    type='credit',
    description='Payment from UK client - Invoice #002'
)

Transaction.objects.create(
    merchant=m2,
    amount_paise=150000,  # ₹1500
    type='credit',
    description='Freelance project payment'
)
Transaction.objects.create(
    merchant=m2,
    amount_paise=200000,  # ₹2000
    type='credit',
    description='Monthly retainer payment'
)

Transaction.objects.create(
    merchant=m3,
    amount_paise=1000000,  # ₹10000
    type='credit',
    description='Agency project milestone payment'
)

print("Seed data created successfully!")
print(f"Ravi Designs balance: ₹{m1.get_balance()/100}")
print(f"Priya Freelancer balance: ₹{m2.get_balance()/100}")
print(f"Kumar Agency balance: ₹{m3.get_balance()/100}")