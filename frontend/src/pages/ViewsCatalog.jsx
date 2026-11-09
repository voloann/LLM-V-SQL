import React, { useState, useMemo } from 'react';
import { 
  Database, 
  Layers, 
  Table as TableIcon, 
  Sparkles, 
  CheckCircle2, 
  Copy, 
  Check, 
  Search, 
  Eye, 
  Play,
  HelpCircle,
  GitMerge,
  ArrowRight,
  Columns,
  Code2
} from 'lucide-react';
import { formatSql } from '../utils/sqlFormatter';

export default function ViewsCatalog({ databases, onTryQuestion, onNavigateTab }) {
  const [selectedDbId, setSelectedDbId] = useState('superhero');
  const [activeSubTab, setActiveSubTab] = useState('views'); // 'views', 'physical', 'comparison', 'samples'
  const [searchDb, setSearchDb] = useState('');
  const [copiedKey, setCopiedKey] = useState(null);
  // View mode for each view card: { [viewName]: 'columns' | 'ddl' }
  const [viewTabModes, setViewTabModes] = useState({});

  const copyToClipboard = (text, key) => {
    if (!text) return;
    navigator.clipboard.writeText(formatSql(text));
    setCopiedKey(key);
    setTimeout(() => {
      setCopiedKey(null);
    }, 2000);
  };

  const getViewMode = (name) => viewTabModes[name] || 'columns';
  const setViewMode = (name, mode) => {
    setViewTabModes(prev => ({ ...prev, [name]: mode }));
  };

  // Filtered databases list
  const filteredDatabases = useMemo(() => {
    if (!databases || databases.length === 0) return [];
    if (!searchDb.trim()) return databases;
    const q = searchDb.toLowerCase();
    return databases.filter(d => d.db_id.toLowerCase().includes(q));
  }, [databases, searchDb]);

  // Current active database object
  const currentDb = useMemo(() => {
    if (!databases || databases.length === 0) return null;
    return databases.find(d => d.db_id === selectedDbId) || databases[0];
  }, [databases, selectedDbId]);

  if (!databases || databases.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '320px', color: '#64748b' }}>
        <Sparkles size={20} className="animate-spin" style={{ marginRight: '8px', color: '#4f46e5' }} />
        <span>Đang nạp danh mục Views và Lược đồ 11 CSDL...</span>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      
      {/* 1. COMPACT TOP SUMMARY RIBBON (Sleek, No Wall of Text) */}
      <div 
        style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          padding: '8px 14px', 
          background: '#ffffff',
          borderRadius: '9px',
          border: '1px solid #e2e8f0',
          boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          flexWrap: 'wrap',
          gap: '10px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span 
            style={{ 
              fontSize: '0.68rem', 
              fontWeight: '700', 
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              padding: '2px 7px',
              borderRadius: '5px',
              background: '#e0e7ff',
              color: '#4338ca'
            }}
          >
            Pha 1 · Table Mapping
          </span>
          <span style={{ fontSize: '0.8rem', color: '#475569' }}>
            Nhóm các bảng có quan hệ khóa ngoại thành View phẳng <code style={{ color: '#4f46e5', fontWeight: '600' }}>v_*</code> mà không sửa SQLite gốc. Đây là bộ 43 view của cấu hình chính.
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', fontSize: '0.78rem' }}>
          <span style={{ color: '#64748b' }}>CSDL: <b style={{ color: '#0f172a' }}>11</b></span>
          <span style={{ color: '#64748b' }}>Views: <b style={{ color: '#4338ca' }}>{(databases || []).reduce((sum, db) => sum + (db.view_count ?? 0), 0)}</b></span>
          <span style={{ color: '#64748b' }}>Bảng gốc: <b style={{ color: '#0f172a' }}>75</b></span>
        </div>
      </div>

      {/* 2. TWO-PANE EXPLORER LAYOUT */}
      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: '1rem', alignItems: 'flex-start' }}>
        
        {/* LEFT PANE: CLEAN DATABASE SELECTOR LIST */}
        <div className="card" style={{ padding: '0.75rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 4px', marginBottom: '2px' }}>
            <span style={{ fontSize: '0.78rem', fontWeight: '700', color: '#0f172a' }}>
              CSDL Benchmark
            </span>
            <span style={{ fontSize: '0.68rem', color: '#64748b', background: '#f1f5f9', padding: '1px 6px', borderRadius: '4px', fontWeight: '600' }}>
              {filteredDatabases.length} / 11
            </span>
          </div>

          {/* Search DB Input */}
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
            <input
              type="text"
              value={searchDb}
              onChange={(e) => setSearchDb(e.target.value)}
              placeholder="Lọc CSDL..."
              style={{
                width: '100%',
                padding: '4px 6px 4px 26px',
                borderRadius: '6px',
                border: '1px solid #cbd5e1',
                fontSize: '0.76rem',
                outline: 'none',
                background: '#ffffff'
              }}
            />
          </div>

          {/* DB List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', maxHeight: '680px', overflowY: 'auto', paddingRight: '1px' }}>
            {filteredDatabases.map((db) => {
              const isSelected = db.db_id === selectedDbId;
              const viewCount = db.view_count ?? db.parsed_views?.length ?? 0;
              const tableCount = db.physical_tables?.length ?? 0;
              const reduction = db.reduction_pct ?? 0;

              return (
                <div
                  key={db.db_id}
                  onClick={() => setSelectedDbId(db.db_id)}
                  style={{
                    padding: '7px 9px',
                    borderRadius: '7px',
                    cursor: 'pointer',
                    border: isSelected ? '1px solid #6366f1' : '1px solid transparent',
                    background: isSelected ? '#eef2ff' : 'transparent',
                    transition: 'all 0.12s ease'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ 
                      fontWeight: isSelected ? '700' : '600', 
                      fontSize: '0.8rem', 
                      color: isSelected ? '#4338ca' : '#1e293b',
                      fontFamily: 'var(--font-mono)'
                    }}>
                      {db.db_id}
                    </span>
                    <span style={{ 
                      fontSize: '0.66rem', 
                      fontWeight: '700',
                      color: reduction >= 70 ? '#15803d' : reduction >= 50 ? '#0284c7' : '#c2410c',
                      background: reduction >= 70 ? '#dcfce7' : reduction >= 50 ? '#f0f9ff' : '#ffedd5',
                      padding: '1px 5px',
                      borderRadius: '4px',
                      whiteSpace: 'nowrap'
                    }}>
                      -{reduction}%
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.69rem', color: '#64748b', marginTop: '2px' }}>
                    <span>📁 {viewCount} views</span>
                    <span>•</span>
                    <span>🗄️ {tableCount} bảng</span>
                  </div>
                </div>
              );
            })}
          </div>

        </div>

        {/* RIGHT PANE: SELECTED DATABASE DETAIL */}
        {currentDb && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
            
            {/* DB Profile Header Card */}
            <div className="card" style={{ padding: '0.875rem 1.15rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ 
                    width: '34px', 
                    height: '34px', 
                    borderRadius: '8px', 
                    background: '#eef2ff', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center',
                    border: '1px solid #c7d2fe'
                  }}>
                    <Database size={18} color="#4f46e5" />
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <h3 style={{ fontSize: '1.05rem', fontWeight: '800', color: '#0f172a', margin: 0, fontFamily: 'var(--font-mono)' }}>
                        {currentDb.db_id}
                      </h3>
                      <span style={{ fontSize: '0.7rem', color: '#64748b', background: '#f1f5f9', padding: '1px 6px', borderRadius: '4px', fontFamily: 'var(--font-mono)' }}>
                        {currentDb.db_id}.sqlite
                      </span>
                    </div>
                  </div>
                </div>

                {/* Metrics Ribbon & Playground Link */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px', 
                    background: '#f8fafc', 
                    border: '1px solid #e2e8f0', 
                    padding: '4px 10px', 
                    borderRadius: '7px',
                    fontSize: '0.74rem'
                  }}>
                    <span style={{ color: '#64748b' }}>Gộp: <b style={{ color: '#0f172a' }}>{currentDb.physical_tables?.length || 0} bảng ➔ {currentDb.parsed_views?.length || 0} views</b></span>
                    <span style={{ color: '#cbd5e1' }}>|</span>
                    <span style={{ color: '#16a34a', fontWeight: '700' }}>Stage 1 giảm {currentDb.reduction_pct ?? 0}% JOIN so với gold</span>
                  </div>

                  {onNavigateTab && (
                    <button
                      onClick={() => onNavigateTab('playground')}
                      className="btn btn-primary"
                      style={{ padding: '5px 10px', fontSize: '0.75rem', gap: '5px' }}
                    >
                      <Play size={12} /> Thử trong Playground
                    </button>
                  )}
                </div>
              </div>

              {/* Sub-Tab Navigation (Clean, Underline Tabs) */}
              <div 
                style={{ 
                  display: 'flex', 
                  gap: '4px', 
                  borderBottom: '1px solid #e2e8f0', 
                  marginTop: '0.875rem', 
                  paddingBottom: '0px',
                  overflowX: 'auto',
                  scrollbarWidth: 'none'
                }}
              >
                <button
                  onClick={() => setActiveSubTab('views')}
                  style={{
                    padding: '7px 12px',
                    borderRadius: '6px 6px 0 0',
                    fontSize: '0.8rem',
                    fontWeight: activeSubTab === 'views' ? '700' : '500',
                    border: 'none',
                    borderBottom: activeSubTab === 'views' ? '2px solid #4f46e5' : '2px solid transparent',
                    background: activeSubTab === 'views' ? '#eef2ff' : 'transparent',
                    color: activeSubTab === 'views' ? '#4f46e5' : '#64748b',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    whiteSpace: 'nowrap',
                    flexShrink: 0
                  }}
                >
                  <Eye size={14} /> Views Khái niệm ({currentDb.parsed_views?.length ?? currentDb.view_count ?? 0})
                </button>

                <button
                  onClick={() => setActiveSubTab('physical')}
                  style={{
                    padding: '7px 12px',
                    borderRadius: '6px 6px 0 0',
                    fontSize: '0.8rem',
                    fontWeight: activeSubTab === 'physical' ? '700' : '500',
                    border: 'none',
                    borderBottom: activeSubTab === 'physical' ? '2px solid #4f46e5' : '2px solid transparent',
                    background: activeSubTab === 'physical' ? '#eef2ff' : 'transparent',
                    color: activeSubTab === 'physical' ? '#4f46e5' : '#64748b',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    whiteSpace: 'nowrap',
                    flexShrink: 0
                  }}
                >
                  <TableIcon size={14} /> Bảng Vật lý ({currentDb.physical_tables?.length ?? 0})
                </button>

                <button
                  onClick={() => setActiveSubTab('comparison')}
                  style={{
                    padding: '7px 12px',
                    borderRadius: '6px 6px 0 0',
                    fontSize: '0.8rem',
                    fontWeight: activeSubTab === 'comparison' ? '700' : '500',
                    border: 'none',
                    borderBottom: activeSubTab === 'comparison' ? '2px solid #4f46e5' : '2px solid transparent',
                    background: activeSubTab === 'comparison' ? '#eef2ff' : 'transparent',
                    color: activeSubTab === 'comparison' ? '#4f46e5' : '#64748b',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    whiteSpace: 'nowrap',
                    flexShrink: 0
                  }}
                >
                  <GitMerge size={14} /> Đối chiếu Lược đồ
                </button>

                <button
                  onClick={() => setActiveSubTab('samples')}
                  style={{
                    padding: '7px 12px',
                    borderRadius: '6px 6px 0 0',
                    fontSize: '0.8rem',
                    fontWeight: activeSubTab === 'samples' ? '700' : '500',
                    border: 'none',
                    borderBottom: activeSubTab === 'samples' ? '2px solid #4f46e5' : '2px solid transparent',
                    background: activeSubTab === 'samples' ? '#eef2ff' : 'transparent',
                    color: activeSubTab === 'samples' ? '#4f46e5' : '#64748b',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    whiteSpace: 'nowrap',
                    flexShrink: 0
                  }}
                >
                  <HelpCircle size={14} /> Câu hỏi Mẫu ({currentDb.samples?.length ?? 0})
                </button>
              </div>
            </div>

            {/* SUB-TAB 1: CONCEPTUAL VIEWS (Clean Cards with Segmented Mode: Columns vs DDL) */}
            {activeSubTab === 'views' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
                {currentDb.parsed_views && currentDb.parsed_views.length > 0 ? (
                  currentDb.parsed_views.map((v, idx) => {
                    const currentMode = getViewMode(v.name);
                    return (
                      <div 
                        key={idx} 
                        className="card" 
                        style={{ 
                          padding: '1rem',
                          borderTop: '3px solid #6366f1',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '10px'
                        }}
                      >
                        {/* Top Row: View Name, Row Count, and Segmented View Toggle */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ 
                              width: '22px', 
                              height: '22px', 
                              borderRadius: '50%', 
                              background: '#4f46e5', 
                              color: '#fff', 
                              fontSize: '0.72rem', 
                              fontWeight: '700', 
                              display: 'inline-flex', 
                              alignItems: 'center', 
                              justifyContent: 'center' 
                            }}>
                              {idx + 1}
                            </span>
                            <span style={{ fontSize: '0.96rem', fontWeight: '800', color: '#0f172a', fontFamily: 'var(--font-mono)' }}>
                              {v.name}
                            </span>
                            <span style={{ 
                              fontSize: '0.68rem', 
                              fontWeight: '700',
                              padding: '1px 6px',
                              borderRadius: '4px',
                              background: '#dcfce7',
                              color: '#15803d'
                            }}>
                              Hợp lệ (Valid)
                            </span>
                            {v.row_count !== undefined && (
                              <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
                                • {v.row_count.toLocaleString()} dòng
                              </span>
                            )}
                          </div>

                          {/* Segmented Controls: [ Thuộc tính (N) ] vs [ Mã DDL SQL ] */}
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <div style={{ 
                              display: 'inline-flex', 
                              background: '#f1f5f9', 
                              padding: '2px', 
                              borderRadius: '6px',
                              border: '1px solid #e2e8f0'
                            }}>
                              <button
                                onClick={() => setViewMode(v.name, 'columns')}
                                style={{
                                  padding: '3px 8px',
                                  fontSize: '0.72rem',
                                  fontWeight: currentMode === 'columns' ? '700' : '500',
                                  border: 'none',
                                  borderRadius: '4px',
                                  background: currentMode === 'columns' ? '#ffffff' : 'transparent',
                                  color: currentMode === 'columns' ? '#4f46e5' : '#64748b',
                                  cursor: 'pointer',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  boxShadow: currentMode === 'columns' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none'
                                }}
                              >
                                <Columns size={12} /> Cột ({v.columns?.length || 0})
                              </button>
                              <button
                                onClick={() => setViewMode(v.name, 'ddl')}
                                style={{
                                  padding: '3px 8px',
                                  fontSize: '0.72rem',
                                  fontWeight: currentMode === 'ddl' ? '700' : '500',
                                  border: 'none',
                                  borderRadius: '4px',
                                  background: currentMode === 'ddl' ? '#ffffff' : 'transparent',
                                  color: currentMode === 'ddl' ? '#4f46e5' : '#64748b',
                                  cursor: 'pointer',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  boxShadow: currentMode === 'ddl' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none'
                                }}
                              >
                                <Code2 size={12} /> DDL (SQL)
                              </button>
                            </div>

                            <button
                              onClick={() => copyToClipboard(v.create_sql, `view_${idx}`)}
                              className="btn btn-secondary"
                              style={{ padding: '3px 8px', fontSize: '0.72rem', height: '26px', gap: '4px' }}
                              title="Sao chép câu lệnh CREATE VIEW"
                            >
                              {copiedKey === `view_${idx}` ? <><Check size={11} color="#16a34a" /> Đã chép</> : <><Copy size={11} /> Chép DDL</>}
                            </button>
                          </div>
                        </div>

                        {/* Visual Mapping Flow: Bảng gốc gộp vào View này */}
                        <div style={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          gap: '6px', 
                          flexWrap: 'wrap',
                          background: '#f8fafc',
                          padding: '6px 10px',
                          borderRadius: '6px',
                          border: '1px solid #f1f5f9'
                        }}>
                          <span style={{ fontSize: '0.7rem', fontWeight: '700', color: '#64748b' }}>
                            Gộp {v.source_tables?.length || 0} bảng:
                          </span>
                          {v.source_tables?.map((st, i) => (
                            <span 
                              key={i} 
                              style={{ 
                                fontSize: '0.7rem', 
                                background: '#e0e7ff', 
                                color: '#3730a3', 
                                padding: '1px 6px', 
                                borderRadius: '4px', 
                                fontWeight: '600', 
                                fontFamily: 'var(--font-mono)' 
                              }}
                            >
                              {st}
                            </span>
                          ))}
                          <ArrowRight size={12} color="#94a3b8" />
                          <span style={{ 
                            fontSize: '0.7rem', 
                            background: '#ecfdf5', 
                            color: '#065f46', 
                            border: '1px solid #a7f3d0', 
                            padding: '1px 6px', 
                            borderRadius: '4px', 
                            fontWeight: '700', 
                            fontFamily: 'var(--font-mono)' 
                          }}>
                            {v.name}
                          </span>
                        </div>

                        {/* MODE 1: STRUCTURED 3-4 COLUMN GRID FOR ATTRIBUTES */}
                        {currentMode === 'columns' && (
                          <div style={{ marginTop: '2px' }}>
                            <div style={{ 
                              display: 'grid', 
                              gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))', 
                              gap: '6px',
                              maxHeight: '180px',
                              overflowY: 'auto',
                              paddingRight: '2px'
                            }}>
                              {v.columns?.map((c, i) => (
                                <div 
                                  key={i} 
                                  style={{ 
                                    display: 'flex', 
                                    alignItems: 'center', 
                                    gap: '6px', 
                                    padding: '4px 8px', 
                                    background: '#ffffff', 
                                    border: '1px solid #e2e8f0', 
                                    borderRadius: '5px',
                                    fontSize: '0.74rem',
                                    fontFamily: 'var(--font-mono)',
                                    color: '#334155'
                                  }}
                                  title={c}
                                >
                                  <span style={{ color: '#94a3b8', fontSize: '0.68rem', userSelect: 'none' }}>#</span>
                                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* MODE 2: HIGH CONTRAST DDL PREVIEW */}
                        {currentMode === 'ddl' && (
                          <div style={{ 
                            background: '#0f172a', 
                            border: '1px solid #1e293b', 
                            borderRadius: '6px', 
                            overflow: 'hidden' 
                          }}>
                            <div style={{ 
                              display: 'flex', 
                              justifyContent: 'space-between', 
                              alignItems: 'center', 
                              padding: '4px 10px', 
                              background: '#1e293b', 
                              borderBottom: '1px solid #334155' 
                            }}>
                              <span style={{ fontSize: '0.68rem', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>
                                CREATE VIEW DDL · Dialect: SQLite
                              </span>
                              <span style={{ fontSize: '0.68rem', color: '#38bdf8', fontWeight: '600' }}>
                                Phase 1 Mapping
                              </span>
                            </div>
                            <pre style={{
                              padding: '10px 12px',
                              fontSize: '0.76rem',
                              color: '#f8fafc',
                              margin: 0,
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                              lineHeight: '1.45',
                              fontFamily: 'var(--font-mono)',
                              maxHeight: '200px',
                              overflowY: 'auto'
                            }}>
                              {formatSql(v.create_sql)}
                            </pre>
                          </div>
                        )}

                      </div>
                    );
                  })
                ) : (
                  <div className="card" style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
                    Chưa có cấu hình View cho CSDL này.
                  </div>
                )}
              </div>
            )}

            {/* SUB-TAB 2: PHYSICAL TABLES (Clean Compact Grid) */}
            {activeSubTab === 'physical' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {currentDb.physical_tables && currentDb.physical_tables.length > 0 ? (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '0.75rem' }}>
                    {currentDb.physical_tables.map((t, idx) => (
                      <div key={idx} className="card" style={{ padding: '0.75rem 0.9rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                          <span style={{ fontWeight: '700', fontSize: '0.85rem', color: '#0f172a', fontFamily: 'var(--font-mono)' }}>
                            🗄️ {t.name}
                          </span>
                          <span style={{ fontSize: '0.68rem', fontWeight: '600', background: '#f1f5f9', color: '#475569', padding: '1px 5px', borderRadius: '4px' }}>
                            {t.row_count?.toLocaleString()} dòng
                          </span>
                        </div>

                        <div style={{ fontSize: '0.7rem', color: '#64748b', marginBottom: '6px' }}>
                          {t.columns?.length || 0} cột thuộc tính gốc
                        </div>

                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '3px', maxHeight: '100px', overflowY: 'auto' }}>
                          {t.columns?.map((c, i) => (
                            <span key={i} style={{ fontSize: '0.67rem', background: '#f8fafc', border: '1px solid #e2e8f0', color: '#334155', padding: '1px 5px', borderRadius: '3px', fontFamily: 'var(--font-mono)' }}>
                              {c}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="card" style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
                    (Thông tin các bảng vật lý được trích xuất trực tiếp từ file SQLite gốc)
                  </div>
                )}
              </div>
            )}

            {/* SUB-TAB 3: SCHEMA COMPARISON (Visual Mapping Table) */}
            {activeSubTab === 'comparison' && (
              <div className="card" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                  <div>
                    <h4 style={{ fontSize: '0.92rem', fontWeight: '700', color: '#0f172a', margin: 0 }}>
                      Đối chiếu Lược đồ: CSDL Gốc vs Views Khái niệm Phẳng
                    </h4>
                    <p style={{ margin: '2px 0 0 0', fontSize: '0.74rem', color: '#64748b' }}>
                      Bản chất cốt lõi: Gom nhiều bảng quan hệ thành một bảng phẳng duy nhất ở Pha 1 để triệt tiêu JOINs.
                    </p>
                  </div>

                  <span style={{ 
                    fontSize: '0.72rem', 
                    fontWeight: '700', 
                    background: '#ecfdf5', 
                    color: '#059669', 
                    border: '1px solid #a7f3d0',
                    padding: '2px 7px', 
                    borderRadius: '5px' 
                  }}>
                    Stage 1 giảm {currentDb.reduction_pct ?? 0}% JOIN so với gold
                  </span>
                </div>

                {/* 3 Metric Cards for Before vs After */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                  <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '7px', padding: '8px 10px', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.68rem', color: '#64748b' }}>Số bảng cần xử lý</div>
                    <div style={{ fontSize: '0.86rem', fontWeight: '700', color: '#0f172a', marginTop: '2px' }}>
                      {currentDb.physical_tables?.length || 0} bảng ➔ <span style={{ color: '#4f46e5' }}>{currentDb.parsed_views?.length || 0} views</span>
                    </div>
                  </div>

                  <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '7px', padding: '8px 10px', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.68rem', color: '#64748b' }}>Số phép JOIN trung bình</div>
                    <div style={{ fontSize: '0.86rem', fontWeight: '700', color: '#0f172a', marginTop: '2px' }}>
                      {currentDb.gold_joins ?? 0} ➔ <span style={{ color: '#0284c7' }}>{currentDb.dummy_joins ?? 0}</span>
                    </div>
                  </div>

                  <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '7px', padding: '8px 10px', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.68rem', color: '#166534' }}>Nguy cơ FK Hallucination</div>
                    <div style={{ fontSize: '0.86rem', fontWeight: '800', color: '#15803d', marginTop: '2px' }}>
                      Triệt tiêu hoàn toàn
                    </div>
                  </div>
                </div>

                {/* Mapping Breakdown Rows */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '4px' }}>
                  <span style={{ fontSize: '0.74rem', fontWeight: '700', color: '#475569' }}>
                    Chi tiết các phép gộp bảng:
                  </span>
                  {currentDb.parsed_views?.map((v, i) => (
                    <div 
                      key={i} 
                      style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'space-between',
                        padding: '8px 12px', 
                        background: '#ffffff', 
                        border: '1px solid #e2e8f0', 
                        borderRadius: '6px',
                        flexWrap: 'wrap',
                        gap: '8px'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '0.78rem', fontWeight: '700', color: '#0f172a', fontFamily: 'var(--font-mono)' }}>
                          {v.name}
                        </span>
                        <span style={{ fontSize: '0.7rem', color: '#64748b' }}>được gộp từ:</span>
                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                          {v.source_tables?.map((st, j) => (
                            <span key={j} style={{ fontSize: '0.7rem', background: '#f1f5f9', color: '#334155', padding: '1px 5px', borderRadius: '3px', fontFamily: 'var(--font-mono)' }}>
                              {st}
                            </span>
                          ))}
                        </div>
                      </div>

                      <span style={{ fontSize: '0.7rem', color: '#15803d', fontWeight: '600', background: '#dcfce7', padding: '1px 6px', borderRadius: '4px' }}>
                        {v.columns?.length || 0} cột phẳng
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* SUB-TAB 4: SAMPLE QUESTIONS */}
            {activeSubTab === 'samples' && (
              <div className="card" style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h4 style={{ fontSize: '0.92rem', fontWeight: '700', color: '#0f172a', margin: 0 }}>
                    Câu hỏi Mẫu BIRD Benchmark ({currentDb.db_id})
                  </h4>
                  <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
                    {currentDb.samples?.length || 0} câu hỏi mẫu
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {currentDb.samples?.map((s, idx) => (
                    <div 
                      key={idx} 
                      style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between', 
                        alignItems: 'center', 
                        padding: '8px 10px', 
                        background: '#f8fafc', 
                        border: '1px solid #e2e8f0', 
                        borderRadius: '6px',
                        flexWrap: 'wrap',
                        gap: '8px'
                      }}
                    >
                      <div style={{ flex: 1, minWidth: '260px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                          <span className={`badge ${
                            s.difficulty === 'simple' 
                              ? 'badge-success' 
                              : s.difficulty === 'moderate' 
                              ? 'badge-warning' 
                              : 'badge-danger'
                          }`} style={{ fontSize: '0.66rem', textTransform: 'capitalize', padding: '1px 5px' }}>
                            {s.difficulty}
                          </span>
                          <span style={{ fontSize: '0.82rem', fontWeight: '600', color: '#0f172a' }}>
                            {s.question}
                          </span>
                        </div>
                        {s.evidence && (
                          <div style={{ fontSize: '0.72rem', color: '#92400e', fontStyle: 'italic', marginTop: '1px' }}>
                            💡 {s.evidence}
                          </div>
                        )}
                      </div>

                      {onTryQuestion && (
                        <button
                          onClick={() => onTryQuestion({ db_id: currentDb.db_id, ...s })}
                          className="btn btn-secondary"
                          style={{ padding: '3px 8px', fontSize: '0.72rem', color: '#4f46e5', gap: '4px' }}
                        >
                          <Play size={11} /> Thử ngay
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

          </div>
        )}

      </div>

    </div>
  );
}
