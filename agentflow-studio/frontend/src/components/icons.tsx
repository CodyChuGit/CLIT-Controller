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
