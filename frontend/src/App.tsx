import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import StoreLayout from "@/layouts/StoreLayout";
import { PageSpinner } from "@/components/ui";
import { useAuth } from "@/features/auth";
import Home from "@/pages/Home";

const Listing = lazy(() => import("@/pages/Listing"));
const ProductPage = lazy(() => import("@/pages/Product"));
const CartPage = lazy(() => import("@/pages/Cart"));
const Checkout = lazy(() => import("@/pages/Checkout"));
const PaymentResult = lazy(() => import("@/pages/PaymentResult"));
const Login = lazy(() => import("@/pages/auth/Login"));
const Register = lazy(() => import("@/pages/auth/Register"));
const ForgotPassword = lazy(() => import("@/pages/auth/ForgotPassword"));
const ResetPassword = lazy(() => import("@/pages/auth/ResetPassword"));
const VerifyEmail = lazy(() => import("@/pages/auth/VerifyEmail"));
const AccountLayout = lazy(() => import("@/pages/account/AccountLayout"));
const Profile = lazy(() => import("@/pages/account/Profile"));
const Addresses = lazy(() => import("@/pages/account/Addresses"));
const Orders = lazy(() => import("@/pages/account/Orders"));
const OrderDetail = lazy(() => import("@/pages/account/OrderDetail"));
const Wishlist = lazy(() => import("@/pages/account/Wishlist"));
const MyReviews = lazy(() => import("@/pages/account/Reviews"));
const MyReturns = lazy(() => import("@/pages/account/Returns"));
const TrackOrder = lazy(() => import("@/pages/TrackOrder"));
const CmsPage = lazy(() => import("@/pages/CmsPage"));
const Collections = lazy(() => import("@/pages/Collections"));
const NotFound = lazy(() => import("@/pages/NotFound"));

const AdminApp = lazy(() => import("@/pages/admin/AdminApp"));

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

export function RequireAuth({ children, staff }: { children: JSX.Element; staff?: boolean }) {
  const { user, ready, isStaff } = useAuth();
  const loc = useLocation();
  if (!ready) return <PageSpinner />;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  if (staff && !isStaff) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <>
      <ScrollToTop />
      <Suspense fallback={<PageSpinner />}>
        <Routes>
          <Route path="/admin/*" element={<RequireAuth staff><AdminApp /></RequireAuth>} />
          <Route element={<StoreLayout />}>
            <Route index element={<Home />} />
            <Route path="shop" element={<Listing mode="all" />} />
            <Route path="search" element={<Listing mode="search" />} />
            <Route path="category/:slug" element={<Listing mode="category" />} />
            <Route path="collections" element={<Collections />} />
            <Route path="collections/:slug" element={<Listing mode="collection" />} />
            <Route path="jewellery" element={<Listing mode="type" productType="jewellery" />} />
            <Route path="apparel" element={<Listing mode="type" productType="apparel" />} />
            <Route path="new-arrivals" element={<Listing mode="flag" flag="new_arrival" />} />
            <Route path="best-sellers" element={<Listing mode="flag" flag="bestseller" />} />
            <Route path="sale" element={<Listing mode="flag" flag="on_sale" />} />
            <Route path="product/:slug" element={<ProductPage />} />
            <Route path="cart" element={<CartPage />} />
            <Route path="checkout" element={<Checkout />} />
            <Route path="payment/:orderNumber" element={<PaymentResult />} />
            <Route path="track" element={<TrackOrder />} />
            <Route path="track/:awb" element={<TrackOrder />} />
            <Route path="pages/:slug" element={<CmsPage />} />
            <Route path="login" element={<Login />} />
            <Route path="register" element={<Register />} />
            <Route path="forgot-password" element={<ForgotPassword />} />
            <Route path="reset-password" element={<ResetPassword />} />
            <Route path="verify-email" element={<VerifyEmail />} />
            <Route path="account" element={<RequireAuth><AccountLayout /></RequireAuth>}>
              <Route index element={<Navigate to="orders" replace />} />
              <Route path="profile" element={<Profile />} />
              <Route path="addresses" element={<Addresses />} />
              <Route path="orders" element={<Orders />} />
              <Route path="orders/:ref" element={<OrderDetail />} />
              <Route path="wishlist" element={<Wishlist />} />
              <Route path="reviews" element={<MyReviews />} />
              <Route path="returns" element={<MyReturns />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Suspense>
    </>
  );
}
