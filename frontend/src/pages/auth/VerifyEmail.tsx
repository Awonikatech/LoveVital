import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Alert, Spinner } from "@/components/ui";
import { storeApi } from "@/services/store";
import { errorMessage } from "@/services/api";
import { useSeo } from "@/hooks/useSeo";
import { AuthShell } from "./AuthShell";

export default function VerifyEmail() {
  useSeo({ title: "Verify email", noindex: true });
  const [sp] = useSearchParams();
  const [state, setState] = useState<{ ok?: string; err?: string }>({});
  useEffect(() => {
    const t = sp.get("token");
    if (!t) { setState({ err: "This verification link is incomplete." }); return; }
    storeApi.verifyEmail(t).then((r) => setState({ ok: r.message })).catch((e) => setState({ err: errorMessage(e) }));
  }, [sp]);
  return (
    <AuthShell title="Email verification">
      {!state.ok && !state.err && <Spinner />}
      {state.ok && <Alert tone="success">{state.ok}</Alert>}
      {state.err && <Alert tone="error">{state.err}</Alert>}
      <p className="mt-6"><Link to="/account" className="link-underline">Go to my account</Link></p>
    </AuthShell>
  );
}
