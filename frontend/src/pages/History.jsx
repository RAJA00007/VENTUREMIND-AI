import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Search, Calendar, FolderOpen, AlertTriangle, Play, HelpCircle, ArrowUpRight } from 'lucide-react';
import { apiService } from '../api/api';

export default function History({ setActivePage, setSelectedReportId, setReportData }) {
  const [list, setList] = useState([]);
  const [filteredList, setFilteredList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [searchTerm, setSearchTerm] = useState('');
  const [filterVerdict, setFilterVerdict] = useState('ALL');

  useEffect(() => {
    async function loadHistory() {
      setLoading(true);
      setError('');
      try {
        const history = await apiService.getHistory();
        setList(history);
        setFilteredList(history);
      } catch (err) {
        console.error(err);
        setError('Could not connect to the backend server. Please verify FastAPI is running.');
      } finally {
        setLoading(false);
      }
    }
    loadHistory();
  }, []);

  useEffect(() => {
    // Filter history based on search and verdict selects
    let temp = [...list];
    
    if (searchTerm.trim() !== '') {
      temp = temp.filter(item => 
        item.company_name.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
    
    if (filterVerdict !== 'ALL') {
      temp = temp.filter(item => {
        let verdict = 'WATCH';
        if (item.final_decision) {
          if (item.final_decision.verdict) {
            verdict = item.final_decision.verdict.toUpperCase();
          } else if (item.final_decision.decision) {
            const decisionText = item.final_decision.decision.toUpperCase();
            if (decisionText.includes('INVEST')) verdict = 'INVEST';
            else if (decisionText.includes('PASS')) verdict = 'PASS';
            else verdict = 'WATCH';
          }
        }
        return verdict === filterVerdict;
      });
    }

    setFilteredList(temp);
  }, [searchTerm, filterVerdict, list]);

  const handleCardClick = (id) => {
    // Reset reportData so report.jsx loads from ID
    setReportData(null);
    setSelectedReportId(id);
    setActivePage('report');
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <div className="w-10 h-10 border-t-2 border-r-2 border-purple-500 rounded-full animate-spin"></div>
        <p className="text-xs text-gray-500 mt-4">Retrieving venture logs from database...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-md mx-auto py-12 text-center space-y-4">
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl text-xs">
          {error}
        </div>
        <button
          onClick={() => window.location.reload()}
          className="px-6 py-2 border border-[#1a1a22] text-xs text-gray-400 hover:text-white rounded-lg transition-colors"
        >
          Try Reconnecting
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      <div>
        <h2 className="text-2xl font-display font-extrabold text-white">VC Ingestion Archives</h2>
        <p className="text-xs text-gray-500 mt-1">Audit previous reports compiled by the investment committee.</p>
      </div>

      {/* Filter and Search Bar */}
      <div className="glass-card p-4 flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="relative w-full md:w-96">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search by company name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-black/30 border border-[#1f2029] rounded-xl pl-10 pr-4 py-2.5 text-xs text-white focus:outline-none focus:border-purple-500/50"
          />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto justify-end">
          <label className="text-[11px] font-mono text-gray-500 uppercase tracking-wider">Filter Verdict</label>
          <select
            value={filterVerdict}
            onChange={(e) => setFilterVerdict(e.target.value)}
            className="bg-[#0c0c0e] border border-[#1f2029] rounded-xl px-4 py-2.5 text-xs text-gray-300 focus:outline-none focus:border-purple-500/50"
          >
            <option value="ALL">All Verdicts</option>
            <option value="INVEST">Invest</option>
            <option value="WATCH">Watch</option>
            <option value="PASS">Pass</option>
          </select>
        </div>
      </div>

      {/* Archives List */}
      {filteredList.length === 0 ? (
        <div className="glass-card p-12 text-center flex flex-col items-center justify-center text-gray-500">
          <FolderOpen className="w-12 h-12 text-gray-700 mb-3" />
          <h3 className="text-sm font-semibold text-white">No archived records found</h3>
          <p className="text-xs mt-1">Ingest a startup first or adjust your filters.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredList.map((item) => {
            let score = 75;
            let verdict = 'WATCH';
            let badgeStyle = 'bg-amber-500/10 border-amber-500/20 text-amber-400';
            
            if (item.final_decision) {
              if (item.final_decision.final_score !== undefined) {
                score = item.final_decision.final_score;
              } else if (item.final_decision.decision) {
                const scoreMatch = item.final_decision.decision.match(/(\d+)\s*\/\s*100/) 
                  || item.final_decision.decision.match(/score:?\s*(\d+)/i) 
                  || item.final_decision.decision.match(/Score\b.*?(\d+)/);
                if (scoreMatch) {
                  score = parseInt(scoreMatch[1]);
                }
              }

              if (item.final_decision.verdict) {
                verdict = item.final_decision.verdict.toUpperCase();
              } else if (item.final_decision.decision) {
                const decisionText = item.final_decision.decision.toUpperCase();
                if (decisionText.includes('INVEST')) verdict = 'INVEST';
                else if (decisionText.includes('PASS')) verdict = 'PASS';
              }
            }

            if (verdict === 'INVEST') {
              badgeStyle = 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400';
            } else if (verdict === 'PASS') {
              badgeStyle = 'bg-rose-500/10 border-rose-500/20 text-rose-400';
            }

            return (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                onClick={() => handleCardClick(item.id)}
                className="glass-card glass-card-hover p-6 flex flex-col justify-between h-56 cursor-pointer group"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div className="w-10 h-10 rounded-lg bg-[#121216] border border-[#1d1d24] flex items-center justify-center font-display font-bold text-white group-hover:border-purple-500/30 transition-colors">
                      {item.company_name.substring(0, 2).toUpperCase()}
                    </div>
                    
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wide border ${badgeStyle}`}>
                      {verdict}
                    </span>
                  </div>

                  <h3 className="font-display font-bold text-base text-white mt-4 group-hover:text-purple-300 transition-colors">
                    {item.company_name}
                  </h3>
                  
                  <div className="flex items-center gap-1.5 text-[11px] text-gray-500 mt-2">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>Ingested {new Date(item.created_at).toLocaleDateString()}</span>
                  </div>
                </div>

                <div className="flex items-center justify-between border-t border-[#1a1a22] pt-4 mt-4">
                  <div className="flex items-baseline gap-1">
                    <span className="text-xl font-display font-extrabold text-white">{score}</span>
                    <span className="text-[10px] text-gray-500 font-mono">/ 100</span>
                  </div>

                  <span className="text-xs text-purple-400 group-hover:text-purple-300 font-medium flex items-center gap-0.5">
                    View report <ArrowUpRight className="w-3.5 h-3.5 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                  </span>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
