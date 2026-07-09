import axios from 'axios';

// Create axios instance using Vite dev proxy
const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const apiService = {
  /**
   * Run multi-agent investment workflow for a startup
   * @param {Object} startupData
   * @returns {Promise<Object>} Analysis results
   */
  analyzeStartup: async (startupData) => {
    const response = await api.post('/analysis/startup', {
      company: startupData.company,
      industry: startupData.industry || 'AI',
      github_repo: startupData.github_repo || null,
      founder_names: startupData.founder_names || null,
      funding: parseFloat(startupData.funding) || 0,
      employees: parseInt(startupData.employees) || 0,
      age: parseInt(startupData.age) || 0,
      revenue: parseFloat(startupData.revenue) || 0,
      growth: parseFloat(startupData.growth) || 0,
    });
    return response.data;
  },

  /**
   * Fetch all historical reports
   * @returns {Promise<Array>} List of analyses
   */
  getHistory: async () => {
    const response = await api.get('/analysis/history');
    return response.data;
  },

  /**
   * Fetch details of a single report
   * @param {string|number} id
   * @returns {Promise<Object>} Analysis detail
   */
  getAnalysisDetail: async (id) => {
    const response = await api.get(`/analysis/${id}`);
    return response.data;
  },

  /**
   * Upload a pitch deck PDF file
   * @param {File} file
   * @returns {Promise<Object>} Ingestion status
   */
  uploadPitchDeck: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
};

export default api;
