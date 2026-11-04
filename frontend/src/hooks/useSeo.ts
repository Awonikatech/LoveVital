import { useEffect } from "react";

interface Seo {
  title?: string;
  description?: string | null;
  canonical?: string;
  jsonLd?: object | null;
  noindex?: boolean;
}

function setMeta(name: string, content: string, attr: "name" | "property" = "name") {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${name}"]`);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, name);
    document.head.appendChild(el);
  }
  el.content = content;
}

/** Sets title, description, Open Graph tags and optional JSON-LD structured data for the current page. */
export function useSeo({ title, description, canonical, jsonLd, noindex }: Seo) {
  useEffect(() => {
    const full = title ? (title.includes("LoveVital") ? title : `${title} | LoveVital`) : "LoveVital — Fine Artificial Jewellery & Couture";
    document.title = full;
    setMeta("og:title", full, "property");
    if (description) {
      setMeta("description", description);
      setMeta("og:description", description, "property");
    }
    setMeta("robots", noindex ? "noindex,nofollow" : "index,follow");
    let link = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!link) {
      link = document.createElement("link");
      link.rel = "canonical";
      document.head.appendChild(link);
    }
    link.href = canonical ?? window.location.origin + window.location.pathname;
    let script: HTMLScriptElement | null = null;
    if (jsonLd) {
      script = document.createElement("script");
      script.type = "application/ld+json";
      script.dataset.seo = "1";
      script.text = JSON.stringify(jsonLd);
      document.head.appendChild(script);
    }
    return () => {
      script?.remove();
    };
  }, [title, description, canonical, noindex, jsonLd ? JSON.stringify(jsonLd) : ""]);
}
