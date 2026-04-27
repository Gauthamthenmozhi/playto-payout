#!/bin/bash

# Build React frontend if npm is available
if command -v npm &> /dev/null; then
    echo "Building React frontend..."
    cd frontend
    npm install --legacy-peer-deps
    npm run build
    cd ..
    echo "React build complete."
else
    echo "npm not found, skipping React build."
fi

# Django setup
python manage.py migrate
python manage.py collectstatic --noinput
python ledger/seed.py

# Start Celery worker in background
celery -A playto_payout worker -l info --pool=solo &

# Start Celery beat in background
celery -A playto_payout beat -l info &

# Start Django (foreground)
gunicorn playto_payout.wsgi:application --bind 0.0.0.0:$PORT
