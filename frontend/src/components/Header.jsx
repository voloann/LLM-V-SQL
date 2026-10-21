import React from 'react';
import { 
  Play, 
  Database, 
  Sparkles, 
  CheckCircle2, 
  ChevronRight,
  TrendingUp,
  RefreshCw,
  GitBranch
} from 'lucide-react';

export default function Header({ activeTab, setActiveTab, health }) {
  const meta = {
    dashboard: {
      category: 'NGHIÊN CỨU & ĐÁNH GIÁ',
      title: 'Báo cáo & Phân tích Thực nghiệm',
      badge: '500/500 câu hoàn tất'
    },
    playground: {
      category: 'CÔNG CỤ TƯƠNG TÁC',
      title: 'Phòng Thử nghiệm Trực tiếp',
      badge: 'Hỗ trợ 11 CSDL'
    },
    explorer: {
      category: 'TRA CỨU DỮ LIỆU',
      title: 'Trình Tra cứu 500 Câu hỏi BIRD',
      badge: 'BIRD Mini-dev Benchmark'
    },
    architecture: {
      category: 'LÝ THUYẾT & PHƯƠNG PHÁP',
      title: 'Kiến trúc Framework V-SQL',
      badge: 'You et al., 2024'
    },
    views_catalog: {
      category: 'THIẾT KẾ PHA 1 (TABLE MAPPING)',
      title: 'Kho Views Ảo & Lược đồ CSDL',
      badge: '11 CSDL · 27 Views Khái niệm'
    }
  };

  const current = meta[activeTab] || meta.dashboard;

  return (
    <header 
      style={{
        minHeight: '76px',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid #e2e8f0',
        position: 'sticky',
        top: 0,
        zIndex: 40,
        boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
        display: 'flex',
        alignItems: 'center',
        width: '100%'
      }}
    >
      <div 
        style={{
          maxWidth: '1400px',
          width: '100%',
          margin: '0 auto',
          padding: '0.85rem 2rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1.5rem'
        }}
      >
        {/* Left: Breadcrumbs + Title */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: '#64748b', fontWeight: '600', letterSpacing: '0.04em' }}>
            <span style={{ color: '#94a3b8' }}>V-SQL STUDIO</span>
            <ChevronRight size={12} color="#cbd5e1" />
            <span style={{ color: '#4f46e5', fontWeight: '700' }}>{current.category}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <h1 style={{ fontSize: '1.25rem', fontWeight: '800', color: '#0f172a', letterSpacing: '-0.025em', lineHeight: 1.25 }}>
              {current.title}
            </h1>
            <span 
              className="badge badge-primary" 
              style={{ 
                fontSize: '0.72rem', 
                padding: '3px 9px',
                borderRadius: '9999px',
                fontWeight: '600'
              }}
            >
              {current.badge}
            </span>
          </div>
        </div>

        {/* Right: Quick Performance KPIs & Action */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
          {/* Quick Result Summary Pill */}
          <div 
            style={{
              display: 'flex',
              alignItems: 'center',
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '9999px',
              padding: '5px 14px',
              fontSize: '0.78rem',
              gap: '12px',
              boxShadow: '0 1px 2px rgba(0,0,0,0.02)'
            }}
            title="Kết quả đo thực tế trên 500 câu hỏi BIRD mini-dev"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#4f46e5' }} />
              <span style={{ color: '#64748b', fontWeight: '500' }}>Direct:</span>
              <b style={{ color: '#0f172a', fontWeight: '700' }}>47.4% EX</b>
            </div>
            <div style={{ width: '1px', height: '14px', background: '#cbd5e1' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#06b6d4' }} />
              <span style={{ color: '#64748b', fontWeight: '500' }}>V-SQL:</span>
              <b style={{ color: '#0f172a', fontWeight: '700' }}>33.6% EX</b>
            </div>
          </div>

          {/* Database Chip */}
          <div 
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: '#ffffff',
              border: '1px solid #e2e8f0',
              padding: '5px 12px',
              borderRadius: '9999px',
              fontSize: '0.78rem',
              color: '#334155',
              fontWeight: '600',
              boxShadow: '0 1px 2px rgba(0,0,0,0.02)'
            }}
          >
            <Database size={13} color="#4f46e5" />
            <span>11 CSDL SQLite</span>
          </div>

          {/* CTA Button */}
          {activeTab !== 'playground' ? (
            <button
              onClick={() => setActiveTab('playground')}
              className="btn btn-primary"
              style={{ 
                padding: '0.52rem 1.15rem', 
                fontSize: '0.82rem',
                fontWeight: '600',
                borderRadius: '9999px',
                background: 'linear-gradient(135deg, #4f46e5 0%, #4338ca 100%)',
                boxShadow: '0 2px 6px rgba(79, 70, 229, 0.35)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <Play size={14} fill="#ffffff" />
              <span>Thử câu mới</span>
            </button>
          ) : (
            <div 
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                backgroundColor: '#ecfdf5',
                border: '1px solid #a7f3d0',
                padding: '6px 14px',
                borderRadius: '9999px',
                fontSize: '0.78rem',
                color: '#065f46',
                fontWeight: '700'
              }}
            >
              <CheckCircle2 size={14} color="#10b981" />
              <span>Studio Live Mode</span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

