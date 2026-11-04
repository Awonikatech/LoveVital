#!/bin/sh
set -e
# Wait for the database, apply migrations, optionally seed demo data, then start the API.
echo "Waiting for database..."
python - <<'PY'
import time, sys
from sqlalchemy import create_engine, text
from app.core.config import settings
for i in range(60):
    try:
        with create_engine(settings.DATABASE_URL).connect() as c:
            c.execute(text("SELECT 1"))
        sys.exit(0)
    except Exception as e:
        print(f"  database not ready ({e.__class__.__name__}), retrying...", flush=True)
        time.sleep(2)
sys.exit("Database never became ready")
PY
echo "Applying migrations..."
alembic upgrade head
if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  echo "Seeding demo data (idempotent)..."
  python -m scripts.seed
fi
exec "$@"
