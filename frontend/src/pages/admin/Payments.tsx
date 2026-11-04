import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Copy, ExternalLink, FlaskConical, ShieldCheck, Zap } from "lucide-react";
import { adminApi, type GatewayMode, type GatewayPayload, type GatewaySettings } from "@/services/admin";
import { FieldGrid, PageHeader, Panel, QueryState, useConfirm } from "@/components/admin/kit";
import { useAdminMutation } from "@/components/admin/hooks";
import { Alert, Badge, Button, Input } from "@/components/ui";
import { useToast } from "@/features/toast";
import { cn } from "@/utils/cn";

const MODES: { id: GatewayMode; label: string; icon: typeof Zap; hint: string }[] = [
  { id: "mock", label: "Simulator", icon: FlaskConical, hint: "No Razorpay page. A local stand-in for development only." },
  { id: "test", label: "Test mode", icon: ShieldCheck, hint: "Real Razorpay checkout with test cards/UPI. No money moves." },
  { id: "live", label: "Live mode", icon: Zap, hint: "Real payments from customers. Needs HTTPS and a webhook." },
];

export default function Payments() {
  const q = useQuery({ queryKey: ["admin", "payment-gateway"], queryFn: adminApi.paymentGateway });
  return (
    <div>
      <PageHeader title="Payments" sub="Razorpay gateway used for card, UPI, net banking and wallet payments at checkout." />
      <QueryState q={q} what="Payment settings">{(s) => <GatewayForm s={s} />}</QueryState>
    </div>
  );
}

