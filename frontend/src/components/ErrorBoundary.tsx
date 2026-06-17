import { Component, type ErrorInfo, type ReactNode } from "react";

/* App-level error boundary (audit P1-08). A render-phase throw anywhere in the
   tree would otherwise unmount the whole IDE to a blank screen — losing the chat
   panel, open editor tabs, and unsaved drafts with no way to recover. This catches
   it, shows the error, and offers a Reload. Wrap the whole app and, ideally,
   individual panes so one crash doesn't take down the others. */

type Props = {
  children: ReactNode;
  /** Short label for the region this boundary guards (shown in the fallback). */
  label?: string;
  /** Optional custom fallback renderer. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
};

type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Surface in the console for local debugging; this is a local single-user tool.
    console.error("ErrorBoundary caught an error:", error, info.componentStack);
  }

  reset = () => this.setState({ error: null });

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback(error, this.reset);

    const region = this.props.label ? ` in ${this.props.label}` : "";
    return (
      <div
        role="alert"
        className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center"
      >
        <div className="text-sm font-semibold text-red-600 dark:text-red-400">
          Something went wrong{region}.
        </div>
        <pre className="max-w-full overflow-auto rounded bg-neutral-100 p-2 text-left text-[11px] text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300">
          {error.message}
        </pre>
        <div className="flex gap-2">
          <button
            onClick={this.reset}
            className="focusable rounded border border-neutral-300 px-3 py-1 text-xs font-medium hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
          >
            Try again
          </button>
          <button
            onClick={() => window.location.reload()}
            className="focusable rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700"
          >
            Reload
          </button>
        </div>
      </div>
    );
  }
}
