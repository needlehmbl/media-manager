import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import Queue from "./pages/Queue";
import Library from "./pages/Library";
import Channels from "./pages/Channels";
import Settings from "./pages/Settings";

function Nav() {
  const loc = useLocation();
  const link = (to: string) =>
    `rounded px-3 py-1.5 text-sm ${loc.pathname === to ? "bg-gray-800 text-white" : "text-gray-400 hover:bg-gray-900 hover:text-gray-100"}`;
  return (
    <nav className="flex items-center gap-2 border-b border-gray-800 bg-gray-950 p-4">
      <span className="mr-4 font-bold text-white">Media Manager</span>
      <Link className={link("/")} to="/">Queue</Link>
      <Link className={link("/library")} to="/library">Library</Link>
      <Link className={link("/channels")} to="/channels">Channels</Link>
      <Link className={link("/settings")} to="/settings">Settings</Link>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-950 text-gray-100">
        <Nav />
        <main className="mx-auto max-w-6xl p-4">
          <Routes>
            <Route path="/" element={<Queue />} />
            <Route path="/library" element={<Library />} />
            <Route path="/channels" element={<Channels />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
