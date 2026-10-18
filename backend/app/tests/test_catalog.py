"""Storefront catalog: listing, filters, sorting, search, product detail and delivery estimates."""
API = "/api/v1"


def _slugs(resp) -> list[str]:
    assert resp.status_code == 200, resp.text
    return [p["slug"] for p in resp.json()["items"]]


def test_list_excludes_non_active_products(client, catalog):
    data = client.get(f"{API}/products").json()
    assert data["total"] == 4
    assert "retired-brass-bracelet" not in [p["slug"] for p in data["items"]]


def test_category_filter_includes_descendants(client, catalog):
    slugs = _slugs(client.get(f"{API}/products", params={"category": "jewellery"}))
    assert set(slugs) == {"temple-jhumka-earrings", "kundan-choker-necklace", "oxidised-silver-ring"}
    assert _slugs(client.get(f"{API}/products", params={"category": "earrings"})) == ["temple-jhumka-earrings"]
    data = client.get(f"{API}/products", params={"category": "jewellery"}).json()
    assert {c["slug"] for c in data["category"]["children"]} == {"earrings", "necklaces", "rings"}


def test_unknown_category_returns_nothing(client, catalog):
    assert client.get(f"{API}/products", params={"category": "nope"}).json()["total"] == 0


def test_price_range_filter(client, catalog):
    slugs = _slugs(client.get(f"{API}/products", params={"min_price": 500, "max_price": 1000}))
    assert set(slugs) == {"temple-jhumka-earrings", "indigo-cotton-kurti"}


def test_in_stock_filter(client, catalog):
    all_slugs = _slugs(client.get(f"{API}/products"))
    in_stock = _slugs(client.get(f"{API}/products", params={"in_stock": "true"}))
    assert "oxidised-silver-ring" in all_slugs
    assert "oxidised-silver-ring" not in in_stock
    assert len(in_stock) == 3


def test_color_filter(client, catalog):
    assert _slugs(client.get(f"{API}/products", params={"color": "red"})) == ["temple-jhumka-earrings"]
    assert set(_slugs(client.get(f"{API}/products", params={"color": "red,blue"}))) == {"temple-jhumka-earrings", "indigo-cotton-kurti"}


def test_sorting_by_price(client, catalog):
    asc = _slugs(client.get(f"{API}/products", params={"sort": "price_asc"}))
    assert asc == ["oxidised-silver-ring", "indigo-cotton-kurti", "temple-jhumka-earrings", "kundan-choker-necklace"]
    desc = _slugs(client.get(f"{API}/products", params={"sort": "price_desc"}))
    assert desc == list(reversed(asc))


def test_pagination(client, catalog):
    p1 = client.get(f"{API}/products", params={"sort": "price_asc", "page_size": 3}).json()
    p2 = client.get(f"{API}/products", params={"sort": "price_asc", "page_size": 3, "page": 2}).json()
    assert p1["total"] == p2["total"] == 4
    assert p1["pages"] == 2
    assert len(p1["items"]) == 3 and len(p2["items"]) == 1
    assert p2["items"][0]["slug"] == "kundan-choker-necklace"
    assert client.get(f"{API}/products", params={"page_size": 61}).status_code == 422


def test_card_fields(client, catalog):
    card = next(p for p in client.get(f"{API}/products").json()["items"] if p["slug"] == "temple-jhumka-earrings")
    assert card["mrp"] == "1299.00"
    assert card["price"] == "899.00"
    assert card["discount_pct"] == 31
    assert card["in_stock"] is True
    assert {c["slug"] for c in card["colors"]} == {"gold", "red"}


def test_search_by_sku(client, catalog):
    assert _slugs(client.get(f"{API}/products", params={"q": "JW-NCK-001"})) == ["kundan-choker-necklace"]
    # variant SKUs are indexed too
    assert _slugs(client.get(f"{API}/products", params={"q": "jw-ear-001-red"})) == ["temple-jhumka-earrings"]


