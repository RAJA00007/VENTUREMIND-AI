import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronUp, ExternalLink, Shield, Cpu, Users, Search, BarChart3, HelpCircle } from 'lucide-react';

export default function ScoreBreakdown({ agentResults }) {
  const [expandedAgent, setExpandedAgent] = useState(null);

  if (!agentResults || Object.keys(agentResults).length === 0) {
    return (
      <div className="text-center py-6 text-xs text-gray-500 border border-[#1a1a22] rounded-xl">
        No agent breakdowns available.
      </div>
    );
  }

  const getAgentIcon = (name) => {
    switch (name) {
      case 'Research Agent': return Search;
      case 'Market Agent': return BarChart3;
      case 'Competitor Agent': return Users;
      case 'Founder Agent': return Users;
      case 'Risk Agent': return Shield;
      case 'Prediction Agent': return Cpu;
      default: return HelpCircle;
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'failed':
        return (
          <span className="px-2 py-0.5 rounded bg-rose-500/10 border border-rose-500/20 text-[9px] font-bold text-rose-400 uppercase font-mono">
            Failed
          </span>
        );
      case 'no_data':
        return (
          <span className="px-2 py-0.5 rounded bg-gray-800 border border-gray-700 text-[9px] font-bold text-gray-400 uppercase font-mono">
            No Data
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-[9px] font-bold text-emerald-400 uppercase font-mono">
            Active
          </span>
        );
    }
  };

  const handleToggle = (agentName) => {
    setExpandedAgent(expandedAgent === agentName ? null : agentName);
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4">
        {Object.entries(agentResults).map(([name, result]) => {
          const isExpanded = expandedAgent === name;
          const Icon = getAgentIcon(name);
          const hasBreakdown = result.score_breakdown && result.score_breakdown.length > 0;

          return (
            <div 
              key={name}
              className={`glass-card border transition-all duration-300 ${
                isExpanded 
                  ? 'border-purple-500/35 bg-black/40 shadow-lg shadow-purple-500/5' 
                  : 'border-[#1f2029]/80 bg-black/20 hover:border-purple-500/20 hover:bg-black/30'
              }`}
            >
              {/* Header section (Always visible) */}
              <div 
                onClick={() => hasBreakdown && handleToggle(name)}
                className={`p-5 flex items-center justify-between select-none ${
                  hasBreakdown ? 'cursor-pointer' : 'cursor-default'
                }`}
              >
                <div className="flex items-center gap-4">
                  <div className={`p-2.5 rounded-xl border ${
                    result.status === 'failed' 
                      ? 'border-rose-500/20 bg-rose-500/10 text-rose-400'
                      : result.status === 'no_data'
                        ? 'border-gray-800 bg-gray-900 text-gray-400'
                        : 'border-purple-500/20 bg-purple-500/10 text-purple-400'
                  }`}>
                    <Icon className="w-4.5 h-4.5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-xs font-semibold text-white font-display tracking-wide">{name}</h4>
                      {getStatusBadge(result.status)}
                    </div>
                    <p className="text-[10px] text-gray-500 font-mono mt-0.5 uppercase tracking-wider">
                      Confidence: {Math.round(result.confidence * 100)}%
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-5">
                  <div className="text-right">
                    <span className="text-[9px] text-gray-500 block uppercase tracking-wider font-mono">Dimension Score</span>
                    <span className="text-sm font-extrabold text-white font-display">
                      {result.status === 'ok' ? `${result.score}/100` : '--'}
                    </span>
                  </div>
                  {hasBreakdown && (
                    <div className="text-gray-500 hover:text-white transition-colors">
                      {isExpanded ? <ChevronUp className="w-4.5 h-4.5" /> : <ChevronDown className="w-4.5 h-4.5" />}
                    </div>
                  )}
                </div>
              </div>

              {/* Expandable Breakdown List */}
              <AnimatePresence initial={false}>
                {isExpanded && hasBreakdown && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.25, ease: 'easeInOut' }}
                    className="overflow-hidden border-t border-[#1a1a22] bg-[#08080a]/50"
                  >
                    <div className="p-5 space-y-4">
                      {/* Summary */}
                      <div className="p-3.5 bg-black/45 border border-[#1a1a22] rounded-xl text-xs text-gray-300 leading-relaxed">
                        <strong className="text-purple-300 block mb-1 font-display text-[10px] uppercase tracking-wider">Analyst Assessment</strong>
                        {result.summary}
                      </div>

                      {/* Factors Grid */}
                      <div className="space-y-3">
                        <h5 className="text-[10px] font-mono text-gray-500 uppercase tracking-widest border-b border-[#1a1a22] pb-1.5">Rubric Performance Details</h5>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {result.score_breakdown.map((factor, idx) => (
                            <div key={idx} className="p-3.5 rounded-xl border border-[#1a1a22]/60 bg-black/20 flex flex-col justify-between">
                              <div>
                                <div className="flex justify-between items-start gap-2">
                                  <h6 className="text-[11px] font-semibold text-gray-200">{factor.factor}</h6>
                                  <span className="text-[11px] font-mono font-bold text-purple-400 whitespace-nowrap bg-purple-500/10 border border-purple-500/20 px-1.5 py-0.5 rounded">
                                    {factor.points} / {factor.max_points}
                                  </span>
                                </div>
                                <p className="text-[11px] text-gray-400 mt-2 leading-relaxed">
                                  {factor.reason}
                                </p>
                              </div>
                              {factor.source && (
                                <div className="mt-3 pt-2.5 border-t border-[#1a1a22]/40 flex items-center justify-between">
                                  <span className="text-[9px] text-gray-500 font-mono">Source</span>
                                  <a 
                                    href={factor.source} 
                                    target="_blank" 
                                    rel="noreferrer" 
                                    className="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-1 font-mono transition-colors"
                                  >
                                    Verify Sourced Link <ExternalLink className="w-3 h-3" />
                                  </a>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </div>
  );
}
