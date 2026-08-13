#!/usr/bin/env bash
set -euo pipefail

APP_ROLE="${APP_ROLE:-web}"

if [[ -z "${OPENAI_API_KEY:-}" && -f "/run/secrets/openai_api_key" ]]; then
  export OPENAI_API_KEY="$(cat /run/secrets/openai_api_key)"
fi

python manage.py safe_migrate

if [[ "${DJANGO_SUPERUSER_USERNAME:-}" != "" ]]; then
  python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
username = '${DJANGO_SUPERUSER_USERNAME}'
email = '${DJANGO_SUPERUSER_EMAIL:-admin@example.com}'
password = '${DJANGO_SUPERUSER_PASSWORD:-adminpass}'
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
"
fi

if [[ "$APP_ROLE" == "worker" ]]; then
  exec celery -A forth worker -l info -Q "${CELERY_WORKER_QUEUES:-celery}" --concurrency="${CELERY_WORKER_CONCURRENCY:-2}"
elif [[ "$APP_ROLE" == "beat" ]]; then
  exec celery -A forth beat -l info
else
  exec daphne -b 0.0.0.0 -p 8000 forth.asgi:application
fi
