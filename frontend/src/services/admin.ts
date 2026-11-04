/**
 * Admin API client + shared admin types.
 * All endpoints live under /api/v1/admin and need a staff access token (handled by `api`).
 */
import axios from "axios";
import { api } from "@/services/api";
import type { OrderDetail, OrderSummary, Paginated } from "@/types";

export type Money = string;
type Params = Record<string, string | number | boolean | null | undefined>;

/** Drop empty values so URLs stay clean and FastAPI doesn't choke on "" for ints/dates. */
export function cleanParams(p: Params): Record<string, string | number | boolean> {
  const out: Record<string, string | number | boolean> = {};
  for (const [k, v] of Object.entries(p)) if (v !== undefined && v !== null && v !== "") out[k] = v;
  return out;
}
export function qs(p: Params): string {
  const s = new URLSearchParams(Object.entries(cleanParams(p)).map(([k, v]) => [k, String(v)])).toString();
  return s ? `?${s}` : "";
}

export const isForbidden = (err: unknown) => axios.isAxiosError(err) && err.response?.status === 403;
export const isNotFound = (err: unknown) => axios.isAxiosError(err) && err.response?.status === 404;

/* ------------------------------------------------------------------ datetimes
 * The backend stores naive UTC. We send naive UTC ("2026-10-18T09:30:00") and show local time in inputs.
 */
