import type { SVGProps } from "react";

/**
 * Single icon family (Lucide-style): 24px grid, 1.8 stroke, round caps.
 * Decorative by default (aria-hidden); pass aria-label via the wrapping control.
 */
function Icon({ children, className = "h-4 w-4", ...rest }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      {...rest}
    >
      {children}
    </svg>
  );
}

export const ChevronRight = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="m9 18 6-6-6-6" />
  </Icon>
);

export const ChevronDown = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="m6 9 6 6 6-6" />
  </Icon>
);

export const ArrowRight = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Icon>
);

export const Folder = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
  </Icon>
);

export const FileIcon = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M6 3h8l4 4v14H6V3z" />
    <path d="M14 3v4h4" />
  </Icon>
);

export const Terminal = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M5 7l4 5-4 5M11 17h8" />
  </Icon>
);

export const Spinner = ({ className = "h-4 w-4", ...rest }: SVGProps<SVGSVGElement>) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    strokeLinecap="round"
    aria-hidden="true"
    className={`animate-spin ${className}`}
    {...rest}
  >
    <path d="M12 3a9 9 0 1 0 9 9" />
  </svg>
);

export const Inbox = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M4 5h16v14H4V5z" />
    <path d="M4 13h5a3 3 0 0 0 6 0h5" />
  </Icon>
);

export const Close = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M6 6l12 12M18 6L6 18" />
  </Icon>
);

export const GitBranch = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <circle cx="6" cy="5" r="2.2" />
    <circle cx="6" cy="19" r="2.2" />
    <circle cx="18" cy="8" r="2.2" />
    <path d="M6 7.2v9.6M18 10.2c0 4-5 3.8-9.5 5.3" />
  </Icon>
);

export const Refresh = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M20 11a8 8 0 1 0-2 6.3" />
    <path d="M20 5v6h-6" />
  </Icon>
);

export const ChevronLeft = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="m15 18-6-6 6-6" />
  </Icon>
);

export const ChatBubble = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M21 12a8 8 0 0 1-8 8H4l2.5-2.5A8 8 0 1 1 21 12z" />
    <path d="M8.5 11h.01M12 11h.01M15.5 11h.01" />
  </Icon>
);

/** The AgentFlow mark: the orchestrator's top hat. */
export const TopHat = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M7 16V6a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v10" />
    <path d="M3.5 16.5c2.7.7 5.5 1 8.5 1s5.8-.3 8.5-1" />
    <path d="M7 12.5h10" />
  </Icon>
);

export const Send = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <path d="M4 12 20 4l-4 16-4.5-6.5L4 12z" />
    <path d="M11.5 13.5 20 4" />
  </Icon>
);

export const StopSquare = (p: SVGProps<SVGSVGElement>) => (
  <Icon {...p}>
    <rect x="7" y="7" width="10" height="10" rx="1.5" />
  </Icon>
);
