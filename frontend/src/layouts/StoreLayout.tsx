import { Outlet } from "react-router-dom";
import { Suspense } from "react";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { CartDrawer } from "@/components/layout/CartDrawer";
import { PageSpinner } from "@/components/ui";

export default function StoreLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[200] focus:rounded-full focus:bg-kajal focus:px-4 focus:py-2 focus:text-ivory">Skip to content</a>
      <Header />
      <main id="main" className="flex-1">
        <Suspense fallback={<PageSpinner />}><Outlet /></Suspense>
      </main>
      <Footer />
      <CartDrawer />
    </div>
  );
}
