import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { 
  Search, 
  BarChart3, 
  ShieldAlert, 
  Cpu, 
  Layers, 
  ArrowUpRight, 
  Users, 
  Building2, 
  TrendingUp, 
  FileText 
} from 'lucide-react';
import AgentCard from '../components/AgentCard';
import { apiService } from '../api/api';

export default function Dashboard({ setActivePage, setSelectedReportId }) {
  const [stats, setStats] = useState({
    analyzedCount: 0,
    avgScore: 0,
    reportsCount: 0,
    recentAnalyses: []
  });

  const agents = [
    {
      name: 'AI Research Agent',
      role: 'Web & Document Intelligence',
      description: 'Scrapes live industry news, identifies funding profiles, analyzes founding teams, and queries internal ChromaDB RAG vector memory.',
      capabilities: ['Web Search', 'Traction Scraper', 'Founders Profile'],
      icon: Search,
    },
    {
      name: 'Market Agent',
      role: 'Financial & TAM sizing',
      description: 'Calculates TAM/SAM/SOM boundaries, aggregates market growth statistics, and assigns market opportunity indicators.',
      capabilities: ['TAM Estimator', 'CAGR Calculator', 'Demand Sizing'],
      icon: BarChart3,
    },
    {
      name: 'Competitor Agent',
      role: 'Market Rivalry Analyst',
      description: 'Scans the competitor matrix, highlights differentiators, evaluates product features, and maps defense moats.',
      capabilities: ['Rivals Grid', 'Moat Analysis', 'Feature Compare'],
      icon: Users,
    },
    {
      name: 'Risk Agent',
      role: 'Skeptical Auditor',
      description: 'Identifies technical scaling vulnerabilities, business viability bottlenecks, execution blindspots, and risk margins.',
      capabilities: ['Audit Risk', 'Execution Friction', 'Scale Vectors'],
      icon: ShieldAlert,
    },
    {
      name: 'ML Success Engine',
      role: 'Predictive Classifier',
      description: 'A pre-trained Random Forest model trained on historical VC datasets classifying probability of a subsequent round or acquisition.',
      capabilities: ['RF Classifier', 'Probability Index', 'Feature Weights'],
      icon: Cpu,
    },
    {
      name: 'RAG Pitch Deck Analyzer',
      role: 'Knowledge Ingestor',
      description: 'Ingests PDF pitch decks, extracts structural semantics, loads embeddings, and indexes them in ChromaDB vector space.',
      capabilities: ['PDF Loader', 'ChromaDB Embeddings', 'Context Search'],
      icon: Layers,
    },
  ];

  useEffect(() => {
    async function loadStats() {
      try {
        const history = await apiService.getHistory();
        
        let totalScore = 0;
        let validScoresCount = 0;

        history.forEach(item => {
          if (item.final_decision) {
            if (item.final_decision.final_score !== undefined) {
              totalScore += parseFloat(item.final_decision.final_score);
              validScoresCount++;
            } else if (item.final_decision.decision) {
              // Regex match score (e.g. 86 or 86/100 or Investment score: 86)
              const scoreMatch = item.final_decision.decision.match(/(\d+)\s*\/\s*100/) || item.final_decision.decision.match(/score:?\s*(\d+)/i) || item.final_decision.decision.match(/Score\b.*?(\d+)/);
              if (scoreMatch) {
                totalScore += parseInt(scoreMatch[1]);
                validScoresCount++;
              }
            }
          }
        });

        setStats({
          analyzedCount: history.length,
          avgScore: validScoresCount > 0 ? Math.round(totalScore / validScoresCount) : 0,
          reportsCount: history.length,
          recentAnalyses: history.slice(0, 3) // showing up to 3 recent ones
        });
      } catch (err) {
        console.error('Error fetching dashboard stats', err);
      }
    }
    loadStats();
  }, []);

  return (
    <div className="space-y-10 max-w-7xl mx-auto">
      {/* Hero Banner */}
      <div className="relative rounded-3xl p-8 md:p-12 overflow-hidden border border-[#1c1c22] bg-gradient-to-br from-[#0c0a1a] via-black to-[#050507]">
        {/* Background Gradients */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-purple-600/10 rounded-full blur-3xl -mr-16 -mt-16"></div>
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl -ml-16 -mb-16"></div>
        
        <div className="relative z-10 max-w-2xl">
          <span className="px-3.5 py-1.5 rounded-full border border-purple-500/30 bg-purple-500/5 text-purple-400 text-xs font-semibold tracking-wide uppercase">
            Venture Capital Intelligence Platform
          </span>
          <h1 className="text-4xl md:text-5xl font-display font-extrabold text-white mt-6 leading-tight">
            Analyze Startups with <span className="text-gradient-purple-blue">Multi-Agent Intelligence</span>
          </h1>
          <p className="text-sm text-gray-400 mt-4 leading-relaxed">
            Empower your investment decision-making. Upload pitch decks, model financial variables, and deploy specialized AI agents working as a synchronized committee to evaluate success rates and potential risks.
          </p>
          <div className="flex gap-4 mt-8">
            <button
              onClick={() => setActivePage('analyze')}
              className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white rounded-xl font-medium text-sm transition-all duration-200 shadow-lg shadow-purple-500/10 flex items-center gap-2 group"
            >
              Analyze New Startup
              <ArrowUpRight className="w-4 h-4 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </button>
            <button
              onClick={() => setActivePage('upload')}
              className="px-6 py-3 bg-black/40 border border-[#1c1c22] text-gray-300 hover:text-white hover:bg-black/60 rounded-xl font-medium text-sm transition-all duration-200"
            >
              Upload Pitch Deck
            </button>
          </div>
        </div>
      </div>

      {/* Stats Section */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        {[
          { label: 'Companies Analyzed', value: stats.analyzedCount, desc: 'Ingested into PostgreSQL', icon: Building2, color: 'text-purple-400 bg-purple-500/5' },
          { label: 'Average Investment Score', value: `${stats.avgScore || 0}%`, desc: 'Based on committee rulings', icon: TrendingUp, color: 'text-emerald-400 bg-emerald-500/5' },
          { label: 'Reports Generated', value: stats.reportsCount, desc: 'Agent reports active', icon: FileText, color: 'text-blue-400 bg-blue-500/5' },
        ].map((stat, i) => {
          const StatIcon = stat.icon;
          return (
            <div key={i} className="glass-card p-6 flex items-center justify-between">
              <div>
                <span className="text-[11px] text-gray-500 uppercase tracking-widest font-mono">{stat.label}</span>
                <h3 className="text-3xl font-display font-extrabold text-white mt-2">{stat.value}</h3>
                <span className="text-[10px] text-gray-400 mt-1 block">{stat.desc}</span>
              </div>
              <div className={`p-3 rounded-2xl border border-white/5 ${stat.color}`}>
                <StatIcon className="w-6 h-6" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Agents Section */}
      <div>
        <div className="mb-6">
          <h2 className="text-xl font-display font-bold text-white">Meet the Investment Committee</h2>
          <p className="text-xs text-gray-500 mt-1">Autonomous AI roles designed for structural VC evaluation</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {agents.map((agent, index) => (
            <AgentCard key={index} {...agent} status="idle" />
          ))}
        </div>
      </div>

      {/* Recent Analyses Table */}
      {stats.recentAnalyses.length > 0 && (
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-6 pb-2 border-b border-[#1a1a22]">
            <div>
              <h3 className="text-base font-display font-bold text-white">Recent Analyses</h3>
              <p className="text-[11px] text-gray-500 mt-0.5">Quick access to recently ingested startups</p>
            </div>
            <button
              onClick={() => setActivePage('history')}
              className="text-xs text-purple-400 hover:text-purple-300 font-medium flex items-center gap-1"
            >
              View archives
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="space-y-4">
            {stats.recentAnalyses.map((item) => {
              let score = '--';
              let decision = 'WATCH';
              if (item.final_decision) {
                if (item.final_decision.final_score !== undefined) {
                  score = item.final_decision.final_score;
                } else if (item.final_decision.decision) {
                  const match = item.final_decision.decision.match(/(\d+)\s*\/\s*100/) || item.final_decision.decision.match(/score:?\s*(\d+)/i) || item.final_decision.decision.match(/Score\b.*?(\d+)/);
                  score = match ? match[1] : '--';
                }
                
                if (item.final_decision.verdict) {
                  decision = item.final_decision.verdict;
                } else if (item.final_decision.decision) {
                  decision = item.final_decision.decision.includes('INVEST') ? 'INVEST' : item.final_decision.decision.includes('WATCH') ? 'WATCH' : 'PASS';
                }
              }
              
              return (
                <div 
                  key={item.id}
                  onClick={() => {
                    setSelectedReportId(item.id);
                    setActivePage('report');
                  }}
                  className="flex items-center justify-between p-4 rounded-xl border border-[#1a1a22] hover:border-purple-500/20 bg-black/20 hover:bg-black/40 cursor-pointer transition-all duration-200 group"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-[#121216] border border-[#1d1d24] flex items-center justify-center font-display font-bold text-white group-hover:border-purple-500/35 transition-colors">
                      {item.company_name.substring(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-white group-hover:text-purple-300 transition-colors">
                        {item.company_name}
                      </h4>
                      <p className="text-[11px] text-gray-500 mt-0.5">
                        Analyzed on {new Date(item.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    {/* Score */}
                    <div className="text-right">
                      <span className="text-[10px] text-gray-500 block uppercase tracking-wider font-mono">Score</span>
                      <span className="text-sm font-bold text-white">{score}/100</span>
                    </div>

                    {/* Verdict */}
                    <span className={`px-2.5 py-1 rounded-md text-[10px] font-bold tracking-wide border ${
                      decision === 'INVEST' 
                        ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                        : decision === 'WATCH' 
                          ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' 
                          : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                    }`}>
                      {decision}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
