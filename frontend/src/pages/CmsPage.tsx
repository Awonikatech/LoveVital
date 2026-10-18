import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { storeApi } from "@/services/store";
import { Breadcrumbs, EmptyState, PageSpinner } from "@/components/ui";
import { useSeo } from "@/hooks/useSeo";
import { date } from "@/utils/format";
import { renderMarkdown } from "@/utils/markdown";

export default function CmsPage() {
  const { slug = "" } = useParams();
  const { data, isLoading, isError } = useQuery({ queryKey: ["page", slug], queryFn: () => storeApi.page(slug) });
  useSeo({ title: data?.seo_title ?? data?.title, description: data?.seo_description });
  if (isLoading) return <PageSpinner />;
  if (isError || !data) return <EmptyState title="Page not found" action={<Link to="/" className="link-underline">Back to home</Link>} />;
  return (
    <div className="container-site max-w-3xl py-10">
      <Breadcrumbs items={[{ label: "Home", to: "/" }, { label: data.title }]} />
      <h1 className="mt-6 text-[40px] leading-tight">{data.title}</h1>
      <p className="mt-2 text-sm text-kajal-400">Last updated {date(data.updated_at)}</p>
      <article className="prose-lovevital mt-6" dangerouslySetInnerHTML={{ __html: renderMarkdown(data.body) }} />
    </div>
  );
}
