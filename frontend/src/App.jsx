import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Dashboard from './pages/Dashboard';
import Playground from './pages/Playground';
import Explorer from './pages/Explorer';
import Architecture from './pages/Architecture';
import ViewsCatalog from './pages/ViewsCatalog';
import PipelineDemo from './pages/PipelineDemo';
import Journey from './pages/Journey';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [collapsed, setCollapsed] = useState(() => window.innerWidth < 1000);
  
  const [health, setHealth] = useState(null);
  const [experiments, setExperiments] = useState(null);
  const [databases, setDatabases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [playgroundPrefill, setPlaygroundPrefill] = useState(null);
  const [pipelinePrefill, setPipelinePrefill] = useState(null);
  const [runs, setRuns] = useState([]);
  const [main, setMain] = useState({ keys: [], mechanism: {} });

  const handleTryQuestion = (item) => {
    setPlaygroundPrefill({
      db_id: item.db_id,
      question: item.question,
      evidence: item.evidence || ''
    });
    setActiveTab('playground');
  };

  const refreshHealth = async () => {
    try {
      const res = await fetch('/api/health');
      const data = await res.json();
      setHealth(data);
      return data;
    } catch (err) {
      console.error('Lỗi khi làm mới trạng thái:', err);
      return null;
    }
  };

  useEffect(() => {
    async function loadInitialData() {
      try {
        const [hRes, expRes, dbRes, runsRes] = await Promise.all([
          fetch('/api/health').then(r => r.json()).catch(() => null),
          fetch('/api/experiments').then(r => r.json()).catch(() => null),
          fetch('/api/databases').then(r => r.json()).catch(() => []),
          fetch('/api/runs').then(r => r.json()).catch(() => null)
        ]);
        setHealth(hRes);
        setExperiments(expRes);
        setDatabases(dbRes || []);
        setRuns(runsRes?.runs || []);
        setMain({ keys: runsRes?.main_runs || [], mechanism: runsRes?.mechanism || {} });
      } catch (err) {
        console.error('Lỗi khi nạp dữ liệu ban đầu:', err);
      } finally {
        setLoading(false);
      }
    }
    loadInitialData();
  }, []);

  return (
    <div className="app-container">
      {/* Collapsible Left Sidebar */}
      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        collapsed={collapsed} 
        setCollapsed={setCollapsed}
        health={health}
        runs={runs}
      />

      {/* Main Content Area */}
      <div className="main-content">
        <Header 
          activeTab={activeTab} 
          setActiveTab={setActiveTab} 
          health={health}
          runs={runs}
        />

        <div className="content-body">
          {activeTab === 'dashboard' && (
            <Dashboard data={experiments} loading={loading} runs={runs} main={main} />
          )}

          {activeTab === 'journey' && (
            <Journey onReplay={(key) => { setPipelinePrefill({ replay_run: key }); setActiveTab('pipeline'); }} />
          )}

          {/* Stays mounted so a running pipeline survives switching tabs during a presentation. */}
          <div style={{ display: activeTab === 'pipeline' ? 'block' : 'none' }}>
            <PipelineDemo prefill={pipelinePrefill} />
          </div>

          {activeTab === 'playground' && (
            <Playground 
              databases={databases} 
              prefill={playgroundPrefill} 
              health={health}
              onRefreshHealth={refreshHealth}
              onNavigateTab={setActiveTab}
            />
          )}

          {activeTab === 'explorer' && (
            <Explorer 
              runs={runs}
              main={main}
              databases={databases} 
              onTryQuestion={handleTryQuestion}
            />
          )}

          {activeTab === 'architecture' && (
            <Architecture />
          )}

          {activeTab === 'views_catalog' && (
            <ViewsCatalog 
              databases={databases} 
              onTryQuestion={handleTryQuestion} 
              onNavigateTab={setActiveTab} 
            />
          )}
        </div>
      </div>
    </div>
  );
}
