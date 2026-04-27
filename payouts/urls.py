from django.urls import path
from .views import PayoutCreateView, MerchantDetailView, MerchantListView, CreditAddView

urlpatterns = [
    path('payouts/', PayoutCreateView.as_view(), name='payout-create'),
    path('merchants/', MerchantListView.as_view(), name='merchant-list'),
    path('merchants/<int:merchant_id>/', MerchantDetailView.as_view(), name='merchant-detail'),
    path('credits/', CreditAddView.as_view(), name='credit-add'),
]