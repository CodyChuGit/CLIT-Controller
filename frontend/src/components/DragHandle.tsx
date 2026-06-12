/** VS Code-style pane resizer: a thin draggable divider. */
export default function DragHandle({
  orientation,
  onMove,
  onDone,
  label,
}: {
  orientation: "vertical" | "horizontal";
  onMove: (clientX: number, clientY: number) => void;
  onDone?: () => void;
  label: string;
}) {
  const start = (e: React.MouseEvent) => {
    e.preventDefault();
    const move = (ev: MouseEvent) => onMove(ev.clientX, ev.clientY);
    const up = () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      onDone?.();
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    document.body.style.cursor = orientation === "vertical" ? "col-resize" : "row-resize";
    document.body.style.userSelect = "none";
  };
  return (
    <div
      role="separator"
      aria-orientation={orientation}
      aria-label={label}
      title={label}
      onMouseDown={start}
      className={`shrink-0 transition-colors duration-150 hover:bg-accent/50 active:bg-accent/70 ${
        orientation === "vertical" ? "w-1 cursor-col-resize" : "h-1 cursor-row-resize"
      }`}
    />
  );
}