export function utcToLocalInput(v: string | null | undefined): string {
  if (!v) return "";
  const d = new Date(v.endsWith("Z") || v.includes("+") ? v : v + "Z");
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
export function localInputToUtc(v: string | null | undefined): string | null {
  if (!v) return null;
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString().slice(0, 19);
}
export function isoDay(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
export function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return isoDay(d);
}

/* ------------------------------------------------------------------ types */
export interface DashboardSummary {
  orders: number; gross_sales?: Money; discounts?: Money; markdowns?: Money; refunds?: Money; net_sales?: Money; revenue?: Money;
  shipping_collected?: Money; tax_collected?: Money; aov?: Money; gross_margin?: Money;
}
export interface LowStockRow {
  variant_id: number; product_id: number; product_name: string; variant_name: string; sku: string; on_hand: number; reserved: number;
  available: number; threshold: number; status: "out_of_stock" | "low_stock";
}
export interface BestSeller {
  product_id: number | null; name: string; sku: string; units: number; net_sales: Money; returned_units: number; image: string | null;
  slug: string | null; gross_margin?: Money;
}
export interface Dashboard {
  range: { start: string; end: string };
  summary: DashboardSummary; previous: DashboardSummary;
  totals: { customers: number; new_customers: number; products: number };
  queues: { pending_orders: number; awaiting_dispatch: number; cancellation_requests: number; open_returns: number; low_stock: number };
  sales_trend: { period: string; orders: number; net_sales?: Money; revenue?: Money }[];
  sales_by_category: { category: string; orders: number; units: number; net_sales?: Money }[];
  payment_methods: { method: string; orders: number; amount?: Money }[];
  best_sellers: BestSeller[];
  low_stock: LowStockRow[];
  recent_orders: OrderSummary[];
  definitions: string;
  finance_visible: boolean;
}

export type ProductStatus = "draft" | "active" | "archived";
export interface AdminProductRow {
  id: number; name: string; slug: string; sku: string; brand: string; product_type: "jewellery" | "apparel"; category_name: string;
  status: ProductStatus; is_featured: boolean; is_bestseller: boolean; is_new_arrival: boolean; price_min: Money; mrp_min: Money;
  max_discount_pct: number; total_stock: number; sold_count: number; rating_avg: number; updated_at: string; image: string | null;
  variant_count: number;
}
export interface AdminVariant {
  id: number; sku: string; name: string; mrp: Money; sale_price: Money; effective_price: Money; discount_pct: number;
  scheduled_sale_price: Money | null; sale_starts_at: string | null; sale_ends_at: string | null; weight_grams: string | null;
  is_active: boolean; is_default: boolean; attribute_value_ids: number[]; attributes: Record<string, string>;
  on_hand: number; reserved: number; available: number; low_stock_threshold: number; cost_price?: Money | null; margin_pct?: number | null;
}
export interface AdminImage { id: number; url: string; alt_text: string | null; is_primary: boolean; display_order: number; variant_id: number | null }
export interface SizeChartData { unit?: string; columns: string[]; rows: string[][]; note?: string }
export interface AdminProduct {
  id: number; name: string; slug: string; sku: string; brand: string; product_type: "jewellery" | "apparel"; category_id: number;
  category_name: string; tax_rate_id: number | null; short_description: string | null; description: string | null;
  specifications: Record<string, string>; care_instructions: string | null; size_chart: SizeChartData | null; tags: string[];
  status: ProductStatus; is_featured: boolean; is_bestseller: boolean; is_new_arrival: boolean; processing_days: number;
  min_order_qty: number; max_order_qty: number; is_returnable: boolean; return_window_days: number; is_cod_available: boolean;
  seo_title: string | null; seo_description: string | null; price_min: Money; mrp_min: Money; max_discount_pct: number;
  rating_avg: number; rating_count: number; sold_count: number; created_at: string; updated_at: string; collection_ids: number[];
  images: AdminImage[]; variants: AdminVariant[]; total_stock: number;
}
export interface ProductMeta {
  categories: { id: number; name: string; slug: string; parent_id: number | null; label: string }[];
  tax_rates: { id: number; name: string; rate: Money; hsn_code: string | null }[];
  collections: { id: number; name: string }[];
  attributes: { id: number; code: string; name: string; is_variant_axis: boolean; values: { id: number; value: string; slug: string; hex: string | null }[] }[];
  can_view_cost: boolean;
}
export interface VariantPayload {
  id?: number | null; sku: string; name: string; mrp: string; sale_price: string; cost_price?: string | null;
  scheduled_sale_price?: string | null; sale_starts_at?: string | null; sale_ends_at?: string | null; weight_grams?: string | null;
  is_active: boolean; is_default: boolean; attribute_value_ids: number[]; stock?: number | null; low_stock_threshold?: number | null;
}
export interface ProductPayload {
  name: string; slug?: string | null; sku: string; brand: string; product_type: "jewellery" | "apparel"; category_id: number;
  tax_rate_id?: number | null; short_description?: string | null; description?: string | null; specifications?: Record<string, string> | null;
  care_instructions?: string | null; size_chart?: SizeChartData | null; tags?: string[] | null; status: ProductStatus;
  is_featured: boolean; is_bestseller: boolean; is_new_arrival: boolean; processing_days: number; min_order_qty: number;
  max_order_qty: number; is_returnable: boolean; return_window_days: number; is_cod_available: boolean; seo_title?: string | null;
  seo_description?: string | null; collection_ids: number[]; variants: VariantPayload[];
}
export interface ImportResult { created: number; updated: number; errors: { line: number; error: string }[]; dry_run: boolean }

export interface AdminCategory {
  id: number; name: string; slug: string; parent_id: number | null; parent_name: string | null; description: string | null;
  image_url: string | null; display_order: number; is_active: boolean; seo_title: string | null; seo_description: string | null; product_count: number;
}
export interface AdminCollection {
  id: number; name: string; slug: string; description: string | null; image_url: string | null; is_featured: boolean; is_active: boolean;
  display_order: number; starts_at: string | null; ends_at: string | null; product_ids: number[]; products: { id: number; name: string; sku: string }[];
}

export interface InventoryRow {
  variant_id: number; product_id: number; product_name: string; variant_name: string; sku: string; image: string | null; on_hand: number;
  reserved: number; available: number; low_stock_threshold: number; is_active: boolean; status: "out_of_stock" | "low_stock" | "in_stock";
}
export interface MovementRow {
  id: number; sku: string; product_name: string; variant_name: string; movement_type: string; quantity: number; balance_after: number;
  reference: string | null; note: string | null; by: string; at: string;
}
export interface ReservationRow { id: number; sku: string | null; order_number: string | null; order_id: number; quantity: number; status: string; expires_at: string; release_reason: string | null }

export type AdminOrderDetail = OrderDetail & { idempotency_key?: string };
export interface OrdersPage extends Paginated<OrderSummary> { status_counts: Record<string, number> }

export interface CustomerRow {
  id: number; full_name: string; email: string; phone: string | null; is_active: boolean; email_verified: boolean; created_at: string;
  orders: number; total_spend: Money; last_order_at: string | null;
}
export interface CustomerDetail {
  id: number; full_name: string; email: string; phone: string | null; is_active: boolean; disabled_reason: string | null;
  email_verified_at: string | null; created_at: string; last_login_at: string | null; support_notes: string | null; roles: string[];
  addresses: { id: number; label: string | null; full_name: string; phone: string; line1: string; line2: string | null; city: string; state: string; pin_code: string; is_default_shipping: boolean }[];
  orders: OrderSummary[];
  stats: { orders: number; lifetime_value: Money; aov: Money; refunded: Money };
}

export type AppliesTo = "all" | "categories" | "products";
export interface Coupon {
  id: number; code: string; description: string | null; discount_type: "percent" | "fixed" | "free_shipping"; value: Money;
  min_cart_value: Money; max_discount: Money | null; starts_at: string | null; ends_at: string | null; usage_limit_total: number | null;
  usage_limit_per_user: number | null; times_used: number; first_order_only: boolean; applies_to: AppliesTo; category_ids: number[];
  product_ids: number[]; customer_emails: string[]; combinable_with_promotions: boolean; is_active: boolean; discount_given?: Money;
}
export type CouponPayload = Omit<Coupon, "id" | "times_used" | "discount_given" | "value" | "min_cart_value" | "max_discount"> & {
  value: string; min_cart_value: string; max_discount: string | null;
};
export interface Redemption { id: number; order_id: number; order_number: string; email: string; discount_amount: Money; status: string; at: string }
export type PromoType = "percent_off" | "fixed_off" | "bogo" | "quantity_discount" | "free_shipping";
export interface Promotion {
  id: number; name: string; description: string | null; badge_text: string | null; promo_type: PromoType; value: Money;
  config: Record<string, number | string>; applies_to: AppliesTo; category_ids: number[]; product_ids: number[]; priority: number;
  is_stackable: boolean; is_active: boolean; starts_at: string | null; ends_at: string | null;
}
export type PromotionPayload = Omit<Promotion, "id">;

export interface ShippingMethod {
  id: number; code: string; name: string; description: string | null; carrier: string; base_charge: Money; free_shipping_threshold: Money | null;
  min_days: number; max_days: number; is_cod_allowed: boolean; is_active: boolean; display_order: number;
}
export type ShippingMethodPayload = Omit<ShippingMethod, "id">;
export interface PinRule {
  id: number; pin_code: string; city: string | null; state: string | null; region: "metro" | "regional" | "national" | "remote";
  extra_days: number; is_serviceable: boolean; is_cod_available: boolean;
}
export type PinPayload = Omit<PinRule, "id">;

export interface ReturnRequest {
  id: number; order_id: number; order_number: string; customer_email: string; return_type: string; status: string; reason: string;
  details: string | null; items: { order_item_id: number; quantity: number; product_name: string; sku: string; image_url: string | null }[];
  refund_amount: Money | null; admin_note: string | null; created_at: string; resolved_at: string | null; order_status: string; payment_method: string;
}

export interface BannerRow {
  id: number; title: string; subtitle: string | null; eyebrow: string | null; image_url: string; cta_text: string | null; cta_link: string | null;
  placement: "hero" | "promo" | "strip"; display_order: number; is_active: boolean; starts_at: string | null; ends_at: string | null;
}
export type BannerPayload = Omit<BannerRow, "id">;
export interface CmsPageRow { id: number; slug: string; title: string; body: string; seo_title: string | null; seo_description: string | null; is_published: boolean; updated_at: string }
export interface SettingRow { key: string; value: any; description: string; is_public: boolean }
export type GatewayMode = "mock" | "test" | "live";
export interface GatewaySettings {
  mode: GatewayMode; source: "admin" | "env"; key_id: string;
  key_secret_set: boolean; key_secret_hint: string | null; webhook_secret_set: boolean; webhook_secret_hint: string | null;
  webhook_url: string; webhook_events: string[]; production: boolean;
}
export interface GatewayPayload { mode: GatewayMode; key_id: string; key_secret?: string; webhook_secret?: string }
export interface Subscriber { email: string; status: string; source: string | null; subscribed_at: string }
export interface AuditRow { id: number; actor: string; action: string; entity_type: string; entity_id: string | null; changes: unknown; ip: string | null; at: string }

export const REPORT_NAMES = ["sales", "order_status", "products", "categories", "inventory", "coupons", "customers", "refunds"] as const;
export type ReportName = (typeof REPORT_NAMES)[number];
export interface ReportResponse<T = any> { report: ReportName; range: { start: string; end: string }; data: T }

/* ------------------------------------------------------------------ calls */
const g = <T,>(url: string) => api.get<T>(`/admin${url}`).then((r) => r.data);
const post = <T,>(url: string, body?: unknown) => api.post<T>(`/admin${url}`, body).then((r) => r.data);
const put = <T,>(url: string, body?: unknown) => api.put<T>(`/admin${url}`, body).then((r) => r.data);
const patch = <T,>(url: string, body?: unknown) => api.patch<T>(`/admin${url}`, body).then((r) => r.data);
const del = <T,>(url: string) => api.delete<T>(`/admin${url}`).then((r) => r.data);
function upload<T>(url: string, file: File) {
  const fd = new FormData();
  fd.append("file", file);
  return api.post<T>(`/admin${url}`, fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 60000 }).then((r) => r.data);
}

