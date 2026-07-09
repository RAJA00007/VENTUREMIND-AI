import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { 
  ArrowLeft, 
  Download, 
  Search, 
  BarChart3, 
  Users, 
  ShieldAlert, 
  Cpu, 
  Sparkles,
  Info
} from 'lucide-react';
import ScoreCard from '../components/ScoreCard';
import DisagreementBanner from '../components/DisagreementBanner';
import ScoreBreakdown from '../components/ScoreBreakdown';
import { RiskRadarChart, MarketSizeChart, MLConfidenceChart } from '../components/Chart';
import { apiService } from '../api/api';

export default function Report({ reportData, reportId, setActivePage }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    async function loadReport() {
      if (reportData) {
        setData(reportData);
      } else if (reportId) {
        setLoading(true);
        setError('');
        try {
          const detail = await apiService.getAnalysisDetail(reportId);
          setData(detail);
        } catch (err) {
          console.error(err);
          setError('Failed to fetch the report from the database archives.');
        } finally {
          setLoading(false);
        }
      }
    }
    loadReport();
  }, [reportData, reportId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <div className="w-10 h-10 border-t-2 border-r-2 border-purple-500 rounded-full animate-spin"></div>
        <p className="text-xs text-gray-500 mt-4">Loading investment report details...</p>
      </div>
    );
  }

  if (error || (!data && !loading)) {
    return (
      <div className="max-w-md mx-auto py-12 text-center space-y-4">
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl text-xs">
          {error || 'No report context available.'}
        </div>
        <button
          onClick={() => setActivePage('history')}
          className="px-6 py-2 border border-[#1a1a22] text-xs text-gray-400 hover:text-white rounded-lg transition-colors"
        >
          Go Back to Archives
        </button>
      </div>
    );
  }

  const normalizeData = (data) => {
    // If it has final_decision (database row), extract from final_decision
    const comm = data.final_decision ? data.final_decision : data;
    
    const companyName = data.company_name || data.company || comm.company || 'Startup';
    const verdict = comm.verdict || 'WATCH';
    const score = comm.final_score !== undefined ? comm.final_score : 50;
    const overallConfidence = comm.overall_confidence !== undefined ? comm.overall_confidence : 0.5;
    const wasOverridden = comm.was_overridden || false;
    const overrideReason = comm.override_reason || null;
    const hasDisagreement = comm.significant_disagreement || false;
    const disagreementNote = comm.disagreement_note || null;
    const keyOpportunities = comm.key_opportunities || [];
    const keyRisks = comm.key_risks || [];
    const narrative = comm.narrative || '';
    const confidenceBreakdown = comm.confidence_breakdown || {};
    
    // Get full agent_results dict
    const agentResults = comm.agent_results || {};
    
    // Extract individual agent summaries for backwards-compatibility rendering
    const research = agentResults["Research Agent"]?.summary || data.research_result?.summary || '';
    const market = agentResults["Market Agent"]?.summary || data.market_result?.summary || '';
    const competitor = agentResults["Competitor Agent"]?.summary || data.competitor_result?.summary || '';
    const risk = agentResults["Risk Agent"]?.summary || data.risk_result?.summary || '';
    
    const mlObj = agentResults["Prediction Agent"];
    const mlProb = mlObj ? mlObj.score : 75;
    const mlPred = mlObj ? (mlObj.score >= 50 ? 'Likely Success' : 'High Risk') : 'Likely Success';
    
    // overall risk is from Risk Agent score
    const riskObj = agentResults["Risk Agent"];
    // score 0-100 where higher is safer, let's map it to risk metric 0-10:
    const overallRisk = riskObj ? Math.round((100 - riskObj.score) / 10) : 5;

    // Extract conflicting agents for disagreement banner
    const conflictingAgents = comm.conflicting_agents || [];
    const spread = comm.spread !== undefined ? comm.spread : 0;

    return {
      companyName,
      verdict,
      score,
      overallConfidence,
      wasOverridden,
      overrideReason,
      hasDisagreement,
      disagreementNote,
      keyOpportunities,
      keyRisks,
      narrative,
      confidenceBreakdown,
      agentResults,
      research,
      market,
      competitor,
      risk,
      mlProb,
      mlPred,
      overallRisk,
      conflictingAgents,
      spread
    };
  };

  const parsed = normalizeData(data);

  // Trigger browser printing for PDF download
  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto print:bg-white print:text-black">
      {/* Header Actions */}
      <div className="flex items-center justify-between print:hidden">
        <button
          onClick={() => setActivePage('history')}
          className="flex items-center gap-2 text-xs text-gray-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Ingestion Archive
        </button>

        <button
          onClick={handlePrint}
          className="px-4 py-2 border border-[#1a1a22] text-xs text-gray-300 hover:text-white rounded-lg flex items-center gap-1.5 transition-colors"
        >
          <Download className="w-4 h-4" /> Download Report PDF
        </button>
      </div>

      {/* Disagreement Warning Banner */}
      <DisagreementBanner 
        hasDisagreement={parsed.hasDisagreement}
        note={parsed.disagreementNote}
        conflictingAgents={parsed.conflictingAgents}
        spread={parsed.spread}
      />

      {/* Hero Overview Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Core Profile Card */}
        <div className="glass-card p-6 flex flex-col justify-between lg:col-span-2">
          <div>
            <span className="text-[10px] font-mono text-purple-400 uppercase tracking-widest font-semibold">
              Venture Intelligence Ingress
            </span>
            <h1 className="text-3xl font-display font-extrabold text-white mt-3">
              {parsed.companyName}
            </h1>
            <p className="text-xs text-gray-400 mt-2 leading-relaxed">
              Synthesized on {new Date(data.created_at || Date.now()).toLocaleString()} using 8 structural committee nodes.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8 pt-6 border-t border-[#1a1a22]">
            <div>
              <span className="text-[9px] font-mono text-gray-500 uppercase tracking-wider block">Ingress Mode</span>
              <span className="text-xs font-semibold text-white mt-1 block">Trustworthy VC Committee</span>
            </div>
            <div>
              <span className="text-[9px] font-mono text-gray-500 uppercase tracking-wider block">ML Success Rate</span>
              <span className="text-xs font-semibold text-purple-400 mt-1 block">{parsed.mlProb}%</span>
            </div>
            <div>
              <span className="text-[9px] font-mono text-gray-500 uppercase tracking-wider block">Audit Risk Rank</span>
              <span className="text-xs font-semibold text-rose-400 mt-1 block">{parsed.overallRisk}/10</span>
            </div>
            <div>
              <span className="text-[9px] font-mono text-gray-500 uppercase tracking-wider block">Record DB Hash</span>
              <span className="text-xs font-mono text-gray-400 mt-1 block">#00{data.id || 'N/A'}</span>
            </div>
          </div>
        </div>

        {/* Verdict Score Widget */}
        <ScoreCard 
          score={parsed.score} 
          decision={parsed.verdict} 
          confidence={parsed.overallConfidence} 
          wasOverridden={parsed.wasOverridden}
          overrideReason={parsed.overrideReason}
        />
      </div>

      {/* Visual Analytics / Recharts Section */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Market Size Projection Area Chart */}
        <div className="glass-card p-6 flex flex-col justify-between">
          <div className="flex items-center gap-1.5 mb-4">
            <BarChart3 className="w-4 h-4 text-purple-400" />
            <h4 className="text-xs font-semibold text-gray-300">Projected Revenue Matrix</h4>
          </div>
          <MarketSizeChart revenue={10} growth={25} />
          <div className="text-[10px] text-gray-500 flex items-center gap-1 mt-4">
            <Info className="w-3.5 h-3.5 text-gray-600" /> Projected using startup YoY variables over 5 years.
          </div>
        </div>

        {/* Risk Radar Chart */}
        <div className="glass-card p-6 flex flex-col justify-between">
          <div className="flex items-center gap-1.5 mb-4">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            <h4 className="text-xs font-semibold text-gray-300">Audited Risk Radar</h4>
          </div>
          <RiskRadarChart overallScore={parsed.overallRisk} />
          <div className="text-[10px] text-gray-500 flex items-center gap-1 mt-4">
            <Info className="w-3.5 h-3.5 text-gray-600" /> Plotting risk margins calculated by Risk Agent.
          </div>
        </div>

        {/* ML Confidence Bar Chart */}
        <div className="glass-card p-6 flex flex-col justify-between">
          <div className="flex items-center gap-1.5 mb-4">
            <Cpu className="w-4 h-4 text-blue-400" />
            <h4 className="text-xs font-semibold text-gray-300">Model Success Probability</h4>
          </div>
          <MLConfidenceChart probability={parsed.mlProb} />
          <div className="text-[10px] text-gray-500 flex items-center gap-1 mt-4">
            <Info className="w-3.5 h-3.5 text-gray-600" /> Forest classifier compared to benchmarks.
          </div>
        </div>
      </div>

      {/* Committee Ruling */}
      <div className="glass-card p-6 border-purple-500/20 bg-purple-500/5 rounded-2xl space-y-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-purple-400 animate-pulse" />
          <h3 className="font-display font-extrabold text-white text-lg">Committee Synthesis Narrative</h3>
        </div>
        <p className="text-xs text-gray-300 leading-relaxed">
          {parsed.narrative}
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-[#1a1a22]">
          {/* Opportunities */}
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wider font-mono">Key Opportunities</h4>
            <ul className="list-disc pl-4 space-y-1.5 text-xs text-gray-400">
              {parsed.keyOpportunities.map((op, idx) => (
                <li key={idx}>{op}</li>
              ))}
              {parsed.keyOpportunities.length === 0 && <li>No specific opportunities flagged.</li>}
            </ul>
          </div>

          {/* Risks */}
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-rose-400 uppercase tracking-wider font-mono">Key Risks</h4>
            <ul className="list-disc pl-4 space-y-1.5 text-xs text-gray-400">
              {parsed.keyRisks.map((risk, idx) => (
                <li key={idx}>{risk}</li>
              ))}
              {parsed.keyRisks.length === 0 && <li>No specific risks flagged.</li>}
            </ul>
          </div>
        </div>
      </div>

      {/* Committee & Agent Output Reports */}
      <div className="space-y-6">
        <div className="pb-2 border-b border-[#1a1a22]">
          <h2 className="text-lg font-display font-bold text-white">Full Node Evaluations</h2>
          <p className="text-[11px] text-gray-500">Click any agent below to review details, points breakdown, and source links.</p>
        </div>

        {/* Scoring Breakdown Accordion */}
        <ScoreBreakdown agentResults={parsed.agentResults} />
      </div>
    </div>
  );
}
