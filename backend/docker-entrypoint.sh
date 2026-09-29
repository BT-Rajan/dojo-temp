#!/bin/sh
# Local trial: wait for MySQL, build the tables, load the fictional test data once, then start the site.
set -e

echo "Waiting for the database..."
until nc -z db 3306; do sleep 2; done

python manage.py migrate --noinput

if [ ! -f /app/media/.seeded ]; then
    echo "Loading the fictional Kuwait test data (first start only, takes a minute)..."
    python manage.py seed_kuwait
    python manage.py seed_website
    python manage.py run_daily_jobs || true
    mkdir -p /app/media && touch /app/media/.seeded
fi

echo ""
echo "Elite Academy is running:"
echo "  Website     http://localhost:8000/en/   (Arabic: /ar/)"
echo "  Staff desk  http://localhost:8000/en/desk/"
echo "  Test logins ceo@test.elite.local, ops@test.elite.local, admin.prm@test.elite.local ..."
echo "  Password    Elite-Test-2026!"
echo "  Parent portal: http://localhost:8000/en/portal/ with the test parent's mobile below; the WhatsApp code"
echo "  appears in this window (no real messages are sent)."
python manage.py shell -c "from apps.members.models import Guardian; g = Guardian.objects.filter(user__email='parent@test.elite.local').first(); print('  Test parent mobile:', g.mobile if g else '-')" || true
echo ""
exec python manage.py runserver 0.0.0.0:8000
