// Money values arrive from the API as decimal strings ("499.00") — never floats.
export type Money = string;

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  phone: string | null;
  is_active: boolean;
  email_verified_at: string | null;
  roles: string[];
  permissions: string[];
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Swatch { value: string; slug: string; hex: string | null }

export interface ProductCard {
  id: number;
  slug: string;
  name: string;
  sku: string;
  brand: string;
  product_type: "jewellery" | "apparel";
  category: { id: number; name: string; slug: string };
  image: string | null;
  hover_image: string | null;
  mrp: Money;
  price: Money;
  discount_pct: number;
  rating_avg: number;
  rating_count: number;
  in_stock: boolean;
  stock_status: "in_stock" | "low_stock" | "out_of_stock";
  is_new_arrival: boolean;
  is_bestseller: boolean;
  is_featured: boolean;
  badges: string[];
  variant_count: number;
  default_variant_id: number | null;
  colors: Swatch[];
}

export interface Variant {
  id: number;
  sku: string;
  name: string;
  mrp: Money;
  price: Money;
  discount_pct: number;
  savings: Money;
  available: number;
  stock_status: ProductCard["stock_status"];
  attributes: Record<string, string>;
  is_default: boolean;
  weight_grams: string | null;
  image_urls: string[];
}

export interface VariantOption {
  code: string;
  name: string;
  display_type: "swatch" | "button" | "text";
  values: Swatch[];
}

export interface SizeChart { unit: string; columns: string[]; rows: string[][]; note?: string }

export interface ProductDetail extends ProductCard {
  description: string | null;
  short_description: string | null;
  specifications: Record<string, string>;
  care_instructions: string | null;
  size_chart: SizeChart | null;
  images: { id: number; url: string; alt: string; variant_id: number | null }[];
  variants: Variant[];
  options: VariantOption[];
  tax_rate: Money;
  tax_inclusive: boolean;
  hsn_code: string | null;
  min_order_qty: number;
  max_order_qty: number;
  processing_days: number;
  is_returnable: boolean;
  return_window_days: number;
  is_cod_available: boolean;
  seo_title: string;
  seo_description: string;
  breadcrumbs: { name: string; slug: string }[];
  tags: string[];
  collections: { name: string; slug: string }[];
  related: ProductCard[];
  frequently_bought_together: ProductCard[];
  free_shipping_threshold: string;
}

export interface Facets {
  brands: { value: string; count: number }[];
  price: { min: Money; max: Money };
  attributes: { code: string; name: string; values: (Swatch & { count: number })[] }[];
}

