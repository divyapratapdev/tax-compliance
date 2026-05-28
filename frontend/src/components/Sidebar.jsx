import React from "react";
import { NavLink, Link } from "react-router-dom";
import {
  LayoutDashboard, Users, FileUp, GitCompareArrows,
  Calculator, CalendarClock, Settings, Compass, LogOut
} from "lucide-react";
import { useAuth } from "@/components/AuthContext";

const NAV = [
  { to: "/",                    label: "Dashboard",         icon: LayoutDashboard, testId: "nav-dashboard" },
  { to: "/clients",             label: "Clients",           icon: Users,           testId: "nav-clients" },
  { to: "/documents",           label: "Documents",         icon: FileUp,          testId: "nav-documents" },
  { to: "/gst-reconciliation",  label: "GST Reconciliation",icon: GitCompareArrows,testId: "nav-gst" },
  { to: "/tds-alerts",          label: "TDS Alerts",        icon: Calculator,      testId: "nav-tds" },
  { to: "/compliance",          label: "Compliance",        icon: CalendarClock,   testId: "nav-compliance" },
  { to: "/settings",            label: "Settings",          icon: Settings,        testId: "nav-settings" },
];

export const Sidebar = ({ firm }) => {
  const { logout } = useAuth();

  return (
    <aside className="w-64 bg-sidebar text-slate-100 flex-shrink-0 flex flex-col" data-testid="app-sidebar">
      <Link to="/" className="h-16 flex items-center gap-3 px-5 border-b border-slate-800/50 hover:bg-slate-800/30 transition">
        <div className="h-9 w-9 rounded-md bg-gradient-to-br from-sky-400 to-navy-500 flex items-center justify-center shadow-sm">
          <Compass className="h-5 w-5 text-white" strokeWidth={2.5} />
        </div>
        <div className="leading-tight">
          <div className="font-heading font-bold text-white tracking-tight text-lg">TaxPilot</div>
          <div className="text-[10px] text-slate-400 uppercase tracking-widest">CA Compliance OS</div>
        </div>
      </Link>

      <nav className="flex-1 px-3 py-5 space-y-1">
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === "/"}
            data-testid={n.testId}
            className={({ isActive }) => `nav-link ${isActive ? "nav-link-active" : ""}`}
          >
            <n.icon className="h-4 w-4" strokeWidth={2} />
            <span>{n.label}</span>
          </NavLink>
        ))}
      </nav>

      <Link to="/settings" className="block hover:bg-slate-800/30 rounded-md transition px-4 py-4 border-t border-slate-800/50">
        {firm && (
          <div>
            <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Firm</div>
            <div className="text-sm font-semibold text-white truncate">{firm.name}</div>
            <div className="text-xs text-slate-400 truncate">{firm.registration_number || "PENDING"}</div>
          </div>
        )}
      </Link>
      <button onClick={logout} className="flex items-center gap-3 w-full px-7 py-4 text-sm text-slate-400 hover:text-white hover:bg-red-600/20 transition" data-testid="sidebar-logout">
        <LogOut className="h-4 w-4" /> Sign out
      </button>
    </aside>
  );
};

export default Sidebar;
