import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AdminLayout from "@/components/admin/AdminLayout";
import { NoAccess } from "@/components/admin/kit";
import { PageSpinner } from "@/components/ui";
import { useAuth } from "@/features/auth";

const Dashboard = lazy(() => import("./Dashboard"));
const Products = lazy(() => import("./Products"));
const ProductEditor = lazy(() => import("./ProductEditor"));
const Categories = lazy(() => import("./Categories"));
const Collections = lazy(() => import("./Collections"));
const Inventory = lazy(() => import("./Inventory"));
const Orders = lazy(() => import("./Orders"));
const OrderDetail = lazy(() => import("./OrderDetail"));
const Customers = lazy(() => import("./Customers"));
const CustomerDetail = lazy(() => import("./CustomerDetail"));
const Coupons = lazy(() => import("./Coupons"));
const Shipping = lazy(() => import("./Shipping"));
const Returns = lazy(() => import("./Returns"));
const Content = lazy(() => import("./Content"));
const Reports = lazy(() => import("./Reports"));
const AuditLog = lazy(() => import("./AuditLog"));

function Guard({ perm, what, children }: { perm: string; what: string; children: ReactNode }) {
  const { can } = useAuth();
  return can(perm) ? <>{children}</> : <NoAccess what={what} />;
}

export default function AdminApp() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route index element={<S><Guard perm="dashboard:view" what="The dashboard"><Dashboard /></Guard></S>} />
        <Route path="products" element={<S><Guard perm="products:read" what="Products"><Products /></Guard></S>} />
        <Route path="products/new" element={<S><Guard perm="products:write" what="Creating products"><ProductEditor /></Guard></S>} />
        <Route path="products/:id" element={<S><Guard perm="products:read" what="Products"><ProductEditor /></Guard></S>} />
        <Route path="categories" element={<S><Guard perm="products:read" what="Categories"><Categories /></Guard></S>} />
        <Route path="collections" element={<S><Guard perm="products:read" what="Collections"><Collections /></Guard></S>} />
        <Route path="inventory" element={<S><Guard perm="inventory:read" what="Inventory"><Inventory /></Guard></S>} />
        <Route path="orders" element={<S><Guard perm="orders:read" what="Orders"><Orders /></Guard></S>} />
        <Route path="orders/:id" element={<S><Guard perm="orders:read" what="Orders"><OrderDetail /></Guard></S>} />
        <Route path="customers" element={<S><Guard perm="customers:read" what="Customers"><Customers /></Guard></S>} />
        <Route path="customers/:id" element={<S><Guard perm="customers:read" what="Customers"><CustomerDetail /></Guard></S>} />
        <Route path="coupons" element={<S><Guard perm="coupons:read" what="Coupons and promotions"><Coupons /></Guard></S>} />
        <Route path="shipping" element={<S><Guard perm="shipping:read" what="Shipping"><Shipping /></Guard></S>} />
        <Route path="returns" element={<S><Guard perm="returns:read" what="Returns"><Returns /></Guard></S>} />
        <Route path="content" element={<S><Guard perm="content:write" what="Content and settings"><Content /></Guard></S>} />
        <Route path="reports" element={<S><Guard perm="reports:view" what="Reports"><Reports /></Guard></S>} />
        <Route path="audit" element={<S><Guard perm="audit:read" what="The audit log"><AuditLog /></Guard></S>} />
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Route>
    </Routes>
  );
}

function S({ children }: { children: ReactNode }) {
  return <Suspense fallback={<PageSpinner />}>{children}</Suspense>;
}
