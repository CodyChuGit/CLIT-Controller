/** localStorage helpers — UI state (open tabs, panels, expanded folders) survives reloads. */

export function loadState<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(`agentflow.${key}`);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

export function saveState(key: string, value: unknown): void {
  try {
    localStorage.setItem(`agentflow.${key}`, JSON.stringify(value));
  } catch {
    /* storage full or unavailable — state just won't persist */
  }
}