export interface ProductList {
  items: ProductCard[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  facets: Facets;
  did_you_mean: string | null;
  category: null | {
    id: number; name: string; slug: string; description: string | null; image_url: string | null;
    seo_title: string | null; seo_description: string | null;
    parent: { name: string; slug: string } | null; children: { name: string; slug: string }[];
  };
  collection: null | { name: string; slug: string; description: string | null; image_url: string | null };
}

export interface CategoryNode {
  id: number; name: string; slug: string; image_url: string | null; description: string | null;
  display_order: number; children: CategoryNode[]; product_count: number;
}

export interface Banner {
  id: number; title: string; subtitle: string | null; eyebrow: string | null; image_url: string;
  cta_text: string | null; cta_link: string | null; placement: string;
}

export interface Totals {
  subtotal_mrp: Money; subtotal: Money; item_discount: Money; promotion_discount: Money; coupon_discount: Money;
  shipping_charge: Money; cod_charge: Money; tax_total: Money; grand_total: Money; total_savings: Money;
  free_shipping: boolean; free_shipping_threshold: Money | null; amount_to_free_shipping: Money | null;
  applied_promotions: { id: number; name: string; type: string; amount: Money; badge: string | null }[];
  coupon: { code: string; applied: boolean; message: string | null } | null;
  messages: string[];
  tax_inclusive: boolean;
}

export interface CartItem {
  id: number; variant_id: number; product_id: number; product_slug: string; product_name: string; variant_name: string;
  sku: string; image: string | null; attributes: Record<string, string>; quantity: number; unit_mrp: Money; unit_price: Money;
  line_mrp: Money; line_subtotal: Money; promo_discount: Money; coupon_discount: Money; line_total: Money;
  available: number; min_qty: number; max_qty: number; purchasable: boolean;
}

export interface Cart {
  id: number; token: string; item_count: number; items: CartItem[]; totals: Totals;
  issues: { item_id: number; code: string; message: string }[]; can_checkout: boolean;
}

export interface Address {
  id: number; label: string | null; full_name: string; phone: string; line1: string; line2: string | null;
  landmark: string | null; city: string; state: string; pin_code: string; country: string;
  is_default_shipping: boolean; is_default_billing: boolean;
}
export type AddressInput = Omit<Address, "id" | "country"> & { country?: string };

export interface DeliveryMethod {
  id: number; code: string; name: string; carrier: string; description: string | null; charge: Money; base_charge: Money;
  free_shipping_threshold: Money | null; is_cod_allowed: boolean; dispatch_date: string; delivery_from: string; delivery_to: string;
  min_days: number; max_days: number;
}
export interface DeliveryEstimate {
  pin_code: string; serviceable: boolean; cod_available: boolean; region: string; city: string | null; state: string | null;
  methods: DeliveryMethod[]; message: string;
}

export interface OrderSummary {
  id: number; order_number: string; status: string; status_label: string; payment_status: string; payment_method: string;
  grand_total: Money; item_count: number; placed_at: string; estimated_delivery_date: string | null; email: string;
  customer_name: string | null; thumbnails: (string | null)[]; first_item: string | null;
}

export interface OrderItem {
  id: number; product_id: number | null; variant_id: number | null; product_name: string; product_slug: string | null;
  variant_name: string | null; sku: string; image_url: string | null; attributes: Record<string, string> | null; quantity: number;
  returned_quantity: number; unit_mrp: Money; unit_price: Money; discount_amount: Money; tax_rate: Money; tax_amount: Money;
  line_total: Money; unit_cost?: Money | null;
}

export interface OrderAddress {
  full_name: string; phone: string; line1: string; line2: string | null; landmark: string | null; city: string; state: string;
  pin_code: string; country: string; gstin: string | null;
}

export interface OrderDetail extends OrderSummary {
  phone: string | null; currency: string; items: OrderItem[];
  totals: { subtotal_mrp: Money; subtotal: Money; item_discount: Money; promotion_discount: Money; coupon_discount: Money;
    coupon_code: string | null; shipping_charge: Money; cod_charge: Money; tax_total: Money; grand_total: Money; refunded_total: Money };
  applied_promotions: Totals["applied_promotions"];
  shipping_address: OrderAddress | null; billing_address: OrderAddress | null; shipping_method_name: string | null;
  estimated_dispatch_date: string | null; customer_note: string | null; cancellation_reason: string | null;
  paid_at: string | null; delivered_at: string | null; cancelled_at: string | null;
  payments: { id: number; provider: string; mode: string; method: string | null; status: string; amount: Money; amount_refunded: Money;
    razorpay_order_id: string | null; razorpay_payment_id: string | null; error_description: string | null; attempts: number;
    created_at: string; captured_at: string | null }[];
  refunds: { id: number; amount: Money; status: string; reason: string | null; razorpay_refund_id: string | null; created_at: string; processed_at: string | null }[];
  shipments: { id: number; courier_name: string | null; tracking_number: string | null; tracking_url: string | null; status: string;
    shipped_at: string | null; delivered_at: string | null; events: { status: string; location: string | null; description: string; occurred_at: string }[] }[];
  history: { from: string | null; to: string; label: string; note: string | null; actor_type: string; at: string }[];
  timeline: { status: string; label: string; done: boolean; at: string | null; exception?: boolean }[];
  can_cancel: boolean; can_request_cancel: boolean; can_return: boolean; can_pay: boolean; can_review: boolean; invoice_available: boolean;
  order_key?: string;
  // admin-only
  allowed_transitions?: { value: string; label: string }[];
  manual_transitions?: { value: string; label: string }[];
  notes?: { id: number; author: string | null; body: string; at: string }[];
  user_id?: number | null;
  can_refund?: boolean;
  can_ship?: boolean;
}

export interface Paginated<T> { items: T[]; total: number; page: number; page_size: number; pages: number }

export interface PaymentOrder {
  key_id: string; mode: "mock" | "test" | "live"; razorpay_order_id: string; amount: number; currency: string; name: string;
  description: string; order_number: string; order_id: number; prefill: { name: string; email: string; contact: string }; theme_color: string;
}

export type PublicSettings = Record<string, any> & {
  store_name: string; announcement_text: string; free_shipping_threshold: string; cod_fee: string; support_email: string;
  support_phone: string; support_hours: string; store_address: string; social_links: Record<string, string>;
  footer_links: { label: string; href: string }[]; testimonials: { name: string; city: string; text: string; rating: number }[];
  payment_mode: "mock" | "test" | "live";
};
