import React from 'react';
import { 
  BarChart3, 
  Play, 
  Search, 
  Layers, 
  PanelLeftClose,
  PanelLeftOpen,
  Database,
  Cpu,
  Sparkles,
  CheckCircle2,
  ExternalLink,
  Activity
} from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, collapsed, setCollapsed, health }) {
  const sections = [
    {
      title: 'TỔNG QUAN & KẾT QUẢ',
      items: [
        { id: 'dashboard', label: 'Báo cáo Thực nghiệm', icon: BarChart3, badge: '500 câu' },
        { id: 'explorer', label: 'Tra cứu 500 câu hỏi', icon: Search, badge: 'BIRD' },
      ]
    },
    {
      title: 'TƯƠNG TÁC & HỌC THUẬT',
      items: [
        { id: 'playground', label: 'Phòng Thử nghiệm', icon: Play, badge: 'Live' },
        { id: 'architecture', label: 'Kiến trúc Framework', icon: Layers, badge: 'V-SQL' },
        { id: 'views_catalog', label: 'Kho Views Ảo & Lược đồ', icon: Database, badge: '11 CSDL' },
      ]
    }
  ];

  return (
    <aside 
      style={{
        width: collapsed ? '72px' : '316px',
        minWidth: collapsed ? '72px' : '316px',
        backgroundColor: '#ffffff',
        borderRight: '1px solid #e2e8f0',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        transition: 'width 0.22s cubic-bezier(0.4, 0, 0.2, 1), min-width 0.22s cubic-bezier(0.4, 0, 0.2, 1)',
        position: 'relative',
        zIndex: 50,
        boxShadow: '1px 0 4px rgba(0,0,0,0.03)'
      }}
    >
      {/* Brand Header */}
      <div 
        style={{
          height: '70px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'space-between',
          padding: collapsed ? '0' : '0 1.25rem',
          borderBottom: '1px solid #f1f5f9'
        }}
      >
        {!collapsed ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div 
              style={{
                width: '38px',
                height: '38px',
                borderRadius: '11px',
                background: 'linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ffffff',
                boxShadow: '0 2px 6px rgba(79, 70, 229, 0.35)',
                flexShrink: 0
              }}
            >
              <Sparkles size={20} />
            </div>
            <div>
              <div style={{ fontWeight: '800', fontSize: '1.05rem', color: '#0f172a', letterSpacing: '-0.025em', lineHeight: 1.2 }}>
                V-SQL Studio
              </div>
              <div style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: '500' }}>
                View-based Text-to-SQL
              </div>
            </div>
          </div>
        ) : (
          <div 
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '11px',
              background: 'linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              boxShadow: '0 2px 6px rgba(79, 70, 229, 0.35)'
            }}
            title="V-SQL Studio"
          >
            <Sparkles size={20} />
          </div>
        )}

        {!collapsed && (
          <button
            onClick={() => setCollapsed(true)}
            style={{
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              padding: '6px',
              cursor: 'pointer',
              color: '#64748b',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.15s ease'
            }}
            title="Thu gọn Sidebar"
          >
            <PanelLeftClose size={17} />
          </button>
        )}
      </div>

      {/* Navigation Sections */}
      <nav style={{ flex: 1, padding: collapsed ? '1.25rem 0.5rem' : '1.25rem 0.75rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', overflowY: 'auto' }}>
        {sections.map((sec, sIdx) => (
          <div key={sIdx} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {!collapsed && (
              <div 
                style={{
                  fontSize: '0.67rem',
                  fontWeight: '700',
                  color: '#94a3b8',
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                  padding: '0 8px',
                  marginBottom: '4px'
                }}
              >
                {sec.title}
              </div>
            )}

            {sec.items.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: collapsed ? '10px 0' : '9px 10px',
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    borderRadius: '10px',
                    border: isActive ? '1px solid #c7d2fe' : '1px solid transparent',
                    background: isActive ? '#eef2ff' : 'transparent',
                    color: isActive ? '#4f46e5' : '#475569',
                    fontWeight: isActive ? '600' : '500',
                    fontSize: '0.84rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    position: 'relative'
                  }}
                  title={item.label}
                >
                  <Icon size={18} color={isActive ? '#4f46e5' : '#64748b'} style={{ flexShrink: 0 }} />
                  {!collapsed && (
                    <span 
                      style={{ 
                        flex: 1, 
                        textAlign: 'left', 
                        whiteSpace: 'nowrap', 
                        overflow: 'hidden', 
                        textOverflow: 'ellipsis',
                        letterSpacing: '-0.01em'
                      }}
                    >
                      {item.label}
                    </span>
                  )}
                  {!collapsed && item.badge && (
                    <span 
                      style={{
                        flexShrink: 0,
                        fontSize: '0.67rem',
                        padding: '2px 7px',
                        borderRadius: '9999px',
                        backgroundColor: isActive ? '#c7d2fe' : '#f1f5f9',
                        color: isActive ? '#3730a3' : '#64748b',
                        fontWeight: '600',
                        letterSpacing: '-0.01em'
                      }}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Expand Button for Collapsed Mode */}
      {collapsed && (
        <div style={{ padding: '0.75rem', display: 'flex', justifyContent: 'center', borderTop: '1px solid #f1f5f9' }}>
          <button
            onClick={() => setCollapsed(false)}
            style={{
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              padding: '7px',
              cursor: 'pointer',
              color: '#475569',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.15s ease'
            }}
            title="Mở rộng Sidebar"
          >
            <PanelLeftOpen size={18} />
          </button>
        </div>
      )}

      {/* Enhanced Bottom System Widget */}
      <div 
        style={{
          padding: collapsed ? '0.75rem 0.5rem' : '0.85rem 1rem',
          borderTop: '1px solid #f1f5f9',
          backgroundColor: '#fafbfc'
        }}
      >
        {!collapsed ? (
          <div 
            style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '12px',
              padding: '11px 12px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span 
                  style={{
                    position: 'relative',
                    display: 'flex',
                    height: '8px',
                    width: '8px'
                  }}
                >
                  <span 
                    style={{
                      position: 'absolute',
                      display: 'inline-flex',
                      height: '100%',
                      width: '100%',
                      borderRadius: '50%',
                      backgroundColor: health?.lm_studio?.connected ? '#10b981' : '#f59e0b',
                      opacity: 0.75,
                      animation: 'ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite'
                    }}
                  />
                  <span 
                    style={{
                      position: 'relative',
                      display: 'inline-flex',
                      borderRadius: '50%',
                      height: '8px',
                      width: '8px',
                      backgroundColor: health?.lm_studio?.connected ? '#10b981' : '#f59e0b'
                    }}
                  />
                </span>
                <span style={{ fontSize: '0.75rem', fontWeight: '700', color: '#1e293b' }}>
                  {health?.lm_studio?.connected ? 'LM Studio Active' : 'LM Studio Offline'}
                </span>
              </div>
              <span className="badge badge-neutral" style={{ fontSize: '0.65rem' }}>
                :1234
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', fontSize: '0.72rem', color: '#64748b' }}>
              <div 
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                title={health?.lm_studio?.model || 'qwen2.5-coder-7b-instruct'}
              >
                <Cpu size={13} color="#6366f1" style={{ flexShrink: 0 }} />
                <span style={{ 
                  color: '#334155', 
                  fontWeight: '500',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap'
                }}>
                  {health?.lm_studio?.model || 'qwen2.5-coder-7b-instruct'}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Database size={13} color="#0ea5e9" style={{ flexShrink: 0 }} />
                <span>11 CSDL · 500 câu hỏi</span>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <span 
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: health?.lm_studio?.connected ? '#10b981' : '#f59e0b',
                boxShadow: health?.lm_studio?.connected ? '0 0 8px rgba(16, 185, 129, 0.7)' : 'none'
              }}
              title={health?.lm_studio?.connected ? 'LM Studio: Connected' : 'LM Studio: Offline'}
            />
          </div>
        )}
      </div>
    </aside>
  );
}
