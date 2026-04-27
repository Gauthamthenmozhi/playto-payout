# Playto Payout Engine

Cross-border payout infrastructure for Indian merchants. Merchants accumulate balance from international customer payments and withdraw to their Indian bank account.

## Stack

- Backend: Django 5 + Django REST Framework
- Database: PostgreSQL (all amounts in paise as BigIntegerField)
- Background jobs: Celery + Redis
- Frontend: React 19

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL running locally
- Redis running locally

Or just use Docker (see below).

---

## Local Setup (without Docker)

### 1. Create and activate a virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

### 2. Install Python dependencies

```bash
pip install django djangorestframework celery redis django-cors-headers psycopg2-binary
```

### 3. Create the PostgreSQL database

```sql
CREATE DATABASE playto_db;
```

Default credentials in `settings.py`: user `postgres`, password `postgres123`, host `localhost`, port `5432`. Change them if needed.

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Seed test data (3 merchants with credit history)

```bash
python ledger/seed.py
```

### 6. Start the Django dev server

```bash
python manage.py runserver
```

### 7. Start the Celery worker (new terminal)

```bash
celery -A playto_payout worker -l info
```

### 8. Start Celery Beat for periodic tasks (new terminal)

Beat runs `retry_stuck_payouts` every 60 seconds to recover payouts stuck in `processing`.

```bash
celery -A playto_payout beat -l info
```

### 9. Start the React frontend (new terminal)

```bash
cd frontend
npm install
npm start
```

Frontend runs on http://localhost:3000 and proxies API calls to http://localhost:8000.

---

## Docker Setup

```bash
docker-compose up --build
```

This starts: PostgreSQL, Redis, Django (migrations + server), Celery worker, Celery Beat, React frontend.

Seed data is loaded automatically on first start.

Frontend: http://localhost:3000  
API: http://localhost:8000/api/v1/

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/merchants/` | List all merchants |
| GET | `/api/v1/merchants/<id>/` | Merchant detail with balance, held, payouts, transactions |
| POST | `/api/v1/payouts/` | Create payout (requires `Idempotency-Key` header) |
| POST | `/api/v1/credits/` | Simulate incoming customer payment |

### POST /api/v1/payouts/

Headers:
```
Idempotency-Key: <uuid>
Content-Type: application/json
```

Body:
```json
{
  "merchant_id": 1,
  "amount_paise": 100000,
  "bank_account_id": "ACC123456"
}
```

---

## Running Tests

```bash
python manage.py test payouts
```

Two tests:
- `IdempotencyTest` — same key returns same payout, only one record created
- `ConcurrencyTest` — two simultaneous ₹60 requests against ₹100 balance, exactly one succeeds

---

## Payout Lifecycle

```
pending → processing → completed
                    ↘ failed (funds returned atomically)
```

Payouts stuck in `processing` for more than 30 seconds are retried by Celery Beat (max 3 attempts, then failed + refund).

Bank simulation: 70% success, 20% fail, 10% hang (triggers retry).
