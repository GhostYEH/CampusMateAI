import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { Icon } from "./Icon.jsx";

export function PageFrame({ eyebrow, title, description, actions, children, className = "", showHeading = true }) {
  return <main id="main-content" className={`page-frame ${className}`}>{showHeading && <header className="page-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>{description && <p>{description}</p>}</div>{actions && <div className="page-actions">{actions}</div>}</header>}{children}</main>;
}

export function Panel({ children, className = "", as: Tag = "section" }) { return <Tag className={`panel ${className}`}>{children}</Tag>; }

export function SectionHeading({ title, detail, action }) { return <div className="section-heading"><div><h2>{title}</h2>{detail && <p>{detail}</p>}</div>{action}</div>; }

export function BackLink({ to = "/home", children = "返回上一页" }) { return <Link className="back-link" to={to}><Icon name="PhArrowLeft" size={16} />{children}</Link>; }

export function Button({ children, variant = "primary", icon, className = "", ...props }) { return <button className={`button button-${variant} ${className}`} {...props}>{icon && <Icon name={icon} size={17} />}{children}</button>; }

export function LinkButton({ children, to, variant = "secondary", icon, className = "", ...props }) { return <Link className={`button button-${variant} ${className}`} to={to} {...props}>{icon && <Icon name={icon} size={17} />}{children}</Link>; }

export function AsyncState({ loading, error, empty, onRetry, children }) {
  if (loading) return <div className="state-card loading-state" aria-busy="true"><span className="loading-orb" /><p>正在加载内容…</p></div>;
  if (error) return <div className="state-card error-state" role="alert"><Icon name="PhWarningCircle" size={24} /><p>{error}</p>{onRetry && <Button variant="secondary" onClick={onRetry}>重试</Button>}</div>;
  if (empty) return <div className="state-card empty-state"><Icon name="PhStack" size={34} /><p>{empty}</p></div>;
  return children;
}

export function StatCard({ label, value, detail, icon, tone = "blue" }) { return <article className={`stat-card tone-${tone}`}><span className="stat-icon"><Icon name={icon} size={22} /></span><div><span>{label}</span><strong>{value}</strong><small>{detail}</small></div></article>; }

export function Modal({ title, children, onClose, actions, variant = "", className = "" }) {
  const modalRef = useRef(null);
  const previouslyFocusedRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    previouslyFocusedRef.current = document.activeElement;
    const handleKeyDown = (event) => {
      if (event.key === "Escape") { event.stopPropagation(); onCloseRef.current(); return; }
      if (event.key !== "Tab") return;
      const root = modalRef.current;
      if (!root) return;
      const focusables = root.querySelectorAll('button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])');
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", handleKeyDown);
    const focusables = modalRef.current?.querySelectorAll('button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])');
    const autoFocusEl = modalRef.current?.querySelector("[autoFocus], [autofocus], [data-autofocus]");
    if (autoFocusEl && typeof autoFocusEl.focus === "function") { autoFocusEl.focus(); }
    else if (focusables && focusables.length) { focusables[0].focus(); }
    const prevOverflow = document.body.style.overflow;
    const prevHtmlOverflow = document.documentElement.style.overflow;
    const prevScrollbarGutter = document.documentElement.style.scrollbarGutter;
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    document.documentElement.style.scrollbarGutter = "auto";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = prevOverflow;
      document.documentElement.style.overflow = prevHtmlOverflow;
      document.documentElement.style.scrollbarGutter = prevScrollbarGutter;
      if (previouslyFocusedRef.current && typeof previouslyFocusedRef.current.focus === "function") {
        try { previouslyFocusedRef.current.focus(); } catch {}
      }
    };
  }, []);
  const variantClass = variant ? `modal--${variant}` : "";
  const extraClass = className ? ` ${className}` : "";
  return createPortal(<div className={`modal-backdrop ${variantClass}`.trim()} role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section ref={modalRef} className={`modal ${variantClass}${extraClass}`.trim()} role="dialog" aria-modal="true" aria-labelledby="modal-title"><header><h2 id="modal-title">{title}</h2><button className="icon-button" aria-label="关闭" onClick={onClose}><Icon name="PhX" /></button></header><div className="modal-body">{children}</div>{actions && <footer>{actions}</footer>}</section></div>, document.body);
}
