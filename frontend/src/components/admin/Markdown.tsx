import type { ReactNode } from "react";

/** Minimal, safe markdown preview (headings, lists, bold/italic, links, paragraphs). Builds React nodes — never raw HTML. */
function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)\s]+\))/g;
  let last = 0, m: RegExpExecArray | null, i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const t = m[0];
    if (t.startsWith("**")) out.push(<strong key={`${key}-${i++}`}>{t.slice(2, -2)}</strong>);
    else if (t.startsWith("*")) out.push(<em key={`${key}-${i++}`}>{t.slice(1, -1)}</em>);
    else {
      const lm = t.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/)!;
      const href = /^(https?:\/\/|\/|mailto:|tel:)/.test(lm[2]) ? lm[2] : "#";
      out.push(<a key={`${key}-${i++}`} href={href} target="_blank" rel="noreferrer">{lm[1]}</a>);
    }
    last = m.index + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function MarkdownPreview({ source }: { source: string }) {
  const blocks: ReactNode[] = [];
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  let para: string[] = [];
  type List = { ordered: boolean; items: string[] };
  let list: List | null = null;
  const flush = () => {
    if (para.length) { blocks.push(<p key={`p${blocks.length}`}>{inline(para.join(" "), `p${blocks.length}`)}</p>); para = []; }
    if (list) {
      const items = list.items.map((it, j) => <li key={j}>{inline(it, `l${blocks.length}-${j}`)}</li>);
      blocks.push(list.ordered ? <ol key={`l${blocks.length}`} className="my-3 list-decimal pl-5">{items}</ol> : <ul key={`l${blocks.length}`}>{items}</ul>);
      list = null;
    }
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    const ul = line.match(/^\s*[-*]\s+(.*)$/);
    const ol = line.match(/^\s*\d+\.\s+(.*)$/);
    if (!line.trim()) { flush(); continue; }
    if (h) { flush(); const lvl = h[1].length; const k = `h${blocks.length}`; blocks.push(lvl <= 2 ? <h2 key={k}>{inline(h[2], k)}</h2> : <h3 key={k}>{inline(h[2], k)}</h3>); continue; }
    if (ul || ol) {
      if (para.length) { const l: List | null = list; list = null; flush(); list = l; }
      const ordered = !!ol;
      if (list && list.ordered !== ordered) flush();
      if (!list) list = { ordered, items: [] };
      list.items.push((ul ?? ol)![1]);
      continue;
    }
    if (list) flush();
    para.push(line.trim());
  }
  flush();
  return <div className="prose-lovevital text-[15px]">{blocks.length ? blocks : <p className="text-kajal-400">Nothing to preview yet.</p>}</div>;
}
