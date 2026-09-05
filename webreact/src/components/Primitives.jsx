import { useEffect, useRef } from "react";
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

export function Modal({ title, children, onClose, actions }) {
  const modalRef = useRef(null);
  useEffect(() => {
    const handleKeyDown = (event) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", handleKeyDown);
    modalRef.current?.querySelector("button")?.focus();
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section ref={modalRef} className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header><h2 id="modal-title">{title}</h2><button className="icon-button" aria-label="关闭" onClick={onClose}><Icon name="PhX" /></button></header><div className="modal-body">{children}</div>{actions && <footer>{actions}</footer>}</section></div>;
}
