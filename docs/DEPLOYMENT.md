# Deployment & operations

## Production checklist

| Setting | Value |
|---|---|
| `ENVIRONMENT` | `production` (start-up refuses the dev secret, insecure cookies or mock payments) |
| `SECRET_KEY` | 48+ random bytes: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `COOKIE_SECURE` | `true` (HTTPS only) |
| `FRONTEND_URL` / `CORS_ORIGINS` | your public origin, e.g. `https://shop.example.com` |
| `RAZORPAY_MODE` | `live` with live keys + webhook secret |
| `EMAIL_BACKEND` | `smtp` with your provider's credentials |
| `SEED_DEMO_DATA` | `false` |
| Database | managed MySQL 8 (utf8mb4), automated backups, least-privilege user |

## Build & run

```bash
docker compose build
docker compose up -d
docker compose logs -f backend
```

Without Docker: `pip install -r backend/requirements.txt`, `alembic upgrade head`, run
`uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers` under systemd/supervisor, and serve
`frontend/dist` (from `npm run build`) with the provided `frontend/nginx.conf` + `security-headers.conf`.

Migrations run automatically at container start (`docker-entrypoint.sh`). For zero-downtime releases run
`docker compose run --rm backend alembic upgrade head` before switching traffic, and keep migrations backward compatible.

## HTTPS & reverse proxy

The SPA and API must share one origin (cookies are `SameSite` and `HttpOnly`). The frontend container already proxies
`/api`, `/static` and `/media` to the API. Terminate TLS in front of it, for example with Caddy:

```
shop.example.com {
  encode gzip
  reverse_proxy frontend:80
}
```

or nginx on the host:

```nginx
server {
  listen 443 ssl http2;
  server_name shop.example.com;
  ssl_certificate     /etc/letsencrypt/live/shop.example.com/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/shop.example.com/privkey.pem;
  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
  location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
  }
}
server { listen 80; server_name shop.example.com; return 301 https://$host$request_uri; }
```

The API trusts `X-Forwarded-For` for rate limiting and audit IPs — only expose it behind your proxy.

**Scaling out:** the rate limiter is in-process; for multiple API hosts move it to Redis (same `rate_limit()` dependency interface).
The reservation sweeper is safe to run on every instance (row locks). Store uploads on shared storage (S3 or a shared volume) and serve `/media` from it.

## Razorpay live mode

1. Complete KYC and activate the account; switch the dashboard to **Live Mode** and generate live keys.
2. Set `RAZORPAY_MODE=live`, `RAZORPAY_KEY_ID=rzp_live_…`, `RAZORPAY_KEY_SECRET=…`.
3. Webhooks → `https://shop.example.com/api/v1/payments/razorpay/webhook`, secret → `RAZORPAY_WEBHOOK_SECRET`, events:
   `payment.captured`, `payment.failed`, `order.paid`, `refund.processed`, `refund.failed`.
4. Payment methods (UPI, cards, net banking, wallets, EMI) are whatever you enable in the Razorpay dashboard — no code change.
5. Do a ₹1 live payment and refund before launch; check **Admin → Orders → Payments & refunds** and `payment_events` for both the verify and webhook rows.

Test mode is identical with `rzp_test_…` keys. Verification fetches the payment from Razorpay to confirm `captured` and the exact amount before marking an order paid.

## Backups & restore

```bash
# Backup (consistent, no table locks for InnoDB)
docker compose exec mysql sh -c 'mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers "$MYSQL_DATABASE"' \
  | gzip > backup-$(date +%F).sql.gz

# Restore into a fresh database
gunzip -c backup-2026-10-18.sql.gz | docker compose exec -T mysql sh -c 'mysql -u root -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'

# Uploaded images
docker run --rm -v ecommerce-platform_media:/data -v "$PWD":/backup alpine tar czf /backup/media-$(date +%F).tgz -C /data .
```

Schedule the dump daily (cron/systemd timer), keep 30 days, copy off-host, and test a restore monthly. After restoring, run
`alembic upgrade head` to bring the schema up to date.

## Monitoring

- Liveness `GET /health`, readiness `GET /health/ready` (checks the DB). Containers have HEALTHCHECKs.
- Logs are structured one-line text with secrets redacted; ship them to your log stack.
- Watch: 5xx rate, `payment_events.processing_result = 'error'`, refunds stuck in `pending`, low-stock queue, and the API log line
  `Released N expired inventory reservation(s)`.

## Troubleshooting

| Problem | Likely cause / fix |
|---|---|
| API exits with "Refusing to start in production…" | Production guard: set a real `SECRET_KEY`, `COOKIE_SECURE=true`, non-mock `RAZORPAY_MODE`. |
| `Can't connect to MySQL server` at start | DB not ready/wrong `DATABASE_URL`. The entrypoint retries for 2 minutes; check credentials and network. |
| `Incorrect string value` / garbled ₹ | Database or connection isn't utf8mb4. Create the DB with `utf8mb4_unicode_ci`; keep `?charset=utf8mb4` in the URL. |
| Users get logged out on refresh | Different origins for SPA and API, or `COOKIE_SECURE=true` over plain HTTP. |
| `CSRF validation failed` on refresh | A proxy is stripping the `X-CSRF-Token` header or cookies. |
| Payment succeeded but order still "Payment pending" | Check webhooks are reaching the API (Razorpay dashboard → Webhooks → deliveries) and the webhook secret matches. Verify is retried from the result page automatically. |
| `Invalid webhook signature` | `RAZORPAY_WEBHOOK_SECRET` differs from the dashboard secret, or a proxy is modifying the raw body. |
| "Not enough stock" while shelves show stock | Stock is held by pending payments. Admin → Inventory → Reservations; holds release after 15 min (or "Release expired holds"). |
| Emails missing | `EMAIL_BACKEND=console` prints to logs; for SMTP check `notifications` table for `failed` rows and the error column. |
| Images upload fails | Only JPEG/PNG/WebP/GIF up to `MAX_UPLOAD_MB`; nginx `client_max_body_size` is 6 MB. |
| Alembic "Target database is not up to date" | Run `alembic upgrade head`; never edit applied migration files. |
