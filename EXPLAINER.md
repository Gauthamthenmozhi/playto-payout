# EXPLAINER.md

## 1. The Ledger

**Balance calculation query:**

```python
# payouts/views.py — inside PayoutCreateView.post(), inside atomic() with select_for_update
agg = Transaction.objects.filter(merchant=merchant).aggregate(
    credits=Sum('amount_paise', filter=Q(type='credit')),
    debits=Sum('amount_paise', filter=Q(type='debit'))
)
balance = (agg['credits'] or 0) - (agg['debits'] or 0)
```

This translates to a single SQL query:
```sql
SELECT
  SUM(amount_paise) FILTER (WHERE type = 'credit') AS credits,
  SUM(amount_paise) FILTER (WHERE type = 'debit')  AS debits
FROM ledger_transaction
WHERE merchant_id = %s;
```

**Why credits and debits this way:**

Every money movement is an immutable Transaction row — never updated, never deleted. Credits come in when a customer pays. Debits are written when a payout is requested (holding the funds). If a payout fails, a new credit row is written to return the funds. The balance at any point is `SUM(credits) - SUM(debits)` across all Transaction rows for that merchant.

This is an append-only ledger. There is no mutable "balance" column anywhere. That means:
- No update conflicts on a balance field
- Full audit trail of every money movement
- The invariant `credits - debits = displayed balance` is always true by construction — it is the definition of balance, not a derived check

Amounts are stored as `BigIntegerField` in paise (1 INR = 100 paise). No floats, no decimals. Integer arithmetic on integers is exact. ₹1000.50 is stored as 100050, never as 1000.5.

---

## 2. The Lock

**Exact code that prevents two concurrent payouts from overdrawing:**

```python
# payouts/views.py
with transaction.atomic():
    # Acquires a PostgreSQL row-level lock on this merchant row.
    # Any other transaction that tries SELECT FOR UPDATE on the same merchant
    # will block here until this atomic block commits or rolls back.
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)

    # Balance aggregate runs inside the same transaction that holds the lock.
    # No concurrent writer can insert a debit for this merchant until we commit.
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

    payout = Payout.objects.create(...)
```

**Database primitive:** PostgreSQL `SELECT FOR UPDATE`.

When two requests for the same merchant arrive simultaneously, both hit `select_for_update()`. PostgreSQL grants the lock to one and blocks the other at the database level — not in Python, not in Django, at the storage engine. The first transaction reads the balance, checks it, writes the debit, creates the payout, and commits. Only then does PostgreSQL release the lock and let the second transaction proceed. The second transaction now reads the updated balance (which already includes the first debit) and correctly rejects if funds are insufficient.

This is the only correct approach. A Python-level check (`if balance >= amount`) without a database lock is a classic TOCTOU (time-of-check-time-of-use) race condition.

---

## 3. The Idempotency

**How the system knows it has seen a key before:**

The `Payout` model has `unique_together = ['merchant', 'idempotency_key']`. This is a database-level unique constraint, not just an application-level check. The system has seen a key before if a row exists in the `payouts_payout` table with that `(merchant_id, idempotency_key)` pair and `created_at >= now() - 24h`.

Fast path (key already exists, no race):
```python
expiry_cutoff = timezone.now() - timedelta(hours=24)
existing = Payout.objects.filter(
    merchant_id=merchant_id,
    idempotency_key=idempotency_key,
    created_at__gte=expiry_cutoff
).first()
if existing:
    return Response(self.serialize(existing))  # exact same response
```

**What happens if the first request is in-flight when the second arrives:**

