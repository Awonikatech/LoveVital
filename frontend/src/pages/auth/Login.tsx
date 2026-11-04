import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff } from "lucide-react";
import { Alert, Button, Input } from "@/components/ui";
import { useAuth } from "@/features/auth";
import { errorMessage } from "@/services/api";
import { useSeo } from "@/hooks/useSeo";
import { AuthShell } from "./AuthShell";

const schema = z.object({ email: z.string().email("Enter a valid email address"), password: z.string().min(1, "Enter your password") });

export function safeNext(next: string | null, fallback = "/account") {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : fallback;
}

export default function Login() {
  useSeo({ title: "Log in", noindex: true });
  const { login } = useAuth();
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const [err, setErr] = useState<string | null>(null);
  const [show, setShow] = useState(false);
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const onSubmit = form.handleSubmit(async (v) => {
    setErr(null);
    try {
      const u = await login(v.email, v.password);
      const isStaff = u.roles.includes("admin") || u.roles.includes("staff");
      nav(safeNext(sp.get("next"), isStaff ? "/admin" : "/account"), { replace: true });
    } catch (e) {
      setErr(errorMessage(e));
    }
  });
  return (
    <AuthShell title="Welcome back" sub="Log in to track orders, save addresses and check out faster.">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {err && <Alert tone="error">{err}</Alert>}
        <Input label="Email" type="email" autoComplete="email" {...form.register("email")} error={form.formState.errors.email?.message} />
        <div className="relative">
          <Input label="Password" type={show ? "text" : "password"} autoComplete="current-password" {...form.register("password")} error={form.formState.errors.password?.message} />
          <button type="button" onClick={() => setShow(!show)} className="absolute right-3 top-[38px] p-1 text-kajal-400" aria-label={show ? "Hide password" : "Show password"}>{show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button>
        </div>
        <div className="text-right"><Link to="/forgot-password" className="text-sm link-underline">Forgot password?</Link></div>
        <Button type="submit" block size="lg" loading={form.formState.isSubmitting}>Log in</Button>
      </form>
      <p className="mt-6 text-center text-[15px] text-kajal-500">New to LoveVital? <Link to={`/register${sp.get("next") ? `?next=${encodeURIComponent(sp.get("next")!)}` : ""}`} className="link-underline text-kajal">Create an account</Link></p>
    </AuthShell>
  );
}
