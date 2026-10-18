# LoveVital — Jewellery & Apparel E-commerce Platform

A production-oriented, full-stack store for artificial jewellery and women's apparel: a gold-and-ivory React storefront,
a role-based admin control panel, a FastAPI REST API, MySQL 8, and Razorpay payments (with a signature-compatible
local simulator so everything runs without credentials).

| | |
|---|---|
| **Frontend** | React 18 + TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, React Hook Form + Zod, Recharts |
| **Backend** | Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, Argon2id, JWT + rotating refresh cookies |
| **Database** | MySQL 8 (MariaDB 10.11 also verified) — 46 tables, DECIMAL money, row locks for stock |
| **Payments** | Razorpay (official SDK) in `mock`, `test` or `live` mode; verified signatures & idempotent webhooks |
| **Tests** | 210 pytest tests (incl. a real MySQL concurrency test), 23 Vitest component tests, 6 Playwright E2E tests |

---

## Quick start (Docker)

```bash
cp .env.example .env            # safe dev defaults; RAZORPAY_MODE=mock needs no keys
docker compose up --build
```

Open **http://localhost:8080** · API docs **http://localhost:8080/api/docs** · Admin **http://localhost:8080/admin**

The backend container waits for MySQL, runs `alembic upgrade head`, and (with `SEED_DEMO_DATA=true`) seeds demo data.

### Demo accounts (development only — defined in `.env`)

| Role | Email | Password | Can do |
|---|---|---|---|
| Admin | `admin@lovevital.example.com` | `Admin@12345` | Everything, incl. cost prices, finance reports, refunds, settings, audit log |
| Staff | `staff@lovevital.example.com` | `Staff@12345` | Orders, shipping, inventory, products, returns, content — no finance/cost data, no refunds |
| Customer | `priya@example.com` | `Customer@123` | Shopping, saved addresses, order history, returns, reviews |

The seed refuses to run when `ENVIRONMENT=production`.

---

## Local development (without Docker)

**Prerequisites:** Python 3.12+, Node 20+, MySQL 8 (or MariaDB 10.11+).

```bash
# 1. Database
mysql -u root -p -e "CREATE DATABASE swarnika CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  CREATE USER 'swarnika'@'%' IDENTIFIED BY 'swarnika_dev_pw'; GRANT ALL ON swarnika.* TO 'swarnika'@'%';"

# 2. API
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env                 # DATABASE_URL points at 127.0.0.1:3306/swarnika
alembic upgrade head                       # create schema
python -m scripts.seed                     # demo data (safe to re-run; never duplicates)
uvicorn app.main:app --reload --port 8000  # http://localhost:8000/api/docs

# 3. Storefront + admin
cd ../frontend
npm install
npm run dev                                # http://localhost:5173 (proxies /api, /static, /media to :8000)
```

Useful commands:

| Task | Command |
|---|---|
| New migration after model changes | `cd backend && alembic revision --autogenerate -m "describe change"` |
| Apply / roll back migrations | `alembic upgrade head` · `alembic downgrade -1` |
| Re-seed (idempotent) | `python -m scripts.seed` (`--no-orders` to skip sample orders) |
| Regenerate product imagery | `python -m scripts.generate_images` |
| Release expired stock holds now | `POST /api/v1/admin/inventory/sweep-reservations` (also runs every 60 s in-process) |
| Production frontend build | `cd frontend && npm run build` → `dist/` |

---

## Testing

```bash
# Backend — unit + API integration (in-memory SQLite, mock Razorpay, no network)
cd backend && ENVIRONMENT=test python -m pytest -q

# Include the real-database concurrency test (12 threads racing for 5 units → exactly 5 succeed)
mysql -e "CREATE DATABASE swarnika_test"
TEST_MYSQL_URL="mysql+pymysql://swarnika:swarnika_dev_pw@127.0.0.1:3306/swarnika_test?charset=utf8mb4" \
  ENVIRONMENT=test python -m pytest -q app/tests/test_inventory.py

# Frontend — component & form tests
cd frontend && npm test

# End-to-end (needs the API on :8000 with seed data, RAZORPAY_MODE=mock, RATE_LIMIT_ENABLED=false)
npx playwright install chromium   # once
npm run e2e                       # starts Vite automatically; E2E_BASE_URL=... to target another host
```

Covered: pricing engine (MRP/sale/scheduled prices, BOGO, quantity offers, coupon caps, stacking rules, GST),
auth (Argon2, refresh rotation & reuse detection, CSRF, reset tokens), RBAC, catalog search/filters, cart & checkout,
idempotent checkout, inventory reservation/expiry/concurrency, Razorpay verify + webhooks (duplicates, bad signatures,
amount mismatch, late & double payments), cancellations, returns, refunds, admin CRUD, CSV import/export, uploads,
rate limiting, and full browser journeys on desktop and mobile.

