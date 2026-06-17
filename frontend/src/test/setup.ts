// Vitest global setup: extend `expect` with jest-dom DOM matchers
// (toBeInTheDocument, toHaveTextContent, …) for component tests.
import "@testing-library/jest-dom/vitest";

// Ensure a working localStorage in the jsdom test env so persist.ts (drafts, UI
// state) behaves as in the browser. jsdom does not always provide one.
if (
  typeof globalThis.localStorage === "undefined" ||
  typeof globalThis.localStorage.clear !== "function"
) {
  const store = new Map<string, string>();
  const ls: Storage = {
    getItem: (k) => (store.has(k) ? (store.get(k) as string) : null),
    setItem: (k, v) => void store.set(k, String(v)),
    removeItem: (k) => void store.delete(k),
    clear: () => store.clear(),
    key: (i) => Array.from(store.keys())[i] ?? null,
    get length() {
      return store.size;
    },
  } as Storage;
  Object.defineProperty(globalThis, "localStorage", { value: ls, configurable: true });
}
