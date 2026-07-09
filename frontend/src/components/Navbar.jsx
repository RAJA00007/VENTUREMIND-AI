import React from 'react';
import { ShieldCheck, Database, Layers, Sparkles } from 'lucide-react';

export default function Navbar({ activePage }) {
  const getPageTitle = () => {
    switch (activePage) {
      case 'dashboard':
        return 'Overview';
      case 'analyze':
        return 'Startup Ingestion';
      case 'report':
        return 'Investment Analysis Report';
      case 'upload':
        return 'RAG Pitch Deck Analyzer';
      case 'history':
        return 'VC Intelligence Archives';
      default:
        return 'VentureMind AI';
    }
  };

  return (
    <header className="h-16 border-b border-[#1a1a22] bg-[#050507]/60 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-20">
      {/* Page Title */}
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-display font-semibold text-white tracking-wide">
          {getPageTitle()}
        </h2>
        <span className="h-4 w-px bg-[#1a1a22]"></span>
        <div className="flex items-center gap-1 text-[11px] text-gray-400 bg-[#121216] border border-[#1e1e24] px-2 py-0.5 rounded-full">
          <Sparkles className="w-3 h-3 text-purple-400" />
          <span>Multi-Agent Mode</span>
        </div>
      </div>

      {/* Latency & DB Badges */}
      <div className="flex items-center gap-4">
        {/* PostgreSQL Ingress Indicator */}
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <Database className="w-3.5 h-3.5 text-blue-400" />
          <span className="font-mono text-[11px]">PostgreSQL Active</span>
        </div>

        {/* Vector DB Indicator */}
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <Layers className="w-3.5 h-3.5 text-purple-400" />
          <span className="font-mono text-[11px]">ChromaDB Connected</span>
        </div>

        {/* LLM Status */}
        <div className="flex items-center gap-2 text-xs bg-emerald-950/20 border border-emerald-900/50 text-emerald-400 px-3 py-1 rounded-lg">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span className="font-medium text-[11px]">AI Model Verified</span>
        </div>
      </div>
    </header>
  );
}
