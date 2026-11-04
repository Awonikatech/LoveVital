/** Minimal, safe Markdown → HTML for CMS pages (headings, lists, bold/italic, links, paragraphs).
 *  All text is HTML-escaped first; only https/relative links are allowed. */
function esc(s: string) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function inline(s: string) {
  return esc(s)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\(((?:https:\/\/|\/)[^)\s]*)\)/g, '<a href="$2">$1</a>');
}
export function renderMarkdown(md: string): string {
  const out: string[] = [];
  let list: string[] | null = null;
  const flush = () => { if (list) { out.push(`<ul>${list.join("")}</ul>`); list = null; } };
  for (const raw of md.split(/\r?\n/)) {
    const line = raw.trimEnd();
    if (/^###\s+/.test(line)) { flush(); out.push(`<h3>${inline(line.replace(/^###\s+/, ""))}</h3>`); }
    else if (/^##\s+/.test(line)) { flush(); out.push(`<h2>${inline(line.replace(/^##\s+/, ""))}</h2>`); }
    else if (/^#\s+/.test(line)) { flush(); out.push(`<h2>${inline(line.replace(/^#\s+/, ""))}</h2>`); }
    else if (/^[-*]\s+/.test(line)) { list = list ?? []; list.push(`<li>${inline(line.replace(/^[-*]\s+/, ""))}</li>`); }
    else if (!line.trim()) { flush(); }
    else { flush(); out.push(`<p>${inline(line)}</p>`); }
  }
  flush();
  return out.join("\n");
}