def test_synonym_search(client, catalog):
    data = client.get(f"{API}/products", params={"q": "jhumki"}).json()
    assert [p["slug"] for p in data["items"]] == ["temple-jhumka-earrings"]
    assert data["did_you_mean"] is None


def test_plural_search_is_stemmed(client, catalog):
    assert "indigo-cotton-kurti" in _slugs(client.get(f"{API}/products", params={"q": "kurtis"}))


def test_typo_gets_did_you_mean(client, catalog):
    data = client.get(f"{API}/products", params={"q": "kundn"}).json()
    assert data["total"] == 0
    assert data["did_you_mean"] == "kundan"


def test_suggest_endpoint_is_typo_tolerant(client, catalog):
    data = client.get(f"{API}/search/suggest", params={"q": "chokr"}).json()
    assert [p["slug"] for p in data["products"]] == ["kundan-choker-necklace"]


def test_product_detail(client, catalog):
    r = client.get(f"{API}/products/temple-jhumka-earrings")
    assert r.status_code == 200
    d = r.json()
    assert d["mrp"] == "1299.00" and d["price"] == "899.00" and d["discount_pct"] == 31
    assert d["tax_rate"] == "3.00" and d["tax_inclusive"] is True
    variants = {v["sku"]: v for v in d["variants"]}
    assert set(variants) == {"JW-EAR-001-GLD", "JW-EAR-001-RED"}
    assert variants["JW-EAR-001-GLD"]["available"] == 10
    assert variants["JW-EAR-001-GLD"]["stock_status"] == "in_stock"
    assert variants["JW-EAR-001-RED"]["price"] == "999.00"
    assert variants["JW-EAR-001-RED"]["savings"] == "300.00"
    assert variants["JW-EAR-001-RED"]["available"] == 3
    assert [b["slug"] for b in d["breadcrumbs"]] == ["jewellery", "earrings"]
    assert d["specifications"]["Material"] == "Brass"
    assert any(o["code"] == "color" for o in d["options"])


def test_out_of_stock_variant_detail(client, catalog):
    d = client.get(f"{API}/products/oxidised-silver-ring").json()
    assert d["in_stock"] is False
    assert d["variants"][0]["stock_status"] == "out_of_stock"
    assert d["discount_pct"] == 0


def test_archived_and_unknown_products_404(client, catalog):
    assert client.get(f"{API}/products/retired-brass-bracelet").status_code == 404
    assert client.get(f"{API}/products/does-not-exist").status_code == 404


def test_delivery_estimate_for_pin(client, catalog):
    r = client.get(f"{API}/delivery/estimate", params={"pin": "110017", "product_slug": "temple-jhumka-earrings"})
    assert r.status_code == 200
    d = r.json()
    assert d["serviceable"] is True and d["cod_available"] is True
    assert d["region"] == "metro"
    m = d["methods"][0]
    assert m["code"] == "standard"
    assert m["charge"] == "79.00"  # 899 < 999 free-shipping threshold
    assert m["delivery_from"] <= m["delivery_to"]
    assert d["message"].startswith("Delivery by")


def test_delivery_estimate_free_shipping_and_unserviceable(client, catalog):
    free = client.get(f"{API}/delivery/estimate", params={"pin": "110017", "order_value": 1500}).json()
    assert free["methods"][0]["charge"] == "0.00"
    blocked = client.get(f"{API}/delivery/estimate", params={"pin": "682551"}).json()
    assert blocked["serviceable"] is False and blocked["methods"] == []
    unknown = client.get(f"{API}/delivery/estimate", params={"pin": "999999"}).json()
    assert unknown["serviceable"] is True and unknown["region"] == "national"
    bad = client.get(f"{API}/delivery/estimate", params={"pin": "012345"})
    assert bad.status_code == 422


def test_category_tree_counts(client, catalog):
    tree = client.get(f"{API}/categories").json()
    jew = next(c for c in tree if c["slug"] == "jewellery")
    assert jew["product_count"] == 3
    assert {c["slug"] for c in jew["children"]} == {"earrings", "necklaces", "rings"}
