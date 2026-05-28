import React from "react";
import { Link } from "react-router-dom";
import { AlertCircle } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center animate-fade-in">
      <div className="w-16 h-16 bg-red-50 text-red-600 rounded-full flex items-center justify-center mb-6">
        <AlertCircle className="w-8 h-8" />
      </div>
      <h1 className="text-3xl font-bold font-heading text-slate-900 mb-2">404 - Page Not Found</h1>
      <p className="text-slate-500 max-w-md mb-8">
        The page you are looking for doesn't exist or has been moved. 
        Please check the URL or navigate back to the dashboard.
      </p>
      <Link 
        to="/" 
        className="px-6 py-2.5 bg-navy-600 text-white rounded-md font-medium hover:bg-navy-700 transition shadow-sm"
      >
        Go to Dashboard
      </Link>
    </div>
  );
}
