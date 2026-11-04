# API reference

Interactive documentation (Swagger UI) is served at **`/api/docs`**, ReDoc at `/api/redoc`, and the OpenAPI schema at `/api/openapi.json`.
This page summarises conventions and the main endpoints (105 in total).

## Conventions

- Base path: `/api/v1`. JSON in and out. Money values are decimal **strings** in INR, tax-inclusive (`"499.00"`).
- Auth: `Authorization: Bearer <access_token>` (15-minute JWT from login/register/refresh). Refresh uses the HttpOnly `swk_refresh`
  cookie plus `X-CSRF-Token` = value of the `swk_csrf` cookie.
- Guest carts: send `X-Cart-Token` (returned in every cart response). On login/register the guest cart merges into the user's cart.
- Idempotent checkout: send `Idempotency-Key: <uuid>`; repeating the request returns the same order (`"created": false`).
- Pagination: `?page=1&page_size=24` → `{ items, total, page, page_size, pages }`.
- Errors: `{"error": {"code": "insufficient_stock", "message": "Only 2 left in stock", "details": …}}` with 400/401/403/404/409/422/429/402.

## Auth

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | `{full_name, email, password, phone?}` → tokens; sends verification email |
| POST | `/auth/login` | rate-limited (10 / 5 min / IP) |
| POST | `/auth/refresh` | cookie + CSRF header; rotates refresh token |
| POST | `/auth/logout` | revokes the session family |
| POST | `/auth/forgot-password` · `/auth/reset-password` | single-use 1-hour token |
| POST | `/auth/verify-email` · `/auth/resend-verification` | |
| GET/PATCH | `/auth/me` · POST `/auth/change-password` | |

## Catalogue & content

| Method | Path | Notes |
|---|---|---|
| GET | `/products` | `q, category, collection, product_type, brand, min_price, max_price, in_stock, min_rating, min_discount, on_sale, featured, bestseller, new_arrival, color, size, material, plating, stone, style, fabric, fit, occasion, sort=popularity|newest|price_asc|price_desc|rating|discount, page, page_size` → items + facets + `did_you_mean` |
| GET | `/products/{slug}` | variants (SKU, price, stock), options, images, specs, size chart, related, frequently bought together |
| GET/POST | `/products/{slug}/reviews` | |
| GET | `/search/suggest?q=` | typeahead (synonym & typo tolerant) |
| GET | `/categories` · `/collections` · `/home` · `/banners` · `/pages/{slug}` · `/settings/public` | |
| GET | `/delivery/estimate?pin=&product_slug=` | serviceability, COD, per-method dates & charges |
| POST | `/newsletter` | |

## Cart, checkout, orders, payments

| Method | Path | Notes |
|---|---|---|
| GET | `/cart` | |
| POST | `/cart/items` | `{variant_id, quantity}` — stock, min/max validated |
| PATCH/DELETE | `/cart/items/{item_id}` | |
| POST/DELETE | `/cart/coupon` | |
| POST | `/checkout/validate` | server quote: totals, delivery options, COD eligibility, cart issues |
| POST | `/checkout` | creates order, reserves stock; COD orders are placed immediately |
| GET | `/orders` · `/orders/{id or number}` | guests use `?key=<order_key>` |
| POST | `/orders/lookup` | guest lookup by order number + email |
| POST | `/orders/{ref}/cancel` | per policy; packed orders become a request |
| POST | `/orders/{ref}/returns` · GET `/returns` | within the return window |
| GET | `/orders/{ref}/invoice` | GST invoice PDF |
| GET | `/track/{awb}` | public tracking |
| POST | `/payments/razorpay/create-order` | `{order_id, order_key?}` |
| POST | `/payments/razorpay/verify` | `{razorpay_order_id, razorpay_payment_id, razorpay_signature}` |
| POST | `/payments/razorpay/failed` | client-reported failure, confirmed with the gateway |
| POST | `/payments/razorpay/webhook` | `X-Razorpay-Signature`, `X-Razorpay-Event-Id` |
| GET | `/payments/status/{ref}` | for the pending screen |
| POST | `/payments/razorpay/mock-checkout` | **mock mode only** |

## Account

`/account/addresses` (CRUD) · `/account/wishlist` (GET/POST, DELETE `/{product_id}`) · `/account/reviews`

## Admin (`/admin/*`, staff or admin; permissions per endpoint)

| Area | Endpoints |
|---|---|
| Dashboard & reports | `GET /dashboard?start&end`, `GET /reports/{sales|order_status|products|categories|inventory|coupons|customers|refunds}?start&end&granularity&format=csv` |
| Products | `GET/POST /products`, `GET/PUT/PATCH/DELETE /products/{id}` (delete archives if ordered), `GET /products/meta`, images: `POST /products/{id}/images` (multipart), `POST …/images/url`, `PATCH/DELETE …/images/{image_id}`; `GET /products-export.csv`, `POST /products-import?dry_run=` |
| Catalogue | `/categories`, `/collections`, `/attributes`, `/attributes/{id}/values`, `/tax-rates`, `POST /uploads/image` |
| Inventory | `GET /inventory`, `POST /inventory/adjust`, `GET /inventory/movements`, `GET /inventory/reservations`, `POST /inventory/sweep-reservations` |
| Orders | `GET /orders` (filters + `status_counts`), `GET /orders-export.csv`, `GET /orders/{id}`, `POST /orders/{id}/status`, `/cancel`, `/cancellation-request`, `/notes`, `/shipments`, `/refunds`, `GET /orders/{id}/invoice`, `/packing-slip`, `POST /shipments/{id}/status` |
| Returns | `GET /returns`, `POST /returns/{id}` `{action: approve|reject|receive}` |
| Customers | `GET /customers`, `GET/PATCH /customers/{id}` |
| Coupons & promotions | `/coupons` CRUD, `/coupons/{id}/redemptions`, `/promotions` CRUD |
| Shipping | `/shipping/methods` CRUD, `/shipping/pincodes` (search, upsert, delete) |
| Content | `/banners` CRUD, `/pages`, `PUT /pages/{slug}`, `GET/PUT /settings`, `GET /newsletter?format=csv` |
| Audit | `GET /audit-logs` |

Health: `GET /health` (liveness), `GET /health/ready` (database check).