The fast-path lookup returns nothing (the first request hasn't committed yet). Both requests enter `atomic()`. One wins the `select_for_update` lock and creates the Payout row. The other, when it eventually gets the lock and tries `Payout.objects.create(...)`, hits the `unique_together` constraint and PostgreSQL raises an `IntegrityError`. We catch it:

```python
except IntegrityError:
    # The unique_together constraint fired — another request created this payout first.
    # Look it up and return the same response.
    existing = Payout.objects.filter(
        merchant_id=merchant_id,
        idempotency_key=idempotency_key,
        created_at__gte=expiry_cutoff
    ).first()
    if existing:
        return Response(self.serialize(existing))
    return Response({'error': 'Duplicate request'}, status=409)
```

The second request returns the exact same payout as the first. No duplicate is created. The database constraint is the final guard — application logic alone is not enough.

Keys are scoped per merchant: the unique constraint is on `(merchant, idempotency_key)`, not just `idempotency_key`. Merchant A and Merchant B can use the same UUID key without conflict.

Keys expire after 24 hours: both lookups filter by `created_at__gte=expiry_cutoff`. An expired key is treated as if it never existed, allowing a new payout to be created with the same key value.

---

## 4. The State Machine

**Legal transitions:**
```
pending → processing → completed
pending → processing → failed
```

**Illegal transitions (everything else): completed → pending, failed → completed, any backwards move.**

**Where illegal transitions are blocked — the `_transition` function in `payouts/tasks.py`:**

```python
ALLOWED_TRANSITIONS = {
    'pending': {'processing'},
    'processing': {'completed', 'failed'},
}

def _transition(payout, new_status):
    allowed = ALLOWED_TRANSITIONS.get(payout.status, set())
    if new_status not in allowed:
        raise ValueError(
            f"Illegal transition: {payout.status} -> {new_status} on payout {payout.id}"
        )
    payout.status = new_status
```

Every status write in the codebase goes through `_transition()`. There is no `payout.status = 'completed'` anywhere that bypasses this check. If `payout.status` is `'failed'` and something tries to move it to `'completed'`, `ALLOWED_TRANSITIONS.get('failed', set())` returns an empty set, `'completed' not in set()` is True, and `ValueError` is raised.

**Failed payout returning funds atomically with the state transition:**

```python
def _fail_and_refund(payout, description):
    # Must be called inside transaction.atomic() + select_for_update
    _transition(payout, 'failed')   # raises ValueError if illegal
    payout.save()
    Transaction.objects.create(
        merchant=payout.merchant,
        amount_paise=payout.amount_paise,
        type='credit',
        description=description
    )
```

The `payout.save()` and `Transaction.objects.create()` are in the same `atomic()` block. If either fails, both roll back. It is impossible for a payout to be marked failed without the refund credit being written, or for the refund credit to be written without the payout being marked failed.

---

## 5. The AI Audit

**What AI gave me (wrong):**

When I asked for the balance calculation, AI generated this:

```python
def get_balance(self):
    credits = self.transactions.filter(type='credit').aggregate(Sum('amount_paise'))['amount_paise__sum'] or 0
    debits = self.transactions.filter(type='debit').aggregate(Sum('amount_paise'))['amount_paise__sum'] or 0
    return credits - debits
```

And for the payout view, AI placed the idempotency check outside the atomic block:

```python
# AI's version — WRONG
existing = Payout.objects.filter(
    merchant_id=merchant_id,
    idempotency_key=idempotency_key
).first()
if existing:
    return Response(self.serialize(existing))

with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    balance = merchant.get_balance()  # called get_balance() outside the lock scope
    ...
```

**What was wrong:**

Two problems:

1. The idempotency check was outside `atomic()`. Two simultaneous requests with the same key both pass the `if existing` check before either commits. Both proceed to create a Payout. The `unique_together` constraint would catch one of them, but AI's code had no `IntegrityError` handler — it would have returned a 500 to the second caller instead of the correct idempotent response.

2. `merchant.get_balance()` was called after acquiring the `select_for_update` lock on Merchant, but `get_balance()` runs two separate queries on the Transaction table. Those Transaction rows are not locked. A concurrent transaction could insert a new debit row between the two aggregate queries inside `get_balance()`, or between the balance read and the debit write. The lock on the Merchant row does not prevent inserts into the Transaction table by other transactions.

**What I replaced it with:**

Moved the idempotency check to a fast-path before the atomic block (for the common case), then moved the Payout creation inside `atomic()` so the `unique_together` constraint fires on race, and added an `IntegrityError` handler that returns the correct idempotent response.

Replaced `merchant.get_balance()` with a single aggregate query that runs inside the same `atomic()` block that holds the Merchant lock:

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    agg = Transaction.objects.filter(merchant=merchant).aggregate(
        credits=Sum('amount_paise', filter=Q(type='credit')),
        debits=Sum('amount_paise', filter=Q(type='debit'))
    )
    balance = (agg['credits'] or 0) - (agg['debits'] or 0)
```

The lock on Merchant serializes all writers. The aggregate runs inside the locked transaction, so no concurrent debit can be inserted between the balance read and our debit write. One query instead of two, and it is safe.
