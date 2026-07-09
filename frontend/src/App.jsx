import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Analyze from './pages/Analyze';
import Report from './pages/Report';
import Upload from './pages/Upload';
import History from './pages/History';

export default function App() {
  const [activePage, setActivePage] = useState('dashboard');
  const [selectedReportId, setSelectedReportId] = useState(null);
  const [reportData, setReportData] = useState(null);

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard':
        return (
          <Dashboard 
            setActivePage={setActivePage} 
            setSelectedReportId={setSelectedReportId} 
          />
        );
      case 'analyze':
        return (
          <Analyze 
            setActivePage={setActivePage} 
            setReportData={setReportData} 
          />
        );
      case 'report':
        return (
          <Report 
            reportData={reportData} 
            reportId={selectedReportId} 
            setActivePage={setActivePage} 
          />
        );
      case 'upload':
        return <Upload />;
      case 'history':
        return (
          <History 
            setActivePage={setActivePage} 
            setSelectedReportId={setSelectedReportId} 
            setReportData={setReportData}
          />
        );
      default:
        return (
          <Dashboard 
            setActivePage={setActivePage} 
            setSelectedReportId={setSelectedReportId} 
          />
        );
    }
  };

  return (
    <div className="min-h-screen bg-[#030303] flex">
      {/* Navigation Sidebar */}
      <Sidebar activePage={activePage} setActivePage={setActivePage} />

      {/* Main Content Area */}
      <div className="flex-1 ml-64 flex flex-col min-h-screen">
        {/* Global Navbar */}
        <Navbar activePage={activePage} />

        {/* Dynamic Page Container */}
        <main className="flex-1 p-8 overflow-y-auto">
          {renderPage()}
        </main>
      </div>
    </div>
  );
}
