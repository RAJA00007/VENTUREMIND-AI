import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Circle, AlertCircle } from 'lucide-react';

export default function AgentCard({ name, role, description, capabilities, status = 'idle', icon: Icon }) {
  const getStatusColor = () => {
    switch (status) {
      case 'active':
        return 'text-blue-400 border-blue-500/30 bg-blue-500/5';
      case 'completed':
        return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/5';
      case 'error':
        return 'text-rose-400 border-rose-500/30 bg-rose-500/5';
      default:
        return 'text-gray-500 border-[#1a1a22] bg-[#0c0c0e]';
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`glass-card glass-card-hover p-6 flex flex-col justify-between h-full relative overflow-hidden group ${
        status === 'active' ? 'border-purple-500/40 ring-1 ring-purple-500/20' : ''
      }`}
    >
      {/* Decorative Gradient Glow */}
      {status === 'active' && (
        <div className="absolute top-0 right-0 w-24 h-24 bg-purple-500/10 rounded-full blur-2xl -mr-6 -mt-6"></div>
      )}

      <div>
        {/* Agent Header */}
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-xl border ${
              status === 'active' 
                ? 'border-purple-500/30 bg-purple-500/10 text-purple-400' 
                : 'border-[#1e1e24] bg-white/5 text-gray-400 group-hover:text-purple-400 group-hover:border-purple-500/20 transition-all duration-300'
            }`}>
              {Icon && <Icon className="w-5 h-5" />}
            </div>
            <div>
              <h3 className="font-display font-semibold text-white group-hover:text-purple-300 transition-colors duration-300">
                {name}
              </h3>
              <p className="text-[11px] text-gray-500 font-mono font-medium uppercase tracking-wider mt-0.5">
                {role}
              </p>
            </div>
          </div>

          {/* Status Badge */}
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[10px] font-medium tracking-wide ${getStatusColor()}`}>
            {status === 'active' && <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-ping"></span>}
            {status === 'completed' && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
            {status === 'error' && <AlertCircle className="w-3 h-3 text-rose-400" />}
            {status === 'idle' && <Circle className="w-2.5 h-2.5 text-gray-500" />}
            <span className="capitalize">{status}</span>
          </div>
        </div>

        {/* Description */}
        <p className="text-xs text-gray-400 leading-relaxed mb-5">
          {description}
        </p>
      </div>

      {/* Capabilities Tags */}
      <div className="flex flex-wrap gap-1.5 mt-auto">
        {capabilities.map((cap, i) => (
          <span 
            key={i} 
            className="text-[10px] bg-[#121216] border border-[#1d1d24] text-gray-400 px-2.5 py-0.5 rounded-md font-mono"
          >
            {cap}
          </span>
        ))}
      </div>
    </motion.div>
  );
}
