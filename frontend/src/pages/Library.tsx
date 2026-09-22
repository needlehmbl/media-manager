import { useCallback, useEffect, useState } from "react";
import { api, type LibraryItem } from "../lib/api";

export default function Library() {
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [q, setQ] = useState("");
  const [source, setSource] = useState("");
  const [selected, setSelected] = useState<LibraryItem | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await api.library.list(q || undefined, source || undefined));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [q, source]);

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [load]);

  useEffect(() => { load(); }, [load]);

  const isVideo = (p: string) => /\.(mp4|mkv|webm|mov|m4v)$/i.test(p);
  const isAudio = (p: string) => /\.(flac|mp3|ogg|oga|opus|m4a|aac|wav|wma|alac|aiff)$/i.test(p);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-white">Library</h1>
      <div className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title or path…" className="flex-1 rounded bg-gray-900 p-2 text-sm border border-gray-800 placeholder:text-gray-600" />
        <select value={source} onChange={(e) => setSource(e.target.value)} className="rounded bg-gray-900 p-2 text-sm border border-gray-800">
          <option value="">all sources</option>
          <option value="yt-dlp">yt-dlp</option>
          <option value="doodstream">doodstream</option>
        </select>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {items.map((it) => (
          <button key={it.id} onClick={() => setSelected(it)} className="overflow-hidden rounded border border-gray-800 bg-gray-900 text-left hover:border-gray-600">
            <div className="relative aspect-video bg-black flex items-center justify-center overflow-hidden">
              {it.thumbnail_path ? (
                <img
                  src={api.library.thumbUrl(it.thumbnail_path)}
                  alt={it.title}
                  loading="lazy"
                  className={`h-full w-full ${isAudio(it.file_path) ? "object-contain" : "object-cover"}`}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              ) : (
                <span className="text-3xl">{isAudio(it.file_path) ? "🎧" : "🎬"}</span>
              )}
              {isAudio(it.file_path) && (
                <span className="absolute left-1 top-1 rounded bg-purple-600/90 px-1.5 py-0.5 text-[10px] font-medium text-white">🎧 audio</span>
              )}
            </div>
            <div className="p-2">
              <div className="truncate text-sm text-gray-100" title={it.title}>{it.title}</div>
              <div className="text-xs text-gray-500">{it.source} · {new Date(it.downloaded_at).toLocaleString()}</div>
            </div>
          </button>
        ))}
      </div>
      {!items.length && <p className="text-sm text-gray-500">No items yet — completed downloads appear here.</p>}

      {selected && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/70 p-4" onClick={() => setSelected(null)}>
          <div className="max-h-[90vh] w-full max-w-3xl overflow-auto rounded border border-gray-700 bg-gray-900 p-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-2">
              <h2 className="font-semibold text-white">{selected.title}</h2>
              <button onClick={() => setSelected(null)} className="rounded bg-gray-800 px-2 py-1 text-sm">Close</button>
            </div>
            {isVideo(selected.file_path) && (
              <video
                controls
                src={api.fileUrlById(selected.id)}
                poster={selected.thumbnail_path ? api.library.thumbUrl(selected.thumbnail_path) : undefined}
                className="w-full rounded bg-black"
              />
            )}
            {isAudio(selected.file_path) && (
              <div className="overflow-hidden rounded bg-black">
                {selected.thumbnail_path && (
                  <img
                    src={api.library.thumbUrl(selected.thumbnail_path)}
                    alt={selected.title}
                    className="mx-auto max-h-72 object-contain"
                  />
                )}
                <audio controls src={api.fileUrlById(selected.id)} className="w-full" />
              </div>
            )}
            {!isVideo(selected.file_path) && !isAudio(selected.file_path) && (
              <p className="text-sm text-gray-500">Preview not available for this file type — use Download below.</p>
            )}
            <div className="mt-2 text-xs text-gray-400 break-all">{selected.file_path}</div>
            <div className="mt-1 text-xs text-gray-500">tags: {selected.tags || "—"}</div>
            <div className="mt-3 flex gap-2">
              <a href={api.fileUrlById(selected.id)} download className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white">Download</a>
              <button onClick={() => api.library.remove(selected.id).then(() => { setSelected(null); load(); })} className="rounded bg-gray-800 px-3 py-1.5 text-sm text-red-300">Delete record</button>
              <button onClick={() => api.library.remove(selected.id, true).then(() => { setSelected(null); load(); })} className="rounded bg-red-900 px-3 py-1.5 text-sm text-red-200">Delete + file</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
