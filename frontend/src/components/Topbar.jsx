import React from "react";
import { Bell, ChevronDown } from "lucide-react";
import { useClients } from "@/components/ClientContext";

export const Topbar = ({ firm }) => {
  const { clients, selected, setSelected } = useClients();
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
        <button className="relative p-2 rounded-md hover:bg-slate-100 transition" data-testid="topbar-notifications">
          <Bell className="h-5 w-5 text-slate-600" />
          <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-red-500"></span>
        </button>
        <div className="flex items-center gap-3 pl-4 border-l border-slate-200">
          <div className="text-right leading-tight hidden sm:block">
            <div className="text-sm font-semibold text-slate-800">{firm?.name || "—"}</div>
            <div className="text-xs text-slate-500">{firm?.email || "—"}</div>
          </div>
          <div className="h-9 w-9 rounded-full bg-gradient-to-br from-navy-500 to-navy-700 flex items-center justify-center text-white font-semibold text-sm font-heading">
            {(firm?.name || "K").charAt(0)}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Topbar;
