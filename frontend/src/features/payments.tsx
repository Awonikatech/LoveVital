import { useCallback, useRef, useState } from "react";
import { CreditCard, Landmark, Smartphone, Wallet, ShieldCheck } from "lucide-react";
import { storeApi } from "@/services/store";
import { errorMessage } from "@/services/api";
import { Button, Modal } from "@/components/ui";
import { rupees } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { PaymentOrder } from "@/types";

export type PayResult =
  | { status: "paid"; orderNumber: string; orderKey?: string }
  | { status: "failed"; orderNumber: string; orderKey?: string; message: string }
  | { status: "dismissed"; orderNumber: string; orderKey?: string };

declare global {
  interface Window { Razorpay?: any }
}

function loadRazorpay(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Couldn't load the Razorpay checkout. Check your connection and try again."));
    document.body.appendChild(s);
  });
}

const METHODS = [
  { id: "upi", label: "UPI", icon: Smartphone, hint: "Google Pay, PhonePe, Paytm, BHIM" },
  { id: "card", label: "Card", icon: CreditCard, hint: "Visa, Mastercard, RuPay, Amex" },
  { id: "netbanking", label: "Net banking", icon: Landmark, hint: "All major Indian banks" },
  { id: "wallet", label: "Wallet", icon: Wallet, hint: "Paytm, Mobikwik, Freecharge" },
];

/**
 * Opens payment for an existing order. The browser never decides that an order is paid:
 * success only means "the gateway returned a signature", which the server then verifies.
 */
export function usePayment() {
  const [mock, setMock] = useState<{ po: PaymentOrder; resolve: (r: PayResult) => void; orderKey?: string } | null>(null);
  const [method, setMethod] = useState("upi");
  const [busy, setBusy] = useState(false);
  const settled = useRef(false);

  const finishSuccess = async (po: PaymentOrder, data: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }, orderKey?: string): Promise<PayResult> => {
    try {
      const r = await storeApi.verifyPayment(data);
      return { status: r.status === "paid" ? "paid" : "failed", orderNumber: po.order_number, orderKey: r.order.order_key ?? orderKey, message: "Payment could not be confirmed" } as PayResult;
    } catch (e) {
      return { status: "failed", orderNumber: po.order_number, orderKey, message: errorMessage(e) };
    }
  };

  const pay = useCallback(async (orderRef: string, orderKey?: string): Promise<PayResult> => {
    const po = await storeApi.createPayment(orderRef, orderKey);
    settled.current = false;
    if (po.mode === "mock") {
      return new Promise<PayResult>((resolve) => setMock({ po, resolve, orderKey }));
    }
    await loadRazorpay();
    return new Promise<PayResult>((resolve) => {
      const rzp = new window.Razorpay({
        key: po.key_id,
        amount: po.amount,
        currency: po.currency,
        name: po.name,
        description: po.description,
        order_id: po.razorpay_order_id,
        prefill: po.prefill,
        theme: { color: po.theme_color },
        handler: async (resp: any) => {
          settled.current = true;
          resolve(await finishSuccess(po, resp, orderKey));
        },
        modal: {
          ondismiss: () => { if (!settled.current) resolve({ status: "dismissed", orderNumber: po.order_number, orderKey }); },
        },
      });
      rzp.on("payment.failed", async (resp: any) => {
        settled.current = true;
        const err = resp?.error ?? {};
        try {
          await storeApi.paymentFailed({ razorpay_order_id: po.razorpay_order_id, razorpay_payment_id: err?.metadata?.payment_id, error_code: err.code, error_description: err.description });
        } catch { /* server will reconcile via webhook */ }
        resolve({ status: "failed", orderNumber: po.order_number, orderKey, message: err.description || "Payment failed" });
      });
      rzp.open();
    });
  }, []);

  const simulate = async (outcome: "success" | "failure") => {
    if (!mock) return;
    setBusy(true);
    const { po, resolve, orderKey } = mock;
    try {
      const r = await storeApi.mockCheckout(po.razorpay_order_id, outcome, method);
      if (r.status === "success" && r.razorpay_signature) {
        resolve(await finishSuccess(po, { razorpay_order_id: r.razorpay_order_id, razorpay_payment_id: r.razorpay_payment_id, razorpay_signature: r.razorpay_signature }, orderKey));
      } else {
        await storeApi.paymentFailed({ razorpay_order_id: po.razorpay_order_id, razorpay_payment_id: r.razorpay_payment_id, error_code: r.error?.code, error_description: r.error?.description });
        resolve({ status: "failed", orderNumber: po.order_number, orderKey, message: r.error?.description ?? "Payment failed" });
      }
    } catch (e) {
      resolve({ status: "failed", orderNumber: po.order_number, orderKey, message: errorMessage(e) });
    } finally {
      setBusy(false);
      setMock(null);
    }
  };

  const modal = (
    <Modal open={!!mock} onClose={() => { if (mock && !busy) { mock.resolve({ status: "dismissed", orderNumber: mock.po.order_number, orderKey: mock.orderKey }); setMock(null); } }}
      title="Razorpay test checkout" size="sm"
      footer={mock && (
        <div className="flex w-full flex-col gap-2">
          <Button block size="lg" loading={busy} onClick={() => simulate("success")}>Pay {rupees(mock.po.amount / 100)}</Button>
          <Button block variant="ghost" disabled={busy} onClick={() => simulate("failure")}>Simulate a declined payment</Button>
        </div>
      )}>
      {mock && (
        <div>
          <div className="rounded-2xl bg-kajal p-4 text-ivory">
            <p className="text-sm text-ivory/70">{mock.po.name} · {mock.po.description}</p>
            <p className="mt-1 font-display text-3xl tabular">{rupees(mock.po.amount / 100)}</p>
            <p className="mt-2 text-xs text-gold-200">Mock mode — no real money moves. The server verifies a genuine HMAC signature exactly as in live mode.</p>
          </div>
          <fieldset className="mt-5">
            <legend className="label">Pay using</legend>
            <div className="grid grid-cols-2 gap-2">
              {METHODS.map((m) => (
                <label key={m.id} className={cn("flex cursor-pointer flex-col gap-1 rounded-xl border p-3 text-sm transition", method === m.id ? "border-kajal bg-white ring-1 ring-kajal" : "border-kajal-300/50 hover:border-gold-500")}>
                  <input type="radio" name="mock-method" value={m.id} checked={method === m.id} onChange={() => setMethod(m.id)} className="sr-only" />
                  <span className="flex items-center gap-2 font-medium"><m.icon className="h-4 w-4 text-gold-600" />{m.label}</span>
                  <span className="text-xs text-kajal-400">{m.hint}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <p className="mt-4 flex items-center gap-2 text-xs text-kajal-400"><ShieldCheck className="h-4 w-4" />Order {mock.po.order_number} · Razorpay order {mock.po.razorpay_order_id}</p>
        </div>
      )}
    </Modal>
  );

  return { pay, modal };
}
