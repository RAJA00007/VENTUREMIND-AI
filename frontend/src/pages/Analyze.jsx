import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { 
  Building2, 
  HelpCircle, 
  Sparkles,
  ArrowRight,
  GitBranch,
  Users
} from 'lucide-react';
import Loader from '../components/Loader';
import { apiService } from '../api/api';

export default function Analyze({ setActivePage, setReportData }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const [formData, setFormData] = useState({
    company: '',
    industry: 'AI',
    github_repo: '',
    founder_names: '',
  });

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.company.trim()) {
      setError('Company name is required');
      return;
    }
    
    setError('');
    setLoading(true);

    try {
      // Call endpoint
      const result = await apiService.analyzeStartup({
        company: formData.company,
        industry: formData.industry || 'AI',
        github_repo: formData.github_repo || null,
        founder_names: formData.founder_names || null,
      });

      // Save output in parent state
      setReportData(result);
      
      // Redirect to report view
      setActivePage('report');
    } catch (err) {
      console.error(err);
      setError(
        err.response?.data?.detail || 
        'An error occurred while generating the investment report. Please verify connection and try again.'
      );
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <Loader companyName={formData.company} />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h2 className="text-2xl font-display font-extrabold text-white">Ingest New Venture</h2>
        <p className="text-xs text-gray-500 mt-1">Deploy our trustworthy multi-agent committee to perform deep-dive startup diligence.</p>
      </div>

      <motion.div 
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-8 bg-[#0c0c0e]/90"
      >
        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="p-4 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl text-xs leading-relaxed">
              {error}
            </div>
          )}

          {/* Row 1: Company & Industry */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="flex flex-col gap-2">
              <label htmlFor="company" className="text-xs font-semibold text-gray-400 flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5" /> Company Name *
              </label>
              <input
                type="text"
                id="company"
                name="company"
                required
                placeholder="e.g. OpenAI"
                value={formData.company}
                onChange={handleInputChange}
                className="glass-input"
              />
            </div>

            <div className="flex flex-col gap-2">
              <label htmlFor="industry" className="text-xs font-semibold text-gray-400 flex items-center gap-1.5">
                <HelpCircle className="w-3.5 h-3.5" /> Industry
              </label>
              <input
                type="text"
                id="industry"
                name="industry"
                placeholder="e.g. AI, SaaS, Web3"
                value={formData.industry}
                onChange={handleInputChange}
                className="glass-input"
              />
            </div>
          </div>

          {/* Row 2: GitHub Repo & Founder Names */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="flex flex-col gap-2">
              <label htmlFor="github_repo" className="text-xs font-semibold text-gray-400 flex items-center gap-1.5">
                <GitBranch className="w-3.5 h-3.5" /> GitHub Repository (Optional)
              </label>
              <input
                type="text"
                id="github_repo"
                name="github_repo"
                placeholder="e.g. https://github.com/org/repo or org/repo"
                value={formData.github_repo}
                onChange={handleInputChange}
                className="glass-input"
              />
            </div>

            <div className="flex flex-col gap-2">
              <label htmlFor="founder_names" className="text-xs font-semibold text-gray-400 flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5" /> Founder Names (Optional)
              </label>
              <input
                type="text"
                id="founder_names"
                name="founder_names"
                placeholder="e.g. Sam Altman, Greg Brockman (comma-separated)"
                value={formData.founder_names}
                onChange={handleInputChange}
                className="glass-input"
              />
            </div>
          </div>

          <div className="pt-4 border-t border-[#1a1a22] flex justify-end">
            <button
              type="submit"
              className="w-full md:w-auto px-8 py-3.5 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white rounded-xl font-medium text-sm transition-all duration-200 shadow-lg shadow-purple-500/10 flex items-center justify-center gap-2 group"
            >
              <Sparkles className="w-4 h-4 text-purple-200" />
              Run AI Investment Analysis
              <ArrowRight className="w-4 h-4 text-purple-200 transition-transform duration-200 group-hover:translate-x-0.5" />
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}
