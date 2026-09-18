import { useEffect, useState, type FormEvent } from "react";
import { api, type Channel } from "../lib/api";

export default function Channels() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [url, setUrl] = useState("");
  const [interval, setInterval] = useState(3600);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setChannels(await api.channels.list());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }
  useEffect(() => { load(); }, []);

  async function add(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.channels.create({ url, check_interval: interval, active: true });
      setUrl("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-white">Channels</h1>
      <p className="text-sm text-gray-400">Recurring checks auto-enqueue new videos as jobs. Minimum interval 300s.</p>
      <form onSubmit={add} className="flex flex-wrap gap-2 rounded border border-gray-800 bg-gray-900 p-4">
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="Channel / playlist URL" className="flex-1 min-w-64 rounded bg-gray-950 p-2 text-sm border border-gray-800 placeholder:text-gray-600" />
        <input type="number" value={interval} min={300} onChange={(e) => setInterval(Number(e.target.value))} className="w-32 rounded bg-gray-950 p-2 text-sm border border-gray-800" title="Check interval (seconds)" />
        <button className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500">Add channel</button>
      </form>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <div className="space-y-2">
        {channels.map((c) => (
          <div key={c.id} className="flex flex-wrap items-center gap-2 rounded border border-gray-800 bg-gray-900 p-3">
            <div className="flex-1 min-w-48">
              <div className="truncate text-sm text-gray-100">{c.url}</div>
              <div className="text-xs text-gray-500">every {c.check_interval}s · last checked {c.last_checked ? new Date(c.last_checked).toLocaleString() : "never"}</div>
            </div>
            <button onClick={() => api.channels.update(c.id, { active: !c.active }).then(load)} className={`rounded px-3 py-1 text-xs ${c.active ? "bg-green-900 text-green-200" : "bg-gray-800 text-gray-400"}`}>{c.active ? "active" : "paused"}</button>
            <button onClick={() => api.channels.check(c.id).then(load)} className="rounded bg-gray-800 px-3 py-1 text-xs hover:bg-gray-700">Check now</button>
            <button onClick={() => api.channels.remove(c.id).then(load)} className="rounded bg-gray-800 px-3 py-1 text-xs text-red-300 hover:bg-gray-700">Delete</button>
          </div>
        ))}
        {!channels.length && <p className="text-sm text-gray-500">No channels yet.</p>}
      </div>
    </div>
  );
}
