import random
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import Payout
from ledger.models import Transaction

# Fix #3: explicit allowed transitions — anything not in this map is illegal
ALLOWED_TRANSITIONS = {
    'pending': {'processing'},
    'processing': {'completed', 'failed'},
}

def _transition(payout, new_status):
    """Apply a status transition. Raises ValueError if illegal."""
    allowed = ALLOWED_TRANSITIONS.get(payout.status, set())
    if new_status not in allowed:
        raise ValueError(
            f"Illegal transition: {payout.status} -> {new_status} on payout {payout.id}"
        )
    payout.status = new_status

def _fail_and_refund(payout, description):
    """Atomically move payout to failed and return funds. Must be called inside atomic()."""
    _transition(payout, 'failed')
    payout.save()
    Transaction.objects.create(
        merchant=payout.merchant,
        amount_paise=payout.amount_paise,
        type='credit',
        description=description
    )

@shared_task(bind=True, max_retries=3)
def process_payout(self, payout_id):
    try:
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)
            # Fix #3: only pending -> processing is legal here
            _transition(payout, 'processing')
            payout.attempt_count += 1
            payout.save()

        outcome = simulate_bank()

        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)

            if outcome == 'success':
                # Fix #3: processing -> completed is the only legal success path
                _transition(payout, 'completed')
                payout.save()

            elif outcome == 'failed':
                # Fix #3: processing -> failed + refund atomically
                _fail_and_refund(payout, 'Payout failed — funds returned')

            elif outcome == 'hang':
                raise self.retry(countdown=2 ** self.request.retries)

    except Payout.DoesNotExist:
        pass
    except ValueError:
        # Illegal transition attempted — log and stop, do not retry
        pass
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            with transaction.atomic():
                payout = Payout.objects.select_for_update().get(id=payout_id)
                if payout.status == 'processing':
                    _fail_and_refund(payout, 'Max retries exceeded — funds returned')
        else:
            raise

# Fix #5: periodic task — picks up payouts stuck in 'processing' for >30s
# Celery Beat runs this every 60s (configured in settings.CELERY_BEAT_SCHEDULE)
@shared_task
def retry_stuck_payouts():
    cutoff = timezone.now() - timedelta(seconds=30)

    # Payouts exhausted all attempts — fail and refund directly
    exhausted = Payout.objects.filter(
        status='processing',
        updated_at__lt=cutoff,
        attempt_count__gte=3
    )
    for payout in exhausted:
        with transaction.atomic():
            p = Payout.objects.select_for_update().get(id=payout.id)
            if p.status == 'processing':
                _fail_and_refund(p, 'Max retries exceeded — funds returned')

    # Payouts still have attempts left — reset to pending so process_payout
    # can legally transition pending → processing again
    stuck = Payout.objects.filter(
        status='processing',
        updated_at__lt=cutoff,
        attempt_count__lt=3
    )
    for payout in stuck:
        with transaction.atomic():
            p = Payout.objects.select_for_update().get(id=payout.id)
            if p.status == 'processing':
                p.status = 'pending'  # reset so process_payout can pick it up
                p.save()
        process_payout.delay(str(p.id))


def simulate_bank():
    r = random.random()
    if r < 0.70:
        return 'success'
    elif r < 0.90:
        return 'failed'
    else:
        return 'hang'