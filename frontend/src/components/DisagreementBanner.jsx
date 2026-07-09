import React from 'react';
import { AlertTriangle } from 'lucide-react';

export default function DisagreementBanner({ hasDisagreement, note, conflictingAgents, spread }) {
  if (!hasDisagreement) return null;
  
  return (
    <div className="glass-card p-5 border-amber-500/20 bg-amber-500/5 relative overflow-hidden rounded-2xl">
      <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/5 rounded-full blur-2xl -mr-6 -mt-6"></div>
      <div className="flex gap-4">
        <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 h-fit">
          <AlertTriangle className="w-5 h-5 animate-pulse" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h4 className="text-xs font-semibold text-amber-300 font-display uppercase tracking-wider">
              Significant Agent Disagreement Detected
            </h4>
            <span className="px-2 py-0.5 rounded-md bg-amber-500/20 border border-amber-500/30 text-[9px] font-bold text-amber-400 font-mono">
              Spread: {spread} pts
            </span>
          </div>
          <p className="text-xs text-gray-300 mt-2 leading-relaxed max-w-3xl">
            {note}
          </p>
          {conflictingAgents && conflictingAgents.length > 0 && (
            <div className="flex gap-1.5 mt-3 flex-wrap">
              {conflictingAgents.map((agent, i) => (
                <span 
                  key={i} 
                  className="text-[9px] bg-black/40 border border-amber-500/20 text-amber-400/80 px-2.5 py-0.5 rounded-md font-mono"
                >
                  {agent}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
