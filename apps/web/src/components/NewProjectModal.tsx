import { useEffect, useState, type ReactNode } from "react";
import { X } from "lucide-react";

export default function NewProjectModal({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  const [mounted, setMounted] = useState(open);
  useEffect(() => {
    if (open) {
      setMounted(true);
      return;
    }
    // Keep the dialog mounted until its exit animation finishes.
    const fallback = window.setTimeout(() => setMounted(false), 320);
    return () => window.clearTimeout(fallback);
  }, [open]);
  if (!mounted) return null;
  return (
    <div
      className={
        "modal-backdrop new-project-backdrop " +
        (open ? "is-open" : "is-closing")
      }
      onClick={onClose}
    >
      <section
        className="modal new-project-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-project-title"
        onClick={(event) => event.stopPropagation()}
        onAnimationEnd={(event) => {
          if (event.target === event.currentTarget && !open) setMounted(false);
        }}
      >
        <button
          type="button"
          className="close new-project-close"
          aria-label="Close new project"
          onClick={onClose}
        >
          <X size={20} />
        </button>
        <div className="new-project-scroll">{children}</div>
      </section>
    </div>
  );
}
