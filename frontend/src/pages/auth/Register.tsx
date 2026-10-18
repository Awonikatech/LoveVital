import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Alert, Button, Checkbox, Input } from "@/components/ui";
import { useAuth } from "@/features/auth";
import { errorMessage } from "@/services/api";
import { useSeo } from "@/hooks/useSeo";
import { PHONE_RE } from "@/utils/india";
import { AuthShell } from "./AuthShell";
import { safeNext } from "./Login";

export const passwordRule = z.string().min(8, "Use at least 8 characters").max(128).regex(/[A-Za-z]/, "Include at least one letter").regex(/\d/, "Include at least one number");
const schema = z.object({
  full_name: z.string().trim().min(2, "Enter your full name"),
  email: z.string().email("Enter a valid email address"),
  phone: z.string().trim().regex(PHONE_RE, "Enter a valid 10-digit mobile number").optional().or(z.literal("")),
  password: passwordRule,
  confirm: z.string(),
  terms: z.literal(true, { errorMap: () => ({ message: "Please accept the terms to continue" }) }),
}).refine((v) => v.password === v.confirm, { path: ["confirm"], message: "Passwords don't match" });

export default function Register() {
  useSeo({ title: "Create account", noindex: true });
  const { register: signup } = useAuth();
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const [err, setErr] = useState<string | null>(null);
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const e = form.formState.errors;
  return (
    <AuthShell title="Create your account" sub="Members get early access to new drops and 15% off their first order." image="/static/tiles/heritage-gold.svg">
      <form noValidate className="space-y-4" onSubmit={form.handleSubmit(async (v) => {
        setErr(null);
        try {
          await signup({ full_name: v.full_name, email: v.email, password: v.password, phone: v.phone || undefined });
          nav(safeNext(sp.get("next"), "/account/profile?welcome=1"), { replace: true });
        } catch (ex) { setErr(errorMessage(ex)); }
      })}>
        {err && <Alert tone="error">{err} {err.includes("exists") && <Link to="/login" className="underline">Log in instead</Link>}</Alert>}
        <Input label="Full name" autoComplete="name" {...form.register("full_name")} error={e.full_name?.message} />
        <Input label="Email" type="email" autoComplete="email" {...form.register("email")} error={e.email?.message} />
        <Input label="Mobile number (optional)" type="tel" autoComplete="tel-national" {...form.register("phone")} error={e.phone?.message} hint="For delivery updates only." />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Password" type="password" autoComplete="new-password" {...form.register("password")} error={e.password?.message} hint="8+ characters with a letter and a number" />
          <Input label="Confirm password" type="password" autoComplete="new-password" {...form.register("confirm")} error={e.confirm?.message} />
        </div>
        <div>
          <Checkbox label={<>I agree to the <Link to="/pages/terms" className="link-underline">terms</Link> and <Link to="/pages/privacy-policy" className="link-underline">privacy policy</Link></>} {...form.register("terms")} />
          {e.terms && <p className="field-error">{e.terms.message}</p>}
        </div>
        <Button type="submit" block size="lg" loading={form.formState.isSubmitting}>Create account</Button>
      </form>
      <p className="mt-6 text-center text-[15px] text-kajal-500">Already have an account? <Link to="/login" className="link-underline text-kajal">Log in</Link></p>
    </AuthShell>
  );
}
