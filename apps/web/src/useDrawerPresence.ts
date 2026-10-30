import { useEffect, useState } from "react";

// Keep the panel mounted until the transform-only exit finishes.
export function useDrawerPresence<T>(value: T | null | undefined) {
  const [retained, setRetained] = useState<T | null>(value ?? null);
  useEffect(() => {
    if (value != null) {
      setRetained(value);
      return;
    }
    const duration = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 280;
    const timer = window.setTimeout(() => setRetained(null), duration);
    return () => window.clearTimeout(timer);
  }, [value]);
  return { value: value ?? retained, closing: value == null && retained != null };
}
