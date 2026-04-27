#!/bin/bash
python manage.py migrate
python ledger/seed.py

# Start Celery worker in background
celery -A playto_payout worker -l info &

# Start Celery beat in background
celery -A playto_payout beat -l info &

# Start Django (foreground)
gunicorn playto_payout.wsgi:application --bind 0.0.0.0:$PORT
