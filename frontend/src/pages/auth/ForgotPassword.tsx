import { useState } from "react";
import { Link } from "react-router-dom";
import { Alert, Button, Input } from "@/components/ui";
import { storeApi } from "@/services/store";
import { errorMessage } from "@/services/api";
import { useSeo } from "@/hooks/useSeo";
import { AuthShell } from "./AuthShell";

export default function ForgotPassword() {
  useSeo({ title: "Reset your password", noindex: true });
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState<{ ok?: string; err?: string }>({});
  const [busy, setBusy] = useState(false);
  return (
    <AuthShell title="Forgot your password?" sub="Enter your email and we'll send you a link to set a new one.">
      <form className="space-y-4" onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true); setMsg({});
        try { setMsg({ ok: (await storeApi.forgot(email)).message }); } catch (err) { setMsg({ err: errorMessage(err) }); } finally { setBusy(false); }
      }}>
        {msg.ok && <Alert tone="success">{msg.ok} In this demo, emails are printed to the API server log.</Alert>}
        {msg.err && <Alert tone="error">{msg.err}</Alert>}
        <Input label="Email" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <Button type="submit" block size="lg" loading={busy}>Send reset link</Button>
      </form>
      <p className="mt-6 text-center text-[15px]"><Link to="/login" className="link-underline">Back to log in</Link></p>
    </AuthShell>
  );
}
