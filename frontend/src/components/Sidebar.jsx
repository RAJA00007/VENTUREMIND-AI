import React from 'react';
import { 
  LayoutDashboard, 
  PlusCircle, 
  UploadCloud, 
  History, 
  Cpu, 
  Zap 
} from 'lucide-react';

export default function Sidebar({ activePage, setActivePage }) {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'analyze', label: 'Analyze Startup', icon: PlusCircle },
    { id: 'upload', label: 'Upload Pitch Deck', icon: UploadCloud },
    { id: 'history', label: 'Analysis History', icon: History },
  ];

  return (
    <aside className="w-64 bg-[#0a0a0c] border-r border-[#1a1a22] flex flex-col h-screen fixed left-0 top-0 z-30">
      {/* Brand Header */}
      <div className="p-6 border-b border-[#1a1a22] flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-purple-600 to-blue-500 flex items-center justify-center shadow-lg shadow-purple-500/20">
          <Cpu className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="font-display font-bold text-lg leading-tight bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
            VentureMind AI
          </h1>
          <span className="text-[10px] text-purple-400 font-semibold tracking-wider uppercase flex items-center gap-1 mt-0.5">
            <Zap className="w-2.5 h-2.5 fill-purple-400" /> VC Copilot
          </span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-4 py-6 space-y-1">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = activePage === item.id || (item.id === 'history' && activePage === 'report');
          return (
            <button
              key={item.id}
              onClick={() => setActivePage(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl font-medium text-sm transition-all duration-200 group ${
                isActive
                  ? 'bg-gradient-to-r from-purple-950/40 to-indigo-950/20 text-purple-300 border-l-2 border-purple-500 shadow-md shadow-purple-500/5'
                  : 'text-gray-400 hover:text-white hover:bg-white/5 border-l-2 border-transparent'
              }`}
            >
              <Icon className={`w-4 h-4 transition-transform duration-200 group-hover:scale-110 ${
                isActive ? 'text-purple-400' : 'text-gray-500 group-hover:text-gray-300'
              }`} />
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Footer Info */}
      <div className="p-4 border-t border-[#1a1a22] bg-black/20 text-[11px] text-gray-500 flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <span>System Status</span>
          <span className="flex items-center gap-1.5 font-semibold text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></span>
            Online
          </span>
        </div>
        <div className="mt-1 flex items-center justify-between text-[10px] text-gray-600">
          <span>AI Engine</span>
          <span>v1.2.0 (Active)</span>
        </div>
      </div>
    </aside>
  );
}
