import type { ReactNode } from "react";

/* Shared layout primitives — every page and panel composes these so the shell
   reads as one design. See DESIGN.md. */

/** Standard page: scrollable canvas, centered max-w-5xl column, h1 + actions row. */
export function PageShell({
  title,
  actions,
  children,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-4 p-6">
        <header className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold">{title}</h1>
          <span className="flex-1" />
          {actions}
        </header>
        {children}
      </div>
    </div>
  );
}

/** Panel card. With `title` it gets the canonical header strip
    (section-title left, actions right); without it, a plain bordered panel. */
export function Card({
  id,
  title,
  actions,
  pad = false,
  className = "",
  bodyClassName = "",
  children,
}: {
  id?: string;
  /** String titles get the canonical section-title style; nodes render as given. */
  title?: ReactNode;
  actions?: ReactNode;
  /** Pad the body (p-4) — off by default for tables/lists that go edge to edge. */
  pad?: boolean;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className={`card overflow-hidden ${className}`}>
      {title !== undefined && (
        <div className="flex shrink-0 items-center gap-2 border-b border-neutral-200 px-3 py-1.5 dark:border-neutral-800">
          {typeof title === "string" ? <span className="section-title">{title}</span> : title}
          <span className="flex-1" />
          {actions}
        </div>
      )}
      <div className={`${pad ? "p-4" : ""} ${bodyClassName}`.trim()}>{children}</div>
    </section>
  );
}

/** Centered empty/placeholder state: muted icon over one short line. */
export function EmptyState({
  icon,
  message,
  children,
  className = "py-24",
}: {
  icon?: ReactNode;
  message: ReactNode;
  /** Optional extra content under the message (chips, a button). */
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex flex-col items-center justify-center gap-2 text-center ${className}`}>
      {icon && <span className="text-neutral-300 dark:text-neutral-600 [&>svg]:h-7 [&>svg]:w-7">{icon}</span>}
      <p className="text-xs text-neutral-500">{message}</p>
      {children}
    </div>
  );
}
