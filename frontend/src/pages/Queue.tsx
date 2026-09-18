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

export default function Queue() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [urls, setUrls] = useState("");
  const [destination, setDestination] = useState("");
  const [source, setSource] = useState("yt-dlp");
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

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
            placeholder="Destination folder (optional, e.g. anime/2026)"
            className="flex-1 min-w-52 rounded bg-gray-950 p-2 text-sm border border-gray-800 placeholder:text-gray-600"
          />
          <select value={source} onChange={(e) => setSource(e.target.value)} className="rounded bg-gray-950 p-2 text-sm border border-gray-800">
            <option value="yt-dlp">yt-dlp (most sites)</option>
            <option value="doodstream">doodstream</option>
          </select>
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
                <td className="p-2 max-w-72 truncate text-gray-200" title={j.url}>{j.title || j.url}<div className="text-xs text-gray-500">{j.source}{j.destination ? ` → ${j.destination}` : ""}</div></td>
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
    </div>
  );
}
