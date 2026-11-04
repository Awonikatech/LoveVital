import { ButtonLink, EmptyState } from "@/components/ui";
import { useSeo } from "@/hooks/useSeo";

export default function NotFound() {
  useSeo({ title: "Page not found", noindex: true });
  return <EmptyState title="We couldn't find that page" body="The link may be old or the piece may have moved." action={<div className="flex gap-3"><ButtonLink to="/">Go home</ButtonLink><ButtonLink to="/new-arrivals" variant="outline">New arrivals</ButtonLink></div>} />;
}
