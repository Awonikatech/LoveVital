import { api, csrfHeaders } from "./api";
import type {
  Address, AddressInput, Banner, Cart, CategoryNode, DeliveryEstimate, OrderDetail, OrderSummary, Paginated, PaymentOrder,
  ProductCard, ProductDetail, ProductList, PublicSettings, TokenResponse, User,
} from "@/types";

const d = <T,>(p: Promise<{ data: T }>) => p.then((r) => r.data);

export const storeApi = {
  // content
  settings: () => d(api.get<PublicSettings>("/settings/public")),
  home: () =>
    d(api.get<{
      banners: Banner[]; categories: CategoryNode[]; trending: ProductCard[]; best_sellers: ProductCard[]; new_arrivals: ProductCard[];
      on_sale: ProductCard[]; collections: { name: string; slug: string; description: string | null; image_url: string | null }[];
      promotions: { name: string; description: string | null; badge: string | null }[]; settings: PublicSettings;
    }>("/home")),
  page: (slug: string) => d(api.get<{ slug: string; title: string; body: string; seo_title: string | null; seo_description: string | null; updated_at: string }>(`/pages/${slug}`)),
  subscribe: (email: string) => d(api.post<{ message: string }>("/newsletter", { email })),

  // catalog
  categories: () => d(api.get<CategoryNode[]>("/categories")),
  collections: () => d(api.get<{ id: number; name: string; slug: string; description: string | null; image_url: string | null; product_count: number; is_featured: boolean }[]>("/collections")),
  products: (params: Record<string, string | number | boolean | undefined>) => d(api.get<ProductList>("/products", { params })),
  product: (slug: string) => d(api.get<ProductDetail>(`/products/${slug}`)),
  reviews: (slug: string, page = 1, sort = "recent") =>
    d(api.get<{ items: { id: number; rating: number; title: string | null; body: string | null; author: string; verified: boolean; created_at: string }[];
      total: number; average: number; count: number; distribution: Record<string, number> }>(`/products/${slug}/reviews`, { params: { page, sort } })),
  addReview: (slug: string, body: { rating: number; title?: string; body?: string }) => d(api.post(`/products/${slug}/reviews`, body)),
  suggest: (q: string) =>
    d(api.get<{ products: { slug: string; name: string; image: string | null; price: string; sku: string }[]; categories: { name: string; slug: string }[]; queries: string[] }>(
      "/search/suggest", { params: { q } })),
  estimate: (pin: string, product_slug?: string, order_value?: string) =>
    d(api.get<DeliveryEstimate>("/delivery/estimate", { params: { pin, product_slug, order_value } })),

  // auth
  login: (email: string, password: string) => d(api.post<TokenResponse>("/auth/login", { email, password })),
  register: (body: { full_name: string; email: string; password: string; phone?: string }) => d(api.post<TokenResponse>("/auth/register", body)),
  logout: () => d(api.post("/auth/logout", null, { headers: csrfHeaders() })),
  me: () => d(api.get<User>("/auth/me")),
  updateMe: (body: { full_name?: string; phone?: string | null }) => d(api.patch<User>("/auth/me", body)),
  changePassword: (current_password: string, new_password: string) => d(api.post("/auth/change-password", { current_password, new_password })),
  forgot: (email: string) => d(api.post<{ message: string }>("/auth/forgot-password", { email })),
  reset: (token: string, password: string) => d(api.post<{ message: string }>("/auth/reset-password", { token, password })),
  verifyEmail: (token: string) => d(api.post<{ message: string }>("/auth/verify-email", { token })),
  resendVerification: () => d(api.post<{ message: string }>("/auth/resend-verification")),

  // cart
  cart: () => d(api.get<Cart>("/cart")),
  addToCart: (variant_id: number, quantity = 1) => d(api.post<Cart>("/cart/items", { variant_id, quantity })),
  updateCartItem: (id: number, quantity: number) => d(api.patch<Cart>(`/cart/items/${id}`, { quantity })),
  removeCartItem: (id: number) => d(api.delete<Cart>(`/cart/items/${id}`)),
  applyCoupon: (code: string) => d(api.post<Cart>("/cart/coupon", { code })),
  removeCoupon: () => d(api.delete<Cart>("/cart/coupon")),

  // checkout & orders
  validateCheckout: (body: { email?: string; pin_code?: string; shipping_method_id?: number; payment_method: string; coupon_code?: string | null }) =>
    d(api.post<{ totals: Cart["totals"]; issues: Cart["issues"]; delivery: DeliveryEstimate | null; cod_available: boolean;
      cod_unavailable_reason: string | null; cod_fee: string; cart: Cart }>("/checkout/validate", body)),
  checkout: (body: Record<string, unknown>, idempotencyKey: string) =>
    d(api.post<{ created: boolean; order: OrderDetail }>("/checkout", body, { headers: { "Idempotency-Key": idempotencyKey } })),
  orders: (page = 1) => d(api.get<Paginated<OrderSummary>>("/orders", { params: { page } })),
  order: (ref: string, key?: string) => d(api.get<OrderDetail>(`/orders/${ref}`, { params: { key } })),
  lookupOrder: (order_number: string, email: string) => d(api.post<OrderDetail>("/orders/lookup", { order_number, email })),
  cancelOrder: (ref: string, reason: string, key?: string) => d(api.post<{ message: string; order: OrderDetail }>(`/orders/${ref}/cancel`, { reason }, { params: { key } })),
  requestReturn: (ref: string, body: { return_type: string; reason: string; details?: string; items: { order_item_id: number; quantity: number }[] }) =>
    d(api.post<{ message: string; order: OrderDetail }>(`/orders/${ref}/returns`, body)),
  returns: () => d(api.get<{ id: number; order_number: string; return_type: string; status: string; reason: string; refund_amount: string | null; admin_note: string | null; created_at: string }[]>("/returns")),
  track: (awb: string) =>
    d(api.get<{ order_number: string; order_status: string; order_status_label: string; courier_name: string | null; tracking_number: string; status: string;
      shipped_at: string | null; delivered_at: string | null; estimated_delivery_date: string | null; destination: string;
      events: { status: string; location: string | null; description: string; occurred_at: string }[] }>(`/track/${awb}`)),

  // payments
  createPayment: (order_id: string, order_key?: string) => d(api.post<PaymentOrder>("/payments/razorpay/create-order", { order_id, order_key })),
  verifyPayment: (body: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) =>
    d(api.post<{ status: string; order_number: string; order: OrderDetail }>("/payments/razorpay/verify", body)),
  paymentFailed: (body: { razorpay_order_id: string; razorpay_payment_id?: string; error_code?: string; error_description?: string }) =>
    d(api.post<{ status: string; order_number: string; order_key: string }>("/payments/razorpay/failed", body)),
  paymentStatus: (ref: string, key?: string) =>
    d(api.get<{ order_number: string; order_status: string; payment_status: string; grand_total: string; last_error: string | null; can_retry: boolean }>(`/payments/status/${ref}`, { params: { key } })),
  mockCheckout: (razorpay_order_id: string, outcome: "success" | "failure", method: string) =>
    d(api.post<{ status: string; razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature?: string; error?: { code: string; description: string } }>(
      "/payments/razorpay/mock-checkout", { razorpay_order_id, outcome, method })),

  // account
  addresses: () => d(api.get<Address[]>("/account/addresses")),
  addAddress: (a: AddressInput) => d(api.post<Address>("/account/addresses", a)),
  updateAddress: (id: number, a: AddressInput) => d(api.put<Address>(`/account/addresses/${id}`, a)),
  deleteAddress: (id: number) => d(api.delete(`/account/addresses/${id}`)),
  wishlist: () => d(api.get<{ items: { id: number; product: ProductCard; variant_id: number | null; added_at: string }[]; product_ids: number[] }>("/account/wishlist")),
  addWishlist: (product_id: number) => d(api.post<{ product_ids: number[] }>("/account/wishlist", { product_id })),
  removeWishlist: (product_id: number) => d(api.delete<{ product_ids: number[] }>(`/account/wishlist/${product_id}`)),
  myReviews: () => d(api.get<{ id: number; rating: number; title: string | null; body: string | null; status: string; product: { name: string; slug: string; image: string | null } | null; created_at: string }[]>("/account/reviews")),
};
