import DOMPurify from "dompurify";
import { marked } from "marked";

if (DOMPurify.isSupported) {
  DOMPurify.addHook("afterSanitizeAttributes", (node) => {
    if (node.tagName === "A" && node.hasAttribute("href")) {
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer");
    }
  });
}

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

/** Sanitize at the final rendering boundary, including SVG/MathML link attributes. */
export function sanitizeHtml(value, { htmlOnly = false } = {}) {
  const html = String(value ?? "");
  // Node rendering and unsupported DOM implementations must never return raw HTML.
  if (!DOMPurify.isSupported) return escapeHtml(html);
  return DOMPurify.sanitize(html, {
    USE_PROFILES: htmlOnly ? { html: true } : { html: true, svg: true, mathMl: true },
    FORBID_TAGS: ["style", "iframe", "object", "embed", "form", "link", "meta"],
    FORBID_ATTR: ["target"],
  });
}

export function renderSafeMarkdown(value) {
  return sanitizeHtml(marked.parse(String(value ?? ""), { breaks: true, gfm: true }), { htmlOnly: true });
}
