import React, { useState, useRef, useEffect } from "react";
import { Bell, ChevronDown, LogOut, User, Settings } from "lucide-react";
import { Link } from "react-router-dom";
import { useClients } from "@/components/ClientContext";
import { useAuth } from "@/components/AuthContext";

export const Topbar = ({ firm }) => {
  const { clients, selected, setSelected } = useClients();
  const { logout } = useAuth();
  const [showNotifs, setShowNotifs] = useState(false);
  const [showUser, setShowUser] = useState(false);
  const notifsRef = useRef(null);
  const userRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (notifsRef.current && !notifsRef.current.contains(e.target)) setShowNotifs(false);
      if (userRef.current && !userRef.current.contains(e.target)) setShowUser(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 flex-shrink-0" data-testid="app-topbar">
      <div className="flex items-center gap-4">
        <label className="text-xs text-slate-500 font-semibold uppercase tracking-wider">Client</label>
        <div className="relative">
          <select
            data-testid="client-switcher"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="appearance-none bg-slate-50 border border-slate-200 text-sm font-medium text-slate-700 pl-3 pr-9 py-2 rounded-md hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-navy-600/30 focus:border-navy-600 transition min-w-[260px] font-mono tabular-nums"
          >
            <option value="all">All clients ({clients.length})</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.name} — {c.gstin}</option>
            ))}
          </select>
          <ChevronDown className="h-4 w-4 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
        </div>
      </div>
      <div className="flex items-center gap-4">
        {/* Notifications */}
        <div className="relative" ref={notifsRef}>
          <button
            onClick={() => { setShowNotifs(!showNotifs); setShowUser(false); }}
            className="relative p-2 rounded-md hover:bg-slate-100 transition"
            data-testid="topbar-notifications"
          >
            <Bell className="h-5 w-5 text-slate-600" />
          </button>
          {showNotifs && (
            <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-lg shadow-xl border border-slate-200 z-50 animate-fade-in">
              <div className="px-4 py-3 border-b border-slate-100 font-semibold text-sm text-slate-800">Notifications</div>
              <div className="px-4 py-8 text-center">
                <Bell className="h-8 w-8 text-slate-300 mx-auto mb-2" />
                <div className="text-sm text-slate-500">No new notifications</div>
                <div className="text-xs text-slate-400 mt-1">You're all caught up!</div>
              </div>
            </div>
          )}
        </div>

        {/* User menu */}
        <div className="relative" ref={userRef}>
          <button
            onClick={() => { setShowUser(!showUser); setShowNotifs(false); }}
            className="flex items-center gap-3 pl-4 border-l border-slate-200 hover:bg-slate-50 rounded-r-md pr-2 py-1 transition"
            data-testid="topbar-user-menu"
          >
            <div className="text-right leading-tight hidden sm:block">
              <div className="text-sm font-semibold text-slate-800">{firm?.name || "—"}</div>
              <div className="text-xs text-slate-500">{firm?.email || "—"}</div>
            </div>
            <div className="h-9 w-9 rounded-full bg-gradient-to-br from-navy-500 to-navy-700 flex items-center justify-center text-white font-semibold text-sm font-heading">
              {(firm?.name || "U").charAt(0)}
            </div>
          </button>
          {showUser && (
            <div className="absolute right-0 top-full mt-2 w-56 bg-white rounded-lg shadow-xl border border-slate-200 z-50 animate-fade-in">
              <div className="px-4 py-3 border-b border-slate-100">
                <div className="text-sm font-semibold text-slate-800 truncate">{firm?.name}</div>
                <div className="text-xs text-slate-500 truncate">{firm?.email}</div>
              </div>
              <div className="py-1">
                <Link to="/settings" onClick={() => setShowUser(false)} className="flex items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition">
                  <Settings className="h-4 w-4 text-slate-400" /> Settings
                </Link>
                <button onClick={logout} className="flex items-center gap-3 w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition" data-testid="topbar-logout">
                  <LogOut className="h-4 w-4" /> Sign out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default Topbar;
