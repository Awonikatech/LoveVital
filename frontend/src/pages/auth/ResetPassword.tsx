import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Alert, Button, Input } from "@/components/ui";
import { storeApi } from "@/services/store";
import { errorMessage } from "@/services/api";
import { useSeo } from "@/hooks/useSeo";
import { AuthShell } from "./AuthShell";
import { passwordRule } from "./Register";

export default function ResetPassword() {
  useSeo({ title: "Set a new password", noindex: true });
  const [sp] = useSearchParams();
  const token = sp.get("token") ?? "";
  const nav = useNavigate();
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (!token) return <AuthShell title="Link missing"><Alert tone="error">This reset link is incomplete. <Link to="/forgot-password" className="underline">Request a new one</Link>.</Alert></AuthShell>;
  return (
    <AuthShell title="Set a new password">
      <form className="space-y-4" onSubmit={async (e) => {
        e.preventDefault();
        const check = passwordRule.safeParse(pw);
        if (!check.success) { setErr(check.error.issues[0].message); return; }
        if (pw !== confirm) { setErr("Passwords don't match"); return; }
        setBusy(true); setErr(null);
        try { await storeApi.reset(token, pw); nav("/login?reset=1", { replace: true }); } catch (ex) { setErr(errorMessage(ex)); } finally { setBusy(false); }
      }}>
        {err && <Alert tone="error">{err}</Alert>}
        <Input label="New password" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} hint="8+ characters with a letter and a number" />
        <Input label="Confirm new password" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        <Button type="submit" block size="lg" loading={busy}>Update password</Button>
      </form>
    </AuthShell>
  );
}
