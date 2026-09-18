import { useEffect, useState } from "react";
import { api } from "../lib/api";

export default function Settings() {
  const [settings, setSettings] = useState<{ download_dir: string; max_concurrent_jobs: number; auth_enabled: boolean } | null>(null);
  const [key, setKey] = useState(() => localStorage.getItem("mm_api_key") || "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.settings().then(setSettings).catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  function saveKey() {
    localStorage.setItem("mm_api_key", key.trim());
    window.location.reload();
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-white">Settings</h1>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <div className="rounded border border-gray-800 bg-gray-900 p-4 space-y-2 text-sm">
        <div><span className="text-gray-500">Download dir: </span><span className="text-gray-100">{settings?.download_dir || "…"}</span></div>
        <div><span className="text-gray-500">Parallel jobs: </span><span className="text-gray-100">{settings?.max_concurrent_jobs ?? "…"}</span></div>
        <div><span className="text-gray-500">Auth: </span><span className="text-gray-100">{settings ? (settings.auth_enabled ? "API key enabled" : "disabled (API_KEY unset)") : "…"}</span></div>
        <p className="text-xs text-gray-500">Set DOWNLOAD_DIR / MAX_CONCURRENT_JOBS / API_KEY env vars on the api service to change. Playlists create a subfolder named after the playlist inside the destination you pick per job.</p>
      </div>
      <div className="rounded border border-gray-800 bg-gray-900 p-4 space-y-2">
        <h2 className="text-sm font-medium text-white">API key (stored in this browser only)</h2>
        <div className="flex gap-2">
          <input value={key} onChange={(e) => setKey(e.target.value)} type="password" placeholder="X-API-Key" className="flex-1 rounded bg-gray-950 p-2 text-sm border border-gray-800" />
          <button onClick={saveKey} className="rounded bg-blue-600 px-4 py-2 text-sm text-white">Save</button>
          <button onClick={() => { localStorage.removeItem("mm_api_key"); setKey(""); }} className="rounded bg-gray-800 px-4 py-2 text-sm">Clear</button>
        </div>
      </div>
    </div>
  );
}
