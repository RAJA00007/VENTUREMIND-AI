import React from 'react';
import { motion } from 'framer-motion';
import { Award, TrendingUp, AlertTriangle, HelpCircle } from 'lucide-react';

export default function ScoreCard({ score, decision, confidence, wasOverridden, overrideReason }) {
  // Normalize score
  const numericScore = Math.min(Math.max(parseInt(score) || 0, 0), 100);
  
  // Circle progress calculation
  const radius = 60;
  const strokeWidth = 8;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (numericScore / 100) * circumference;

  // Determine styling based on decision
  const getDecisionDetails = () => {
    const formatted = String(decision).toUpperCase();
    if (formatted.includes('INVEST')) {
      return {
        label: 'INVEST',
        color: 'from-emerald-500 to-teal-400',
        textColor: 'text-emerald-400',
        bgColor: 'bg-emerald-500/10 border-emerald-500/20',
        shadowColor: 'shadow-emerald-500/10',
        icon: TrendingUp,
        desc: 'Strong investment indicators across primary metrics.',
      };
    } else if (formatted.includes('WATCH')) {
      return {
        label: 'WATCH',
        color: 'from-amber-500 to-orange-400',
        textColor: 'text-amber-400',
        bgColor: 'bg-amber-500/10 border-amber-500/20',
        shadowColor: 'shadow-amber-500/10',
        icon: HelpCircle,
        desc: 'Potential opportunity. Keep monitoring milestones.',
      };
    } else {
      return {
        label: 'PASS',
        color: 'from-rose-500 to-red-400',
        textColor: 'text-rose-400',
        bgColor: 'bg-rose-500/10 border-rose-500/20',
        shadowColor: 'shadow-rose-500/10',
        icon: AlertTriangle,
        desc: 'Elevated risks or weak indicators. Not recommended.',
      };
    }
  };

  const info = getDecisionDetails();
  const Icon = info.icon;

  return (
    <div className="glass-card p-6 flex flex-col items-center justify-center relative overflow-hidden h-full">
      {/* Background Radial Glow */}
      <div className={`absolute -bottom-16 -right-16 w-36 h-36 bg-gradient-radial ${
        info.label === 'INVEST' 
          ? 'from-emerald-500/5 to-transparent' 
          : info.label === 'WATCH' 
            ? 'from-amber-500/5 to-transparent' 
            : 'from-rose-500/5 to-transparent'
      } rounded-full blur-2xl`}></div>

      <div className="w-full flex items-center justify-between mb-4 border-b border-[#1a1a22] pb-3">
        <div className="flex items-center gap-2">
          <Award className="w-4.5 h-4.5 text-purple-400" />
          <h3 className="text-sm font-semibold tracking-wide text-gray-200">Committee Ruling</h3>
        </div>
        <span className="text-[10px] text-gray-500 uppercase tracking-widest font-mono">Verdict</span>
      </div>

      <div className="flex flex-col md:flex-row items-center gap-6 py-2 w-full justify-around">
        {/* SVG Circular Dial */}
        <div className="relative flex items-center justify-center">
          <svg className="w-36 h-36 transform -rotate-95">
            {/* Background Ring */}
            <circle
              className="text-[#15151b]"
              strokeWidth={strokeWidth}
              stroke="currentColor"
              fill="transparent"
              r={radius}
              cx="72"
              cy="72"
            />
            {/* Foreground Score Ring */}
            <motion.circle
              className={`stroke-current`}
              strokeWidth={strokeWidth}
              strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset }}
              transition={{ duration: 1, ease: 'easeOut' }}
              strokeLinecap="round"
              fill="transparent"
              r={radius}
              cx="72"
              cy="72"
              style={{
                stroke: `url(#scoreGradient)`,
                filter: `drop-shadow(0 0 4px rgba(139, 92, 246, 0.3))`
              }}
            />
            {/* Gradients definitions */}
            <defs>
              <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#8b5cf6" />
                <stop offset="100%" stopColor="#3b82f6" />
              </linearGradient>
            </defs>
          </svg>

          {/* Core Score Number inside Circle */}
          <div className="absolute flex flex-col items-center justify-center">
            <span className="text-3xl font-display font-extrabold text-white tracking-tighter">
              {numericScore}
            </span>
            <span className="text-[10px] text-gray-500 uppercase font-mono tracking-wider -mt-1">
              / 100
            </span>
          </div>
        </div>

        {/* Verdict Badge & Details */}
        <div className="flex-1 flex flex-col items-center md:items-start text-center md:text-left">
          <div className={`px-5 py-2 rounded-xl border font-display font-bold text-lg tracking-wider flex items-center gap-2 shadow-lg ${info.bgColor} ${info.textColor} ${info.shadowColor}`}>
            <Icon className="w-5 h-5 animate-pulse" />
            <span>{info.label}</span>
          </div>
          
          <h4 className="text-[10px] text-gray-500 uppercase tracking-widest font-mono mt-4 mb-0.5">
            Committee Confidence
          </h4>
          <div className="flex items-center gap-2">
            <span className={`text-xs font-mono font-bold ${
              confidence >= 0.70 
                ? 'text-emerald-400' 
                : confidence >= 0.50 
                  ? 'text-amber-400' 
                  : 'text-rose-400'
            }`}>
              {confidence !== undefined ? `${Math.round(confidence * 100)}%` : 'N/A'}
            </span>
            <span className="text-[10px] text-gray-400">
              ({confidence >= 0.70 ? 'High' : confidence >= 0.50 ? 'Medium' : 'Low'})
            </span>
          </div>
          
          {wasOverridden && (
            <div className="mt-3 p-2.5 bg-amber-500/10 border border-amber-500/20 rounded-xl text-[10px] text-amber-400 leading-relaxed max-w-[220px]">
              <strong>Safety Override:</strong> {overrideReason}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
