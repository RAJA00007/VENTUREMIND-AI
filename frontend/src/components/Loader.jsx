import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, BarChart3, Users, ShieldAlert, Cpu, Sparkles } from 'lucide-react';

export default function Loader({ companyName }) {
  const [activeStep, setActiveStep] = useState(0);

  const steps = [
    { label: 'Research Agent', desc: 'Gathering funding, traction, and live web metrics...', icon: Search },
    { label: 'Market Agent', desc: 'Sizing TAM/SAM/SOM and evaluating market growth trends...', icon: BarChart3 },
    { label: 'Competitor Agent', desc: 'Identifying market rivals and evaluating competitive moats...', icon: Users },
    { label: 'Risk Agent', desc: 'Assessing technical, business, and founding risk matrices...', icon: ShieldAlert },
    { label: 'ML Success Engine', desc: 'Running classification predictor over company vectors...', icon: Cpu },
    { label: 'Investment Committee', desc: 'Synthesizing final score, opportunity vectors, and verdict...', icon: Sparkles },
  ];

  useEffect(() => {
    // Progress through the loading steps to simulate real agents executing in parallel
    const interval = setInterval(() => {
      setActiveStep((prev) => {
        if (prev < steps.length - 1) {
          return prev + 1;
        }
        return prev; // Hold at the last step
      });
    }, 4500); // 27 seconds total simulation (backend normally takes 15-30s depending on LLM latency)

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center py-12 max-w-lg mx-auto text-center">
      {/* Spinning AI Orb */}
      <div className="relative w-28 h-28 mb-8">
        <motion.div 
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 10, ease: "linear" }}
          className="absolute inset-0 rounded-full border-2 border-dashed border-purple-500/30"
        />
        <motion.div 
          animate={{ rotate: -360 }}
          transition={{ repeat: Infinity, duration: 15, ease: "linear" }}
          className="absolute inset-2 rounded-full border border-dashed border-blue-500/20"
        />
        <div className="absolute inset-4 rounded-full bg-gradient-to-tr from-purple-600/20 to-blue-500/20 blur-sm flex items-center justify-center">
          <div className="w-16 h-16 rounded-full bg-black border border-purple-500/40 flex items-center justify-center shadow-lg shadow-purple-500/20">
            <Cpu className="w-8 h-8 text-purple-400 animate-pulse" />
          </div>
        </div>
      </div>

      <h3 className="text-xl font-display font-bold text-white mb-2">
        Analyzing {companyName || 'Startup'}
      </h3>
      <p className="text-xs text-gray-500 max-w-sm mb-10">
        Our multi-agent committee is analyzing live data points and historical success signals. This takes a few seconds.
      </p>

      {/* Stepper Timeline */}
      <div className="w-full space-y-4 text-left">
        {steps.map((step, idx) => {
          const StepIcon = step.icon;
          const isPending = idx > activeStep;
          const isActive = idx === activeStep;
          const isCompleted = idx < activeStep;

          return (
            <div 
              key={idx}
              className={`flex items-start gap-4 p-3 rounded-xl border transition-all duration-300 ${
                isActive 
                  ? 'bg-purple-950/10 border-purple-500/30 shadow-[0_0_15px_-5px_rgba(168,85,247,0.2)]'
                  : isCompleted
                    ? 'bg-black/20 border-emerald-950/20 opacity-70'
                    : 'bg-black/10 border-transparent opacity-40'
              }`}
            >
              {/* Step Status Indicator */}
              <div className="relative mt-0.5">
                {isCompleted ? (
                  <div className="w-6 h-6 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
                    <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                  </div>
                ) : isActive ? (
                  <div className="w-6 h-6 rounded-full bg-purple-500/20 border border-purple-500/50 flex items-center justify-center">
                    <span className="w-2.5 h-2.5 rounded-full bg-purple-400 animate-ping"></span>
                  </div>
                ) : (
                  <div className="w-6 h-6 rounded-full bg-[#15151c] border border-gray-800 flex items-center justify-center">
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-700"></span>
                  </div>
                )}
              </div>

              {/* Step Copy */}
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <StepIcon className={`w-3.5 h-3.5 ${isActive ? 'text-purple-400' : isCompleted ? 'text-emerald-400' : 'text-gray-500'}`} />
                  <h4 className={`text-xs font-semibold ${isActive ? 'text-purple-300' : isCompleted ? 'text-emerald-400' : 'text-gray-400'}`}>
                    {step.label}
                  </h4>
                </div>
                {isActive && (
                  <motion.p 
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className="text-[11px] text-gray-400 mt-1 leading-relaxed"
                  >
                    {step.desc}
                  </motion.p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