---

## Razorpay

| Mode | Use for | Keys |
|---|---|---|
| `mock` (default) | Local dev, CI, demos | none — a built-in simulator issues real HMAC signatures, so the server's verification path is identical |
| `test` | Sandbox testing with Razorpay's checkout | Test keys from the Razorpay Dashboard (Test Mode) |
| `live` | Production | Live keys, HTTPS, webhook configured |

**Sandbox workflow (test mode)**
1. Dashboard → *Test Mode* → *Settings → API Keys* → generate keys. Set `RAZORPAY_MODE=test`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`.
2. *Settings → Webhooks* → add `https://<your-host>/api/v1/payments/razorpay/webhook` with a secret (`RAZORPAY_WEBHOOK_SECRET`) and the events
   `payment.captured`, `payment.failed`, `order.paid`, `refund.processed`, `refund.failed`. For local testing expose port 8080 with a tunnel (e.g. `cloudflared`, `ngrok`).
3. Restart the API, place an order and pay with Razorpay's test UPI ID / test cards from their docs.

Security guarantees: the key secret never reaches the browser; amounts are computed server-side; an order becomes paid only after
signature verification (and, in test/live, a server-side fetch confirming `captured` and the exact amount); webhooks are signature-checked
and de-duplicated by event id; refunds carry idempotency keys. Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#payments).

---

## Project structure

```
ecommerce-platform/
├── backend/
│   ├── app/
│   │   ├── api/v1/            # route handlers (thin) — auth, catalog, cart/checkout, orders/payments, account, admin/*
│   │   ├── core/              # config, database, security, errors, deps (RBAC), rate limit, money, logging
│   │   ├── models/            # SQLAlchemy models (46 tables)
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── services/          # business logic: pricing, cart, order state machine, inventory, payments, reports…
│   │   ├── integrations/      # Razorpay gateway (+ mock), email backends, shipping provider adapter (mock courier)
│   │   ├── repositories/      # (queries live in services; folder kept for future extraction)
│   │   ├── tasks/             # background jobs (reservation sweeper runs from app lifespan)
│   │   └── tests/             # pytest suite
│   ├── alembic/               # migrations
│   ├── scripts/               # seed.py, seed_catalog.py, generate_images.py
│   └── static/                # generated product imagery, category tiles, banners (SVG)
├── frontend/
│   ├── src/{components,pages,layouts,features,hooks,services,types,utils,test}
│   ├── e2e/                   # Playwright specs
│   └── nginx.conf             # production server + reverse proxy
├── database/seed_data/        # seed catalogue exported as JSON (reference)
├── docs/                      # architecture, API, deployment & operations
├── docker-compose.yml
└── .env.example
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — architecture, database relationships (ER diagram), pricing rules, order state machine, inventory & payments design
- [docs/API.md](docs/API.md) — endpoint reference & conventions (full interactive docs at `/api/docs`)
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — production build, HTTPS & reverse proxy, Razorpay live mode, backups/restore, troubleshooting

## Troubleshooting (quick)

| Symptom | Fix |
|---|---|
| `Refusing to start in production with insecure settings` | Set a real `SECRET_KEY`, `COOKIE_SECURE=true`, and `RAZORPAY_MODE=test/live` |
| Logged out on every refresh in production | Serve SPA and API from the same origin over HTTPS (`COOKIE_SECURE=true` requires HTTPS) |
| "Too many attempts" when logging in repeatedly | Login is rate-limited (10 per 5 min per IP). Wait, or set `RATE_LIMIT_ENABLED=false` for automated local testing only |
| Emails don't arrive | `EMAIL_BACKEND=console` prints them to the API log; configure `smtp` for real delivery |
| ₹ shows as "Rs." in PDF invoices | Install DejaVu fonts (`fonts-dejavu-core`); the Docker image includes them |

More in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#troubleshooting).

## Screenshots

| Storefront | Product | Checkout |
|---|---|---|
| ![Home](docs/screenshots/storefront-home.jpg) | ![Product](docs/screenshots/product-page.jpg) | ![Checkout](docs/screenshots/checkout.jpg) |
| **Payment (mock Razorpay)** | **Order tracking & refund** | **Admin dashboard** |
| ![Razorpay](docs/screenshots/razorpay-test-checkout.jpg) | ![Order](docs/screenshots/order-detail.jpg) | ![Admin](docs/screenshots/admin-dashboard.jpg) |
