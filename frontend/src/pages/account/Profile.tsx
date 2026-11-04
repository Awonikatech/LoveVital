import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Alert, Button, Input } from "@/components/ui";
import { useAuth } from "@/features/auth";
import { useToast } from "@/features/toast";
import { storeApi } from "@/services/store";
import { errorMessage } from "@/services/api";
import { passwordRule } from "@/pages/auth/Register";
import { PHONE_RE } from "@/utils/india";
import { useSeo } from "@/hooks/useSeo";

export default function Profile() {
  useSeo({ title: "Profile", noindex: true });
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [sp] = useSearchParams();
  const [name, setName] = useState(user?.full_name ?? "");
  const [phone, setPhone] = useState(user?.phone ?? "");
  const [pErr, setPErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [pw, setPw] = useState({ current: "", next: "" });
  const [pwErr, setPwErr] = useState<string | null>(null);
  const [pwBusy, setPwBusy] = useState(false);
  if (!user) return null;
  return (
    <div className="space-y-8">
      {sp.get("welcome") && <Alert tone="success">Welcome to LoveVital! Use code <strong>WELCOME15</strong> for 15% off your first order.</Alert>}
      {!user.email_verified_at && (
        <Alert tone="warning">Please verify {user.email} to secure your account.{" "}
          <button className="underline" onClick={async () => { try { toast((await storeApi.resendVerification()).message); } catch (e) { toast(errorMessage(e), "error"); } }}>Resend verification email</button>
        </Alert>
      )}
      <section className="card p-6">
        <h2 className="text-2xl">Personal details</h2>
        <form className="mt-5 grid max-w-xl gap-4 sm:grid-cols-2" onSubmit={async (e) => {
          e.preventDefault();
          if (phone && !PHONE_RE.test(phone)) { setPErr("Enter a valid 10-digit mobile number"); return; }
          setSaving(true); setPErr(null);
          try { setUser(await storeApi.updateMe({ full_name: name, phone: phone || null })); toast("Profile updated"); } catch (ex) { setPErr(errorMessage(ex)); } finally { setSaving(false); }
        }}>
          <Input label="Full name" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
          <Input label="Mobile number" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} error={pErr ?? undefined} />
          <Input className="sm:col-span-2" label="Email" value={user.email} disabled hint={user.email_verified_at ? "Verified" : "Not verified yet"} />
          <div><Button type="submit" loading={saving}>Save details</Button></div>
        </form>
      </section>
      <section className="card p-6">
        <h2 className="text-2xl">Change password</h2>
        <form className="mt-5 grid max-w-xl gap-4 sm:grid-cols-2" onSubmit={async (e) => {
          e.preventDefault();
          const c = passwordRule.safeParse(pw.next);
          if (!c.success) { setPwErr(c.error.issues[0].message); return; }
          setPwBusy(true); setPwErr(null);
          try { await storeApi.changePassword(pw.current, pw.next); setPw({ current: "", next: "" }); toast("Password changed"); } catch (ex) { setPwErr(errorMessage(ex)); } finally { setPwBusy(false); }
        }}>
          {pwErr && <Alert tone="error" className="sm:col-span-2">{pwErr}</Alert>}
          <Input label="Current password" type="password" autoComplete="current-password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} required />
          <Input label="New password" type="password" autoComplete="new-password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} required hint="8+ characters with a letter and a number" />
          <div><Button type="submit" variant="outline" loading={pwBusy}>Update password</Button></div>
        </form>
      </section>
    </div>
  );
}
