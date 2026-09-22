import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, type Job } from "../lib/api";

const STATUSES = ["all", "queued", "running", "done", "failed", "cancelled"];

function barColor(s: string) {
  if (s === "done") return "bg-green-500";
  if (s === "failed") return "bg-red-500";
  if (s === "running") return "bg-blue-500";
  if (s === "cancelled") return "bg-gray-600";
  return "bg-yellow-500";
}

function DirectoryPicker({ initial, onSelect, onClose }: { initial: string; onSelect: (path: string) => void; onClose: () => void }) {
  const [browse, setBrowse] = useState<{ current: string; parent: string | null; home: string; download_dir: string; dirs: { name: string; path: string }[] } | null>(null);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const go = useCallback(async (path?: string) => {
    setError(null);
    try {
      setBrowse(await api.fs.browse(path));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => { go(initial || undefined); }, [go, initial]);

  async function create() {
    const name = newName.trim().replace(/[/\\]/g, "_");
    if (!name || !browse) return;
    setError(null);
    try {
      const res = await api.fs.mkdir(`${browse.current.replace(/\/$/, "")}/${name}`);
      setNewName("");
      await go(res.path);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div className="w-full max-w-xl overflow-hidden rounded border border-gray-700 bg-gray-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-gray-800 p-3">
          <h2 className="font-semibold text-white">Choose download folder</h2>
          <button onClick={onClose} className="rounded bg-gray-800 px-2 py-1 text-sm hover:bg-gray-700">Close</button>
        </div>
        <div className="space-y-3 p-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <button onClick={() => browse?.parent && go(browse.parent)} disabled={!browse?.parent} className="rounded bg-gray-800 px-2 py-1 disabled:opacity-40 hover:bg-gray-700">↑ Up</button>
            <button onClick={() => browse && go(browse.home)} className="rounded bg-gray-800 px-2 py-1 hover:bg-gray-700">🏠 Home</button>
            <button onClick={() => browse && go(browse.download_dir)} className="rounded bg-gray-800 px-2 py-1 hover:bg-gray-700">⬇ Default</button>
            <span className="min-w-0 flex-1 truncate font-mono text-xs text-gray-300" title={browse?.current}>{browse?.current || "…"}</span>
          </div>
          <div className="max-h-64 overflow-auto rounded border border-gray-800">
            {browse?.dirs.map((d) => (
              <button key={d.path} onClick={() => go(d.path)} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-gray-200 hover:bg-gray-800">
                <span>📁</span><span className="truncate">{d.name}</span>
              </button>
            ))}
            {browse && !browse.dirs.length && <p className="p-3 text-sm text-gray-500">Empty folder.</p>}
            {!browse && <p className="p-3 text-sm text-gray-500">Loading…</p>}
          </div>
          <div className="flex gap-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); create(); } }}
              placeholder="New folder name…"
              className="flex-1 rounded bg-gray-950 p-2 text-sm border border-gray-800 placeholder:text-gray-600"
            />
            <button onClick={create} className="rounded bg-gray-800 px-3 py-2 text-sm hover:bg-gray-700">+ Create</button>
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end gap-2">
            <button onClick={onClose} className="rounded bg-gray-800 px-4 py-2 text-sm hover:bg-gray-700">Cancel</button>
            <button
              onClick={() => { if (browse) { onSelect(browse.current); onClose(); } }}
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
            >
              Select this folder
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Queue() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [urls, setUrls] = useState("");
  const [destination, setDestination] = useState("");
  const [source, setSource] = useState("yt-dlp");
  const [audioOnly, setAudioOnly] = useState(false);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [defaultDir, setDefaultDir] = useState("");

  const load = useCallback(async () => {
    try {
      setJobs(await api.jobs.list(filter === "all" ? undefined : filter));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [filter]);

  useEffect(() => {
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => {
    api.settings().then((s) => setDefaultDir(s.download_dir)).catch(() => {});
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const lines = urls.split("\n").map((s) => s.trim()).filter(Boolean);
    if (!lines.length) return;
    setSubmitting(true);
    try {
      await api.jobs.create({
        urls: lines,
        source,
        destination: destination.trim() || undefined,
        audio_only: audioOnly,
      });
      setUrls("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-white">Download Queue</h1>
      <p className="text-sm text-gray-400">
        Paste one URL per line — multiple downloads queue at once and run up to the parallel limit.
        Playlists auto-download recursively into a folder named after the playlist. Metadata +
        thumbnails are embedded. Interrupted downloads resume via retry.
      </p>

      <form onSubmit={submit} className="rounded border border-gray-800 bg-gray-900 p-4 space-y-3">
        <textarea
          value={urls}
          onChange={(e) => setUrls(e.target.value)}
          rows={3}
          placeholder={"https://...\nhttps://... (playlist URL works too)"}
          className="w-full rounded bg-gray-950 p-2 text-sm text-gray-100 border border-gray-800 placeholder:text-gray-600"
        />
        <div className="flex flex-wrap gap-2">
          <input
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            placeholder={defaultDir ? `Default: ${defaultDir}` : "Default download folder"}
            title="Empty = default folder. Relative paths stay inside it; absolute paths may be anywhere in your home directory."
            className="flex-1 min-w-52 rounded bg-gray-950 p-2 text-sm border border-gray-800 placeholder:text-gray-600"
          />
          <button type="button" onClick={() => setPickerOpen(true)} title="Browse the server filesystem and create folders" className="rounded bg-gray-800 px-3 py-2 text-sm hover:bg-gray-700">
            📂 Browse…
          </button>
          {destination && (
            <button type="button" onClick={() => setDestination("")} title="Reset to default folder" className="rounded bg-gray-800 px-3 py-2 text-sm hover:bg-gray-700">
              Reset
            </button>
          )}
          <select value={source} onChange={(e) => setSource(e.target.value)} className="rounded bg-gray-950 p-2 text-sm border border-gray-800">
            <option value="yt-dlp">yt-dlp (most sites)</option>
            <option value="doodstream">doodstream</option>
          </select>
          <button
            type="button"
            role="switch"
            aria-checked={audioOnly}
            onClick={() => setAudioOnly((v) => !v)}
            title="Audio only: download audio as FLAC with cover + metadata"
            className={`flex items-center gap-2 rounded border px-3 py-2 text-sm transition-colors ${
              audioOnly
                ? "border-purple-500 bg-purple-600/20 text-purple-200"
                : "border-gray-800 bg-gray-950 text-gray-400 hover:border-gray-600"
            }`}
          >
            <span
              className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors ${
                audioOnly ? "bg-purple-500" : "bg-gray-700"
              }`}
            >
              <span
                className={`inline-block h-3 w-3 rounded-full bg-white transition-transform ${
                  audioOnly ? "translate-x-3.5" : "translate-x-0.5"
                }`}
              />
            </span>
            🎧 Audio only · FLAC
          </button>
          <button disabled={submitting} className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50">
            {submitting ? "Queuing…" : "Add to queue"}
          </button>
          <select value={filter} onChange={(e) => setFilter(e.target.value)} className="rounded bg-gray-950 p-2 text-sm border border-gray-800">
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
      </form>

      <div className="overflow-x-auto rounded border border-gray-800">
        <table className="w-full text-sm">
          <thead className="bg-gray-900 text-left text-gray-400">
            <tr><th className="p-2">URL / Title</th><th className="p-2">Status</th><th className="p-2 w-48">Progress</th><th className="p-2">Output</th><th className="p-2">Actions</th></tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id} className="border-t border-gray-800">
                <td className="p-2 max-w-72 truncate text-gray-200" title={j.url}>{j.title || j.url}<div className="text-xs text-gray-500">{j.source}{j.audio_only ? " · 🎧 flac" : ""}{j.destination ? ` → ${j.destination}` : ""}</div></td>
                <td className="p-2"><span className="rounded bg-gray-800 px-2 py-0.5 text-xs">{j.status}</span>{j.error && <div className="max-w-64 truncate text-xs text-red-400" title={j.error}>{j.error}</div>}</td>
                <td className="p-2"><div className="h-2 rounded bg-gray-800"><div className={`h-2 rounded ${barColor(j.status)}`} style={{ width: `${j.progress}%` }} /></div><div className="text-xs text-gray-500">{j.progress.toFixed(1)}%</div></td>
                <td className="p-2 max-w-48 truncate text-xs text-gray-500" title={j.output_path || ""}>{j.output_path || "—"}</td>
                <td className="p-2 flex gap-1">
                  {(j.status === "failed" || j.status === "cancelled") && <button onClick={() => api.jobs.retry(j.id).then(load)} className="rounded bg-gray-800 px-2 py-1 text-xs hover:bg-gray-700">Retry</button>}
                  {(j.status === "queued" || j.status === "running") && <button onClick={() => api.jobs.cancel(j.id).then(load)} className="rounded bg-gray-800 px-2 py-1 text-xs hover:bg-gray-700">Cancel</button>}
                  <button onClick={() => api.jobs.remove(j.id).then(load)} className="rounded bg-gray-800 px-2 py-1 text-xs text-red-300 hover:bg-gray-700">Delete</button>
                </td>
              </tr>
            ))}
            {!jobs.length && <tr><td colSpan={5} className="p-4 text-center text-gray-500">No jobs. Paste a URL above.</td></tr>}
          </tbody>
        </table>
      </div>
      {pickerOpen && (
        <DirectoryPicker
          initial={destination.trim() || defaultDir}
          onSelect={(p) => setDestination(p)}
          onClose={() => setPickerOpen(false)}
        />
      )}
    </div>
  );
}
