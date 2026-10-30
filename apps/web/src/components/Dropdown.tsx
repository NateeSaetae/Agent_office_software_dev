import {
  Children,
  isValidElement,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown, Layers3 } from "lucide-react";
import "./Dropdown.css";

type Props = {
  id?: string;
  value: string;
  disabled?: boolean;
  children: ReactNode;
  onValueChange: (value: string) => void;
  "aria-label"?: string;
  multipleValues?: string[];
  onMultipleChange?: (values: string[]) => void;
};
export default function Dropdown({
  id,
  value,
  disabled,
  children,
  onValueChange,
  "aria-label": label,
  multipleValues,
  onMultipleChange,
}: Props) {
  const uid = useId(),
    trigger = useRef<HTMLButtonElement>(null),
    menu = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false),
    [active, setActive] = useState(0);
  const [position, setPosition] = useState({
    left: 0,
    top: 0,
    width: 0,
    maxHeight: 280,
  });
  const options: { value: string; label: ReactNode }[] = [];
  function collect(nodes: ReactNode) {
    Children.forEach(nodes, (node) => {
      if (!isValidElement<{ value?: string; children?: ReactNode }>(node))
        return;
      if (node.type === "option")
        options.push({
          value: String(node.props.value ?? ""),
          label: node.props.children,
        });
      else if (node.props.children) collect(node.props.children);
    });
  }
  collect(children);
  const selected = options.findIndex((o) => o.value === value);
  useEffect(() => {
    if (!open || disabled) {
      if (disabled) setOpen(false);
      return;
    }
    function place() {
      const anchor = trigger.current!.closest("[data-dropdown-anchor]") ?? trigger.current!;
      const r = anchor.getBoundingClientRect();
      const below = window.innerHeight - r.bottom - 16,
        above = r.top - 16;
      const height = Math.min(280, options.length * 46 + 16);
      const upwards = below < height && above > below;
      const maxHeight = Math.max(60, Math.min(280, upwards ? above : below));
      const width = Math.min(r.width, window.innerWidth - 24);
      setPosition({
        left: Math.max(12, Math.min(r.left, window.innerWidth - width - 12)),
        top: upwards ? r.top - Math.min(height, maxHeight) - 8 : r.bottom + 8,
        width,
        maxHeight,
      });
    }
    function outside(e: PointerEvent) {
      if (
        !trigger.current?.contains(e.target as Node) &&
        !menu.current?.contains(e.target as Node)
      )
        setOpen(false);
    }
    place();
    document.addEventListener("pointerdown", outside);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      document.removeEventListener("pointerdown", outside);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, disabled, options.length]);
  useEffect(() => {
    if (open)
      document
        .getElementById(`${uid}-${active}`)
        ?.scrollIntoView({ block: "nearest" });
  }, [active, open, uid]);
  function choose(index: number) {
    const option = options[index];
    if (option && multipleValues && onMultipleChange) {
      onMultipleChange(
        multipleValues.includes(option.value)
          ? multipleValues.filter((v) => v !== option.value)
          : [...multipleValues, option.value],
      );
      trigger.current?.focus();
      return;
    }
    if (option) onValueChange(option.value);
    setOpen(false);
    trigger.current?.focus();
  }
  return (
    <>
      <button
        ref={trigger}
        id={id}
        type="button"
        className="modern-dropdown-trigger"
        role="combobox"
        aria-label={label}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? uid : undefined}
        aria-activedescendant={open ? `${uid}-${active}` : undefined}
        disabled={disabled}
        onClick={() => {
          setActive(Math.max(0, selected));
          setOpen(!open);
        }}
        onKeyDown={(e) => {
          if (
            [
              "ArrowDown",
              "ArrowUp",
              "Home",
              "End",
              "Enter",
              " ",
              "Escape",
            ].includes(e.key)
          )
            e.preventDefault();
          if (e.key === "Escape" && open) e.stopPropagation();
          if (e.key === "Tab" || e.key === "Escape") {
            setOpen(false);
            return;
          }
          if (e.key === "Enter" || e.key === " ") {
            if (open) choose(active);
            else {
              setActive(Math.max(0, selected));
              setOpen(true);
            }
          }
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            if (!open) {
              setActive(Math.max(0, selected));
              setOpen(true);
            } else
              setActive(
                (i) =>
                  (i + (e.key === "ArrowDown" ? 1 : -1) + options.length) %
                  options.length,
              );
          }
          if (e.key === "Home") setActive(0);
          if (e.key === "End") setActive(options.length - 1);
          if (e.key.length === 1 && e.key !== " ") {
            const index = options.findIndex((o) =>
              String(Children.toArray(o.label).join(""))
                .toLowerCase()
                .startsWith(e.key.toLowerCase()),
            );
            if (index >= 0) {
              setActive(index);
              if (!open) onValueChange(options[index].value);
            }
          }
        }}
      >
        <Layers3 size={18} className="dropdown-leading" />
        <span>
          {multipleValues
            ? "Select agents"
            : (options[selected]?.label ?? "Select an option")}
        </span>
        <ChevronDown
          size={17}
          className={open ? "dropdown-chevron is-open" : "dropdown-chevron"}
        />
      </button>
      {open &&
        !disabled &&
        createPortal(
          <div
            ref={menu}
            id={uid}
            role="listbox"
            aria-multiselectable={multipleValues ? true : undefined}
            aria-label={label ?? "Options"}
            className="modern-dropdown-menu"
            style={position}
          >
            {options.map((option, index) => (
              <div
                id={`${uid}-${index}`}
                key={option.value}
                role="option"
                aria-selected={
                  multipleValues
                    ? multipleValues.includes(option.value)
                    : option.value === value
                }
                className={`modern-dropdown-option ${index === active ? "is-active" : ""}`}
                onPointerMove={() => setActive(index)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => choose(index)}
              >
                <Layers3 size={18} />
                <span>{option.label}</span>
                {(multipleValues
                  ? multipleValues.includes(option.value)
                  : option.value === value) && (
                  <Check size={18} className="dropdown-check" />
                )}
              </div>
            ))}
          </div>,
          document.body,
        )}
    </>
  );
}
