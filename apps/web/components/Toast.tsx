"use client";

import { useEffect } from "react";
import { AlertIcon, CheckIcon, XIcon } from "./icons";

export type ToastState = { message: string; kind: "ok" | "err" } | null;

export function Toast({
  state,
  onClose,
}: {
  state: ToastState;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!state) return;
    const timer = setTimeout(onClose, 4200);
    return () => clearTimeout(timer);
  }, [state, onClose]);

  if (!state) return null;
  return (
    <div className={`toast ${state.kind}`}>
      {state.kind === "ok" ? (
        <CheckIcon size={17} style={{ color: "var(--ok)" }} />
      ) : (
        <AlertIcon size={17} style={{ color: "var(--danger)" }} />
      )}
      <span>{state.message}</span>
      <button
        onClick={onClose}
        className="btn-icon"
        style={{ width: 26, height: 26, border: 0, background: "transparent" }}
        aria-label="إغلاق"
      >
        <XIcon size={14} />
      </button>
    </div>
  );
}
