// Shared UI primitives: Avatar, AvatarStack, Modal, Spinner, and a toast
// system. Markup/classes mirror the prototype so the reused CSS applies.

import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { Icon } from './icons.jsx';

// ── Avatar ──
export function Avatar({ person, size = 28, ring = false, title }) {
  const p = person || { init: '?', bg: '#8A99B0', name: '' };
  return (
    <div
      className="avatar"
      title={title ?? p.name}
      style={{
        width: size,
        height: size,
        background: p.bg,
        fontSize: size * 0.38,
        ...(ring ? { boxShadow: `0 0 0 2px #fff,0 0 0 4px ${p.bg}40` } : null),
      }}
    >
      {p.init}
    </div>
  );
}

export function AvatarStack({ people, size = 26 }) {
  return (
    <div className="avatars">
      {people.filter(Boolean).map((p, i) => (
        <Avatar key={i} person={p} size={size} />
      ))}
    </div>
  );
}

// ── Modal ──
export function Modal({ open, onClose, title, children, footer, maxWidth, className = '', titleColor }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === 'Escape' && onClose?.();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="overlay open" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className={`modal ${className}`} style={maxWidth ? { maxWidth } : undefined}>
        <div className="modal-head">
          <h3 style={titleColor ? { color: titleColor } : undefined}>{title}</h3>
          <button className="btn-ghost" onClick={onClose} aria-label="Close">
            <Icon name="x" stroke="currentColor" />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function Spinner() {
  return <div className="spinner" />;
}

// ── Toasts ──
const ToastCtx = createContext(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const toast = useCallback((msg, type = 'info') => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, msg, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);
  return (
    <ToastCtx.Provider value={toast}>
      {children}
      <div id="toasts">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.type}`}>
            <Icon name={t.type === 'success' ? 'check' : 'info'} />
            <span>{t.msg}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
