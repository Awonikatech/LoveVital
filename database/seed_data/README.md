# Seed data

`catalog.json` is a read-only export of the demo catalogue (22 categories, 5 collections, 10 attributes, 51 products with
their variant colours/sizes, prices, stock levels and flags). The source of truth is `backend/scripts/seed_catalog.py`;
`backend/scripts/seed.py` loads it plus users, coupons, promotions, shipping rules, banners, CMS pages, 65 sample orders
(in every lifecycle state, created through the real checkout/payment services) and ~180 reviews.

```bash
cd backend && python -m scripts.seed      # idempotent: re-running never duplicates records
```

Product photography is generated locally as SVG (`python -m scripts.generate_images`) so the demo never depends on external image hosts.
