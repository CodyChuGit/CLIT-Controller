import { useCallback, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "../api";
import type { OpensrcFile, OpensrcSearchHit, OpensrcTree } from "../types";

const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

export default function SourcesPage() {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [input, setInput] = useState("");
  const [pkg, setPkg] = useState("");
  const [cached, setCached] = useState<{ name?: string; path?: string }[]>([]);
  const [tree, setTree] = useState<OpensrcTree | null>(null);
  const [filter, setFilter] = useState("");
  const [file, setFile] = useState<OpensrcFile | null>(null);
  const [hits, setHits] = useState<OpensrcSearchHit[] | null>(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const s = await api.opensrcStatus();
      setAvailable(s.available);
      if (s.available) setCached(await api.opensrcList());
    } catch (e) {
      setError(errMsg(e));
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const openPkg = useCallback(async (name: string) => {
    setBusy(true);
    setError(null);
    setFile(null);
    setHits(null);
    try {
      await api.opensrcFetch(name);
      setTree(await api.opensrcTree(name));
      setPkg(name);
      setCached(await api.opensrcList()); // a fresh fetch belongs in Cached immediately
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  }, []);

  const openFile = async (path: string) => {
    if (!pkg) return;
    setError(null);
    setHits(null);
    try {
      setFile(await api.opensrcFile(pkg, path));
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const runSearch = async () => {
    if (!pkg || !query.trim()) return;
    setError(null);
    try {
      setHits(await api.opensrcSearch(pkg, query.trim()));
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const files = useMemo(
    () =>
      (tree?.entries ?? []).filter(
        (e) => e.type === "file" && e.path.toLowerCase().includes(filter.toLowerCase()),
      ),
    [tree, filter],
  );

  if (available === false) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center">
        <h2 className="text-sm font-semibold text-neutral-800 dark:text-neutral-200">
          opensrc not installed
        </h2>
        <p className="mt-1 max-w-sm text-xs text-neutral-500">
          <code className="rounded bg-neutral-100 px-1 py-0.5 dark:bg-neutral-800">opensrc</code>{" "}
          fetches any package's real source. Install it from the <strong>Agents</strong> tab (needs
          Node ≥ 24), then reload.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0">
      {/* Left: fetch + cached packages + file list */}
      <div className="flex w-72 shrink-0 flex-col gap-4 overflow-y-auto border-r border-neutral-200 p-3 dark:border-neutral-800">
        <div>
          <div className="section-label">Fetch source</div>
          <form
            className="mt-1 flex gap-1.5"
            onSubmit={(e) => {
              e.preventDefault();
              if (input.trim()) void openPkg(input.trim());
            }}
          >
            <input
              className="input"
              placeholder="zod · pypi:requests · owner/repo"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              aria-label="Package to fetch"
            />
            <button className="btn-primary" type="submit" disabled={busy}>
              {busy ? "…" : "Fetch"}
            </button>
          </form>
          <p className="mt-1 text-[11px] text-neutral-400">
            npm · pypi: · crates: · gitlab: · bitbucket: · owner/repo
          </p>
        </div>

        {cached.length > 0 && (
          <div>
            <div className="section-label">Cached</div>
            <ul className="mt-1 space-y-0.5">
              {cached.map((c) => (
                <li key={c.name ?? c.path}>
                  <button
                    className="focusable w-full truncate rounded px-1 py-0.5 text-left text-[11px] text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
                    onClick={() => c.name && void openPkg(c.name)}
                  >
                    {c.name ?? c.path}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {tree && (
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="section-label">{pkg} files</div>
            <input
              className="input mt-1"
              placeholder="Filter files…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              aria-label="Filter files"
            />
            <ul className="mt-1 min-h-0 flex-1 space-y-0.5 overflow-y-auto">
              {files.slice(0, 500).map((f) => (
                <li key={f.path}>
                  <button
                    className={`focusable w-full truncate rounded px-1 py-0.5 text-left font-mono text-[11px] hover:bg-neutral-100 dark:hover:bg-neutral-800 ${
                      file?.path === f.path
                        ? "bg-accent/10 text-blue-700 dark:text-blue-300"
                        : "text-neutral-600 dark:text-neutral-300"
                    }`}
                    title={f.path}
                    onClick={() => void openFile(f.path)}
                  >
                    {f.path}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Main: search + code viewer / hits */}
      <div className="flex min-h-0 flex-1 flex-col p-3">
        {pkg && (
          <form
            className="mb-3 flex gap-1.5"
            onSubmit={(e) => {
              e.preventDefault();
              void runSearch();
            }}
          >
            <input
              className="input"
              placeholder={`Search in ${pkg}…`}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search package source"
            />
            <button className="btn-secondary" type="submit">
              Search
            </button>
          </form>
        )}

        {error && (
          <div className="mb-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            {error}
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-auto">
          {hits ? (
            hits.length === 0 ? (
              <p className="text-xs text-neutral-400">No matches.</p>
            ) : (
              <ul className="space-y-1">
                {hits.map((h, i) => (
                  <li key={`${h.path}:${h.line}:${i}`}>
                    <button
                      className="focusable w-full rounded px-1 py-0.5 text-left hover:bg-neutral-100 dark:hover:bg-neutral-800"
                      onClick={() => void openFile(h.path)}
                    >
                      <span className="font-mono text-[11px] text-blue-700 dark:text-blue-300">
                        {h.path}:{h.line}
                      </span>
                      <span className="ml-2 font-mono text-[11px] text-neutral-500">{h.text}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )
          ) : file ? (
            <>
              <div className="mb-1 font-mono text-[11px] text-neutral-500">{file.path}</div>
              <pre className="mono-block whitespace-pre-wrap">{file.content}</pre>
            </>
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-neutral-400">
              Fetch a package, then pick a file to read its real source.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
