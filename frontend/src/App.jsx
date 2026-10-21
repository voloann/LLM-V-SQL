import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Dashboard from './pages/Dashboard';
import Playground from './pages/Playground';
import Explorer from './pages/Explorer';
import Architecture from './pages/Architecture';
import ViewsCatalog from './pages/ViewsCatalog';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [collapsed, setCollapsed] = useState(false);
  
  const [health, setHealth] = useState(null);
  const [experiments, setExperiments] = useState(null);
  const [databases, setDatabases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [playgroundPrefill, setPlaygroundPrefill] = useState(null);

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
        const [hRes, expRes, dbRes] = await Promise.all([
          fetch('/api/health').then(r => r.json()).catch(() => null),
          fetch('/api/experiments').then(r => r.json()).catch(() => null),
          fetch('/api/databases').then(r => r.json()).catch(() => [])
        ]);
        setHealth(hRes);
        setExperiments(expRes);
        setDatabases(dbRes || []);
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
      />

      {/* Main Content Area */}
      <div className="main-content">
        <Header 
          activeTab={activeTab} 
          setActiveTab={setActiveTab} 
          health={health} 
        />

        <div className="content-body">
          {activeTab === 'dashboard' && (
            <Dashboard data={experiments} loading={loading} />
          )}

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