export const adminApi = {
  dashboard: (p: { start?: string; end?: string }) => g<Dashboard>(`/dashboard${qs(p)}`),
  report: <T = any>(name: ReportName, p: Params) => g<ReportResponse<T>>(`/reports/${name}${qs(p)}`),

  products: (p: Params) => g<Paginated<AdminProductRow>>(`/products${qs(p)}`),
  productMeta: () => g<ProductMeta>("/products/meta"),
  product: (id: number) => g<AdminProduct>(`/products/${id}`),
  createProduct: (b: ProductPayload) => post<AdminProduct>("/products", b),
  updateProduct: (id: number, b: ProductPayload) => put<AdminProduct>(`/products/${id}`, b),
  patchProduct: (id: number, b: Partial<Pick<AdminProduct, "status" | "is_featured" | "is_bestseller" | "is_new_arrival">>) => patch(`/products/${id}`, b),
  deleteProduct: (id: number) => del<{ deleted?: boolean; archived?: boolean; message?: string }>(`/products/${id}`),
  uploadProductImage: (id: number, f: File) => upload<{ id: number; url: string; is_primary: boolean }>(`/products/${id}/images`, f),
  patchImage: (pid: number, iid: number, b: Partial<Pick<AdminImage, "is_primary" | "display_order" | "alt_text" | "variant_id">>) => patch(`/products/${pid}/images/${iid}`, b),
  deleteImage: (pid: number, iid: number) => del(`/products/${pid}/images/${iid}`),
  importProducts: (f: File, dryRun: boolean) => upload<ImportResult>(`/products-import?dry_run=${dryRun}`, f),

  categories: () => g<AdminCategory[]>("/categories"),
  saveCategory: (id: number | null, b: unknown) => (id ? put<AdminCategory>(`/categories/${id}`, b) : post<AdminCategory>("/categories", b)),
  deleteCategory: (id: number) => del(`/categories/${id}`),
  uploadImage: (f: File, folder: "content" | "categories" | "collections" | "banners") => upload<{ url: string }>(`/uploads/image?folder=${folder}`, f),
  collections: () => g<AdminCollection[]>("/collections"),
  saveCollection: (id: number | null, b: unknown) => (id ? put<AdminCollection>(`/collections/${id}`, b) : post<AdminCollection>("/collections", b)),
  deleteCollection: (id: number) => del(`/collections/${id}`),

  inventory: (p: Params) => g<Paginated<InventoryRow>>(`/inventory${qs(p)}`),
  adjustStock: (b: { variant_id: number; delta: number; movement_type: string; note?: string | null; low_stock_threshold?: number | null }) =>
    post<{ variant_id: number; on_hand: number; reserved: number; available: number; low_stock_threshold: number }>("/inventory/adjust", b),
  movements: (p: Params) => g<Paginated<MovementRow>>(`/inventory/movements${qs(p)}`),
  reservations: (status = "active") => g<ReservationRow[]>(`/inventory/reservations?status=${status}`),
  sweepReservations: () => post<{ released_orders: number | string[] }>("/inventory/sweep-reservations"),

  orders: (p: Params) => g<OrdersPage>(`/orders${qs(p)}`),
  order: (id: number) => g<AdminOrderDetail>(`/orders/${id}`),
  setOrderStatus: (id: number, status: string, note?: string) => post<AdminOrderDetail>(`/orders/${id}/status`, { status, note: note || null }),
  cancelOrder: (id: number, reason: string) => post<AdminOrderDetail>(`/orders/${id}/cancel`, { reason }),
  resolveCancellation: (id: number, approve: boolean, note?: string) => post<AdminOrderDetail>(`/orders/${id}/cancellation-request`, { approve, note: note || null }),
  addOrderNote: (id: number, body: string) => post<AdminOrderDetail["notes"]>(`/orders/${id}/notes`, { body }),
  createShipment: (id: number, b: { courier_name?: string | null; tracking_number?: string | null; tracking_url?: string | null; weight_grams?: number | null; mark_shipped: boolean }) =>
    post<AdminOrderDetail>(`/orders/${id}/shipments`, b),
  shipmentStatus: (sid: number, b: { status: string; location?: string | null; description?: string | null }) => post<AdminOrderDetail>(`/shipments/${sid}/status`, b),
  refund: (id: number, b: { amount?: string | null; reason: string }) => post<AdminOrderDetail>(`/orders/${id}/refunds`, b),

  customers: (p: Params) => g<Paginated<CustomerRow>>(`/customers${qs(p)}`),
  customer: (id: number) => g<CustomerDetail>(`/customers/${id}`),
  patchCustomer: (id: number, b: { is_active?: boolean; disabled_reason?: string | null; support_notes?: string | null }) => patch<{ ok: boolean; is_active: boolean }>(`/customers/${id}`, b),

  coupons: () => g<Coupon[]>("/coupons"),
  saveCoupon: (id: number | null, b: CouponPayload) => (id ? put<Coupon>(`/coupons/${id}`, b) : post<Coupon>("/coupons", b)),
  deleteCoupon: (id: number) => del<{ message: string }>(`/coupons/${id}`),
  redemptions: (id: number) => g<Redemption[]>(`/coupons/${id}/redemptions`),
  promotions: () => g<Promotion[]>("/promotions"),
  savePromotion: (id: number | null, b: PromotionPayload) => (id ? put<Promotion>(`/promotions/${id}`, b) : post<Promotion>("/promotions", b)),
  deletePromotion: (id: number) => del(`/promotions/${id}`),

  shippingMethods: () => g<ShippingMethod[]>("/shipping/methods"),
  saveShippingMethod: (id: number | null, b: ShippingMethodPayload) => (id ? put<ShippingMethod>(`/shipping/methods/${id}`, b) : post<ShippingMethod>("/shipping/methods", b)),
  pins: (p: Params) => g<Paginated<PinRule>>(`/shipping/pincodes${qs(p)}`),
  upsertPin: (b: PinPayload) => post<PinRule>("/shipping/pincodes", b),
  deletePin: (id: number) => del(`/shipping/pincodes/${id}`),

  returns: (p: Params) => g<Paginated<ReturnRequest>>(`/returns${qs(p)}`),
  returnAction: (id: number, action: "approve" | "reject" | "receive", note?: string) => post<ReturnRequest>(`/returns/${id}`, { action, note: note || null }),

  banners: () => g<BannerRow[]>("/banners"),
  saveBanner: (id: number | null, b: BannerPayload) => (id ? put<BannerRow>(`/banners/${id}`, b) : post<BannerRow>("/banners", b)),
  deleteBanner: (id: number) => del(`/banners/${id}`),
  pages: () => g<CmsPageRow[]>("/pages"),
  savePage: (slug: string, b: { slug: string; title: string; body: string; seo_title?: string | null; seo_description?: string | null; is_published: boolean }) =>
    put<{ slug: string; title: string }>(`/pages/${encodeURIComponent(slug)}`, b),
  settings: () => g<SettingRow[]>("/settings"),
  saveSettings: (values: Record<string, unknown>) => put<{ ok: boolean }>("/settings", { values }),
  paymentGateway: () => g<GatewaySettings>("/payment-gateway"),
  savePaymentGateway: (body: GatewayPayload) => put<GatewaySettings>("/payment-gateway", body),
  testPaymentGateway: (body: GatewayPayload) => post<{ ok: boolean; message: string }>("/payment-gateway/test", body),
  resetPaymentGateway: () => del<GatewaySettings>("/payment-gateway"),
  newsletter: () => g<Subscriber[]>("/newsletter"),

  audit: (p: Params) => g<Paginated<AuditRow>>(`/audit-logs${qs(p)}`),
};

/** Statuses an admin sees in the order list filter, in workflow order. */
export const ORDER_STATUSES: { value: string; label: string }[] = [
  { value: "payment_pending", label: "Payment pending" }, { value: "order_placed", label: "Order placed" },
  { value: "payment_confirmed", label: "Payment confirmed" }, { value: "processing", label: "Processing" }, { value: "packed", label: "Packed" },
  { value: "shipped", label: "Shipped" }, { value: "out_for_delivery", label: "Out for delivery" }, { value: "delivered", label: "Delivered" },
  { value: "delivery_failed", label: "Delivery failed" }, { value: "cancellation_requested", label: "Cancellation requested" },
  { value: "cancelled", label: "Cancelled" }, { value: "return_requested", label: "Return requested" }, { value: "returned", label: "Returned" },
  { value: "refund_initiated", label: "Refund initiated" }, { value: "refunded", label: "Refunded" },
];