function GatewayForm({ s }: { s: GatewaySettings }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [mode, setMode] = useState<GatewayMode>(s.mode);
  const [keyId, setKeyId] = useState(s.key_id);
  const [keySecret, setKeySecret] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setMode(s.mode); setKeyId(s.key_id); setKeySecret(""); setWebhookSecret(""); }, [s]);

  const payload = (): GatewayPayload => ({ mode, key_id: keyId.trim(), key_secret: keySecret || undefined, webhook_secret: webhookSecret || undefined });
  const inv = { invalidate: [["admin", "payment-gateway"], ["settings"]] };
  const save = useAdminMutation(() => adminApi.savePaymentGateway(payload()), { ...inv, success: "Payment settings saved" });
  const test = useAdminMutation(() => adminApi.testPaymentGateway(payload()), { success: (r) => r.message });
  const reset = useAdminMutation(() => adminApi.resetPaymentGateway(), { ...inv, success: "Using the server's .env settings" });

  const real = mode !== "mock";
  const keyChanged = keyId.trim() !== s.key_id;
  const secretKept = real && s.key_secret_set && !keyChanged && s.mode !== "mock";
  const dirty = mode !== s.mode || keyChanged || !!keySecret || !!webhookSecret;

  const validate = () => {
    if (!real) return true;
    if (!keyId.trim().startsWith(`rzp_${mode}_`)) return setErr(`A ${mode}-mode Key ID starts with “rzp_${mode}_”. Copy it from Razorpay Dashboard → Account & Settings → API Keys (with ${mode === "test" ? "Test" : "Live"} mode selected).`), false;
    if (!keySecret && !secretKept) return setErr("Enter the Key Secret shown when you generated this key."), false;
    if (mode === "live" && !webhookSecret && !(s.webhook_secret_set && s.mode !== "mock")) return setErr("Live mode needs a webhook secret."), false;
    setErr(null);
    return true;
  };
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    if (mode === "live" && s.mode !== "live" && !(await confirm({ title: "Switch to live payments?", body: "Customers will be charged real money from now on.", confirmLabel: "Go live" })).ok) return;
    save.mutate(undefined);
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(s.webhook_url); toast("Webhook URL copied", "success"); } catch { /* clipboard blocked */ }
  };

  return (
    <form onSubmit={submit} className="space-y-6">
      <Alert tone={s.mode === "mock" ? "warning" : s.mode === "live" ? "success" : "info"}>
        <span className="flex flex-wrap items-center gap-2">
          Currently active: <Badge tone={s.mode === "live" ? "success" : s.mode === "test" ? "info" : "warning"}>{MODES.find((m) => m.id === s.mode)!.label}</Badge>
          {s.mode !== "mock" && <span className="font-mono text-xs">{s.key_id}</span>}
          <span className="text-kajal-500">· {s.source === "admin" ? "set in this panel" : "from the server's .env file"}</span>
        </span>
        {s.mode === "mock" && <span className="mt-1 block">Checkout does not open Razorpay in this mode. Switch to Test or Live to take card and UPI payments through Razorpay.</span>}
      </Alert>

      <Panel title="Gateway mode">
        <div role="radiogroup" aria-label="Gateway mode" className="grid gap-3 sm:grid-cols-3">
          {MODES.filter((m) => m.id !== "mock" || !s.production).map((m) => (
            <label key={m.id} className={cn("flex cursor-pointer flex-col gap-1 rounded-xl border p-4 text-sm transition", mode === m.id ? "border-kajal bg-white ring-1 ring-kajal" : "border-kajal-300/50 hover:border-gold-500")}>
              <input type="radio" name="gateway-mode" value={m.id} checked={mode === m.id} onChange={() => { setMode(m.id); setErr(null); }} className="sr-only" />
              <span className="flex items-center gap-2 font-medium"><m.icon className="h-4 w-4 text-gold-600" />{m.label}</span>
              <span className="text-xs text-kajal-400">{m.hint}</span>
            </label>
          ))}
        </div>
      </Panel>

      {real && (
        <Panel title="Razorpay API keys" action={<a href="https://dashboard.razorpay.com/app/website-app-settings/api-keys" target="_blank" rel="noreferrer" className="link-underline inline-flex items-center gap-1 text-sm">Get keys <ExternalLink className="h-3.5 w-3.5" /></a>}>
          <FieldGrid>
            <Input label="Key ID" value={keyId} onChange={(e) => setKeyId(e.target.value)} placeholder={`rzp_${mode}_xxxxxxxxxxxxxx`} autoComplete="off" spellCheck={false} />
            <Input label="Key Secret" type="password" value={keySecret} onChange={(e) => setKeySecret(e.target.value)} autoComplete="new-password"
              placeholder={secretKept ? `Saved ${s.key_secret_hint ?? ""}` : "Paste the key secret"}
              hint={secretKept ? "Leave blank to keep the saved secret." : "Shown once by Razorpay when you generate the key."} />
          </FieldGrid>
          <p className="mt-3 text-xs text-kajal-400">Secrets are encrypted before they are stored and are never shown again. Keys are checked with Razorpay before saving.</p>
        </Panel>
      )}

      {real && (
        <Panel title="Webhook">
          <p className="text-sm text-kajal-700">Webhooks confirm payments even if the customer closes the page before returning. In Razorpay Dashboard → Webhooks, add:</p>
          <div className="mt-3 flex items-center gap-2 rounded-xl border border-gold-200/60 bg-ivory-50 px-3 py-2">
            <code className="min-w-0 flex-1 truncate text-sm">{s.webhook_url}</code>
            <button type="button" onClick={copy} aria-label="Copy webhook URL" className="rounded p-1.5 text-kajal-500 hover:text-kajal"><Copy className="h-4 w-4" /></button>
          </div>
          <p className="mt-2 text-xs text-kajal-400">Active events: {s.webhook_events.join(", ")}. The URL must be publicly reachable over HTTPS (not localhost).</p>
          <div className="mt-4 max-w-md">
            <Input label={`Webhook secret${mode === "live" ? "" : " (optional in test mode)"}`} type="password" value={webhookSecret} onChange={(e) => setWebhookSecret(e.target.value)} autoComplete="new-password"
              placeholder={s.webhook_secret_set && s.mode !== "mock" ? `Saved ${s.webhook_secret_hint ?? ""}` : "The secret you typed when creating the webhook"}
              hint={s.webhook_secret_set && s.mode !== "mock" ? "Leave blank to keep the saved secret." : undefined} />
          </div>
        </Panel>
      )}

      {mode === "test" && (
        <Alert>Test payments: card <span className="font-mono">4111 1111 1111 1111</span>, any future expiry and CVV; UPI <span className="font-mono">success@razorpay</span> or <span className="font-mono">failure@razorpay</span>.</Alert>
      )}

      <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center justify-end gap-3 border-t border-gold-200/60 bg-ivory/95 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-2xl sm:border">
        {err && <p role="alert" className="mr-auto text-sm text-kumkum">{err}</p>}
        {s.source === "admin" && (
          <Button variant="ghost" size="sm" loading={reset.isPending} disabled={save.isPending}
            onClick={async () => { if ((await confirm({ title: "Use the server's .env settings?", body: "The keys saved here will be removed.", confirmLabel: "Reset", danger: true })).ok) reset.mutate(undefined); }}>
            Reset to .env
          </Button>
        )}
        {real && <Button variant="outline" size="sm" loading={test.isPending} onClick={() => { if (validate()) test.mutate(undefined); }}>Test connection</Button>}
        <Button type="submit" size="sm" disabled={!dirty} loading={save.isPending}>Save</Button>
      </div>
    </form>
  );
}
