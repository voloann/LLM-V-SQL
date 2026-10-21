import React, { useState, useEffect } from 'react';
import { 
  PlaySquare, 
  Database, 
  Sparkles, 
  CheckCircle2, 
  AlertCircle, 
  Clock, 
  Zap, 
  Layers, 
  ArrowRight, 
  ArrowDown,
  Code2, 
  Table as TableIcon,
  Wifi,
  WifiOff,
  Radio,
  RotateCcw,
  Copy,
  Check,
  ExternalLink,
  HelpCircle,
  X,
  Server,
  Shuffle,
  Terminal,
  AlertTriangle,
  RefreshCw
} from 'lucide-react';
import { formatSql } from '../utils/sqlFormatter';

export default function Playground({ databases, prefill, health, onRefreshHealth, onNavigateTab }) {
  const [selectedDb, setSelectedDb] = useState('superhero');
  const [question, setQuestion] = useState('Please list all the superpowers of 3-D Man.');
  const [evidence, setEvidence] = useState("3-D Man refers to superhero_name = '3-D Man'; superpowers refers to power_name");
  const [method, setMethod] = useState('vsql'); // 'vsql' or 'direct'
  const [loading, setLoading] = useState(false);
  const [checkingLm, setCheckingLm] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copiedSection, setCopiedSection] = useState(null);

  // Modal Connection State
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [isRetryingConnect, setIsRetryingConnect] = useState(false);
  const [connectSuccessMsg, setConnectSuccessMsg] = useState(null);
  const [connectErrorMsg, setConnectErrorMsg] = useState(null);

  // Nhận dữ liệu prefill từ Explorer nếu có
  useEffect(() => {
    if (prefill) {
      if (prefill.db_id) setSelectedDb(prefill.db_id);
      if (prefill.question) setQuestion(prefill.question);
      if (prefill.evidence !== undefined) setEvidence(prefill.evidence || '');
      setResult(null);
      setError(null);
    }
  }, [prefill]);

  // Khi đổi DB, nạp câu hỏi mẫu đầu tiên của DB đó nếu có
  const handleDbChange = (dbId) => {
    setSelectedDb(dbId);
    const dbObj = databases?.find(d => d.db_id === dbId);
    if (dbObj && dbObj.samples && dbObj.samples.length > 0) {
      setQuestion(dbObj.samples[0].question);
      setEvidence(dbObj.samples[0].evidence || '');
    }
    setResult(null);
  };

  const handleSampleClick = (sample) => {
    setQuestion(sample.question);
    setEvidence(sample.evidence || '');
    setResult(null);
  };

  const handleRandomSample = () => {
    const dbObj = databases?.find(d => d.db_id === selectedDb);
    if (dbObj && dbObj.samples && dbObj.samples.length > 0) {
      const remaining = dbObj.samples.filter(s => s.question !== question);
      const pool = remaining.length > 0 ? remaining : dbObj.samples;
      const random = pool[Math.floor(Math.random() * pool.length)];
      handleSampleClick(random);
    }
  };

  const handleClearInputs = () => {
    setQuestion('');
    setEvidence('');
    setResult(null);
    setError(null);
  };

  const copyToClipboard = (text, sectionKey) => {
    if (!text) return;
    navigator.clipboard.writeText(formatSql(text));
    setCopiedSection(sectionKey);
    setTimeout(() => {
      setCopiedSection(null);
    }, 2000);
  };

  const currentDbObj = databases?.find(d => d.db_id === selectedDb);
  const isLmOnline = health?.lm_studio?.connected === true;

  // Kiểm tra kết nối lại trong Modal
  const handleRetryConnection = async () => {
    setIsRetryingConnect(true);
    setConnectSuccessMsg(null);
    setConnectErrorMsg(null);

    try {
      let freshHealth = null;
      if (onRefreshHealth) {
        freshHealth = await onRefreshHealth();
      } else {
        const res = await fetch('/api/health');
        freshHealth = await res.json();
      }

      if (freshHealth?.lm_studio?.connected === true) {
        setConnectSuccessMsg(`Kết nối thành công! Đang nhận diện model: ${freshHealth.lm_studio.model || 'Qwen2.5-Coder'}`);
        setTimeout(() => {
          setShowConnectModal(false);
          setConnectSuccessMsg(null);
        }, 1200);
      } else {
        setConnectErrorMsg('Server tại http://localhost:1234/v1 vẫn chưa phản hồi. Vui lòng mở LM Studio và bấm "Start Server".');
      }
    } catch (err) {
      setConnectErrorMsg('Lỗi khi gọi API kiểm tra: ' + (err.message || 'Không thể kết nối API'));
    } finally {
      setIsRetryingConnect(false);
    }
  };

  // Kích hoạt suy luận
  const handleRun = async () => {
    if (!question.trim()) return;

    // BƯỚC 1: Kiểm tra trạng thái LM Studio thời gian thực
    setCheckingLm(true);
    let isConnected = false;
    try {
      let currentStatus = null;
      if (onRefreshHealth) {
        currentStatus = await onRefreshHealth();
      } else {
        const res = await fetch('/api/health');
        currentStatus = await res.json();
      }
      isConnected = currentStatus?.lm_studio?.connected === true;
    } catch (e) {
      isConnected = false;
    } finally {
      setCheckingLm(false);
    }

    // Nếu chưa có LM hoạt động, hiển thị Modal thông báo yêu cầu kết nối
    if (!isConnected) {
      setShowConnectModal(true);
      return;
    }

    // BƯỚC 2: LM Studio đã sẵn sàng -> Gọi API suy luận Text-to-SQL
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const resp = await fetch('/api/infer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          db_id: selectedDb,
          question: question.trim(),
          evidence: evidence.trim(),
          method: method
        })
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || 'Lỗi khi gọi API infer');
      }

      const data = await resp.json();
      setResult(data);
    } catch (err) {
      setError(err.message || 'Đã xảy ra lỗi trong quá trình suy luận.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      
      {/* 1. Main Configuration Card */}
      <div className="card" style={{ padding: '1.25rem 1.5rem' }}>
        
        {/* Card Header with Live LM Status */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', marginBottom: '1.25rem', paddingBottom: '0.85rem', borderBottom: '1px solid #f1f5f9' }}>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: '700', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <PlaySquare size={18} color="#4f46e5" />
              <span>Thiết lập Thực nghiệm & Suy luận SQL Trực tiếp</span>
            </h3>
            <p style={{ margin: '3px 0 0 0', fontSize: '0.78rem', color: '#64748b' }}>
              Thử nghiệm mô hình Qwen2.5-Coder trên 11 CSDL BIRD Benchmark qua cơ chế V-SQL 2-Stage hoặc Direct Baseline.
            </p>
          </div>

          {/* LM Studio Status Pill */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: '20px',
              fontSize: '0.75rem',
              fontWeight: '600',
              background: isLmOnline ? '#ecfdf5' : '#fff1f2',
              color: isLmOnline ? '#065f46' : '#991b1b',
              border: isLmOnline ? '1px solid #a7f3d0' : '1px solid #fecaca'
            }}>
              <span style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: isLmOnline ? '#10b981' : '#ef4444',
                boxShadow: isLmOnline ? '0 0 8px rgba(16, 185, 129, 0.6)' : 'none'
              }} />
              <span>{isLmOnline ? `LM Studio Online (:1234)` : 'LM Studio Offline (:1234)'}</span>
            </div>

            {!isLmOnline && (
              <button
                onClick={() => setShowConnectModal(true)}
                className="btn btn-secondary"
                style={{ padding: '3px 10px', fontSize: '0.75rem', height: '28px', color: '#4f46e5', borderColor: '#c7d2fe' }}
              >
                <Server size={12} /> Hướng dẫn kết nối
              </button>
            )}
          </div>
        </div>

        {/* 2-Column Selectors Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
          
          {/* CSDL Selector */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '700', color: '#334155', marginBottom: '6px' }}>
              1. Chọn Cơ sở dữ liệu (11 CSDL BIRD Benchmark)
            </label>
            <div style={{ position: 'relative' }}>
              <select
                value={selectedDb}
                onChange={(e) => handleDbChange(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.65rem 0.85rem',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  background: '#ffffff',
                  fontSize: '0.875rem',
                  fontWeight: '600',
                  color: '#0f172a',
                  outline: 'none',
                  cursor: 'pointer'
                }}
              >
                {databases?.map((db) => (
                  <option key={db.db_id} value={db.db_id}>
                    {db.db_id} ({db.view_count} views ảo)
                  </option>
                ))}
              </select>
            </div>

            {/* Current DB Views Info Strip */}
            {currentDbObj && (
              <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: '600' }}>
                  Views ảo sẵn có:
                </span>
                {currentDbObj.views && currentDbObj.views.length > 0 ? (
                  currentDbObj.views.map((v, i) => (
                    <span 
                      key={i} 
                      style={{ 
                        fontSize: '0.7rem', 
                        background: '#e0e7ff', 
                        color: '#3730a3', 
                        padding: '1px 6px', 
                        borderRadius: '4px', 
                        fontFamily: 'var(--font-mono)' 
                      }}
                    >
                      {v}
                    </span>
                  ))
                ) : (
                  <span style={{ fontSize: '0.72rem', color: '#94a3b8', fontStyle: 'italic' }}>Không có View</span>
                )}
              </div>
            )}
          </div>

          {/* Method Selector Cards */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '700', color: '#334155', marginBottom: '6px' }}>
              2. Chọn Phương pháp Thực thi
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              
              {/* Option 1: V-SQL */}
              <div
                onClick={() => setMethod('vsql')}
                style={{
                  border: method === 'vsql' ? '2px solid #4f46e5' : '1px solid #cbd5e1',
                  background: method === 'vsql' ? '#eef2ff' : '#ffffff',
                  borderRadius: '10px',
                  padding: '10px 12px',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  position: 'relative'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ 
                    fontSize: '0.85rem', 
                    fontWeight: '700', 
                    color: method === 'vsql' ? '#4338ca' : '#1e293b' 
                  }}>
                    V-SQL (2-Stage)
                  </span>
                  <span style={{ 
                    fontSize: '0.65rem', 
                    background: '#dbeafe', 
                    color: '#1e40af', 
                    padding: '1px 5px', 
                    borderRadius: '4px',
                    fontWeight: '700'
                  }}>
                    ⭐ Đề xuất
                  </span>
                </div>
                <div style={{ fontSize: '0.72rem', color: '#64748b', lineHeight: '1.3' }}>
                  Dummy SQL trên Views ➔ Unroll về bảng thật (Giảm JOINs)
                </div>
              </div>

              {/* Option 2: Direct Baseline */}
              <div
                onClick={() => setMethod('direct')}
                style={{
                  border: method === 'direct' ? '2px solid #4f46e5' : '1px solid #cbd5e1',
                  background: method === 'direct' ? '#eef2ff' : '#ffffff',
                  borderRadius: '10px',
                  padding: '10px 12px',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ 
                    fontSize: '0.85rem', 
                    fontWeight: '700', 
                    color: method === 'direct' ? '#4338ca' : '#1e293b' 
                  }}>
                    Direct Baseline
                  </span>
                  <span style={{ 
                    fontSize: '0.65rem', 
                    background: '#f1f5f9', 
                    color: '#475569', 
                    padding: '1px 5px', 
                    borderRadius: '4px',
                    fontWeight: '600'
                  }}>
                    Chuẩn 1 chặng
                  </span>
                </div>
                <div style={{ fontSize: '0.72rem', color: '#64748b', lineHeight: '1.3' }}>
                  Sinh trực tiếp trên toàn bộ bảng gốc (Không dùng View)
                </div>
              </div>

            </div>
          </div>

        </div>

        {/* 3. Sample Queries Section */}
        {currentDbObj && currentDbObj.samples && currentDbObj.samples.length > 0 && (
          <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid #f1f5f9' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.78rem', fontWeight: '700', color: '#475569' }}>
                💡 Câu hỏi mẫu có sẵn trong CSDL <span style={{ color: '#4f46e5' }}>{selectedDb}</span>:
              </span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={handleRandomSample}
                  className="btn btn-secondary"
                  style={{ padding: '2px 8px', fontSize: '0.72rem', height: '24px' }}
                  title="Chọn ngẫu nhiên câu hỏi mẫu khác"
                >
                  <Shuffle size={12} /> Chọn ngẫu nhiên
                </button>
                {onNavigateTab && (
                  <button
                    type="button"
                    onClick={() => onNavigateTab('explorer')}
                    className="btn btn-secondary"
                    style={{ padding: '2px 8px', fontSize: '0.72rem', height: '24px', color: '#4f46e5' }}
                  >
                    Xem 500 câu benchmark <ExternalLink size={11} />
                  </button>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {currentDbObj.samples.map((s, idx) => {
                const isSelected = question === s.question;
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSampleClick(s)}
                    style={{
                      background: isSelected ? '#eef2ff' : '#f8fafc',
                      border: isSelected ? '1px solid #6366f1' : '1px solid #e2e8f0',
                      borderRadius: '6px',
                      padding: '5px 10px',
                      fontSize: '0.75rem',
                      color: isSelected ? '#3730a3' : '#334155',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontWeight: isSelected ? '600' : '400',
                      transition: 'all 0.15s ease',
                      maxWidth: '100%',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}
                    title={s.question}
                  >
                    <span 
                      className={`badge ${
                        s.difficulty === 'simple' 
                          ? 'badge-success' 
                          : s.difficulty === 'moderate' 
                          ? 'badge-warning' 
                          : 'badge-danger'
                      }`} 
                      style={{ marginRight: '6px', fontSize: '0.65rem', padding: '1px 5px', textTransform: 'capitalize' }}
                    >
                      {s.difficulty}
                    </span>
                    <span>{s.question.length > 70 ? s.question.substring(0, 70) + '...' : s.question}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* 4. Natural Language Question & Evidence Inputs */}
        <div style={{ marginTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '5px' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: '700', color: '#334155' }}>
                Câu hỏi tự nhiên (Question)
              </label>
              <button
                type="button"
                onClick={() => setQuestion('')}
                style={{ background: 'none', border: 'none', color: '#94a3b8', fontSize: '0.72rem', cursor: 'pointer' }}
              >
                Xóa câu hỏi
              </button>
            </div>
            <textarea
              rows={2}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Nhập câu hỏi bằng tiếng Anh hoặc tiếng Việt muốn chuyển sang SQL..."
              style={{
                width: '100%',
                padding: '0.7rem 0.85rem',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                fontSize: '0.875rem',
                color: '#0f172a',
                outline: 'none',
                fontFamily: 'inherit',
                lineHeight: '1.45',
                resize: 'vertical'
              }}
            />
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '5px' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: '700', color: '#334155' }}>
                Kiến thức bổ trợ ngoài (External Knowledge / Evidence)
              </label>
              <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Gợi ý ánh xạ giá trị BIRD Benchmark</span>
            </div>
            <input
              type="text"
              value={evidence}
              onChange={(e) => setEvidence(e.target.value)}
              placeholder="VD: 3-D Man refers to superhero_name = '3-D Man'; superpowers refers to power_name..."
              style={{
                width: '100%',
                padding: '0.65rem 0.85rem',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                fontSize: '0.85rem',
                color: '#0f172a',
                outline: 'none',
                fontFamily: 'inherit'
              }}
            />
          </div>

          {/* Action Bar */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            flexWrap: 'wrap', 
            gap: '10px',
            marginTop: '0.5rem',
            paddingTop: '0.85rem',
            borderTop: '1px solid #f1f5f9'
          }}>
            <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
              💡 Hệ thống sẽ tự động thực thi câu lệnh SQL sinh ra trên file SQLite cục bộ (<code style={{ color: '#4f46e5' }}>{selectedDb}.sqlite</code>).
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                type="button"
                onClick={handleClearInputs}
                className="btn btn-secondary"
                style={{ padding: '0.6rem 1rem', fontSize: '0.82rem' }}
              >
                <RotateCcw size={14} /> Xóa nội dung
              </button>

              <button
                type="button"
                onClick={handleRun}
                disabled={loading || checkingLm || !question.trim()}
                className="btn btn-primary"
                style={{ 
                  padding: '0.65rem 1.5rem', 
                  fontSize: '0.875rem',
                  fontWeight: '700',
                  background: 'linear-gradient(135deg, #4f46e5 0%, #6366f1 100%)',
                  boxShadow: '0 4px 12px rgba(79, 70, 229, 0.25)'
                }}
              >
                {checkingLm ? (
                  <>
                    <RefreshCw size={16} className="animate-spin" />
                    <span>Đang kiểm tra LM...</span>
                  </>
                ) : loading ? (
                  <>
                    <Sparkles size={16} className="animate-spin" />
                    <span>Đang suy luận qua LM Studio...</span>
                  </>
                ) : (
                  <>
                    <Zap size={16} />
                    <span>Chạy Suy luận Text-to-SQL</span>
                  </>
                )}
              </button>
            </div>
          </div>

        </div>

      </div>

      {/* 5. Error state banner */}
      {error && (
        <div style={{ 
          background: '#fef2f2', 
          border: '1px solid #fecaca', 
          padding: '0.85rem 1rem', 
          borderRadius: '10px', 
          color: '#991b1b', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          gap: '10px',
          fontSize: '0.85rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertCircle size={18} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
          <button
            onClick={() => setShowConnectModal(true)}
            className="btn btn-secondary"
            style={{ padding: '2px 8px', fontSize: '0.75rem', height: '26px', borderColor: '#fecaca', color: '#991b1b' }}
          >
            Kiểm tra kết nối LM Studio
          </button>
        </div>
      )}

      {/* 6. Result Display Section */}
      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          
          {/* Header Result Badge Ribbon */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 0.5rem', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span className="badge badge-primary" style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
                Phương pháp: {result.method?.toUpperCase()}
              </span>
              <span className="badge badge-neutral" style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
                <Clock size={14} style={{ marginRight: '4px' }} />
                Tổng độ trễ: {result.total_latency_s || result.latency_s}s
              </span>
              {result.tokens && (
                <span className="badge badge-neutral" style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
                  {result.tokens} tokens
                </span>
              )}
            </div>

            {result.execution?.error ? (
              <span className="badge badge-danger" style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
                <AlertCircle size={14} style={{ marginRight: '4px' }} /> Thực thi SQLite có lỗi
              </span>
            ) : (
              <span className="badge badge-success" style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
                <CheckCircle2 size={14} style={{ marginRight: '4px' }} /> Thực thi SQLite thành công ({result.execution?.rows?.length ?? 0} dòng)
              </span>
            )}
          </div>

          {/* V-SQL 2-Stage Stepper View */}
          {result.method === 'vsql' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.25rem' }}>
              
              {/* Stage 1 Box */}
              <div className="card" style={{ borderTop: '4px solid #06b6d4', padding: '1rem 1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ width: '22px', height: '22px', borderRadius: '50%', background: '#06b6d4', color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: '700' }}>1</span>
                    <span style={{ fontWeight: '700', color: '#0f172a', fontSize: '0.9rem' }}>Stage 1 — Dummy SQL (trên Views ảo)</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className="badge badge-success" style={{ fontSize: '0.72rem' }}>
                      JOINs: {result.stage1?.joins}
                    </span>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(result.stage1?.dummy_sql, 'stage1')}
                      className="btn btn-secondary"
                      style={{ padding: '2px 6px', fontSize: '0.7rem', height: '22px' }}
                    >
                      {copiedSection === 'stage1' ? <><Check size={11} /> Đã chép</> : <><Copy size={11} /> Chép</>}
                    </button>
                  </div>
                </div>

                <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '8px' }}>
                  Truy vấn trên bảng ảo (loại bỏ quan hệ FK phức tạp) • {result.stage1?.tokens ?? 0} tok • {result.stage1?.latency_s ?? 0}s
                </div>

                <pre style={{ 
                  background: '#f8fafc', 
                  border: '1px solid #e2e8f0', 
                  borderRadius: '8px', 
                  padding: '12px', 
                  fontSize: '0.8rem', 
                  color: '#0f172a', 
                  whiteSpace: 'pre-wrap', 
                  wordBreak: 'break-word', 
                  lineHeight: '1.45', 
                  fontFamily: 'var(--font-mono)',
                  maxHeight: '180px',
                  overflowY: 'auto'
                }}>
                  {formatSql(result.stage1?.dummy_sql)}
                </pre>
              </div>

              {/* Stage 2 Box */}
              <div className="card" style={{ borderTop: '4px solid #4f46e5', padding: '1rem 1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ width: '22px', height: '22px', borderRadius: '50%', background: '#4f46e5', color: '#fff', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: '700' }}>2</span>
                    <span style={{ fontWeight: '700', color: '#0f172a', fontSize: '0.9rem' }}>Stage 2 — Final SQL (trên Bảng gốc)</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className="badge badge-primary" style={{ fontSize: '0.72rem' }}>
                      JOINs: {result.stage2?.joins}
                    </span>
                    {result.stage2?.view_leak && (
                      <span className="badge badge-warning" style={{ fontSize: '0.72rem' }}>
                        <AlertTriangle size={11} /> View Leak!
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => copyToClipboard(result.stage2?.final_sql, 'stage2')}
                      className="btn btn-secondary"
                      style={{ padding: '2px 6px', fontSize: '0.7rem', height: '22px' }}
                    >
                      {copiedSection === 'stage2' ? <><Check size={11} /> Đã chép</> : <><Copy size={11} /> Chép</>}
                    </button>
                  </div>
                </div>

                <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '8px' }}>
                  Phục hồi về bảng vật lý SQLite • {result.stage2?.tokens ?? 0} tok • {result.stage2?.latency_s ?? 0}s
                </div>

                <pre style={{ 
                  background: '#f8fafc', 
                  border: '1px solid #e2e8f0', 
                  borderRadius: '8px', 
                  padding: '12px', 
                  fontSize: '0.8rem', 
                  color: '#0f172a', 
                  whiteSpace: 'pre-wrap', 
                  wordBreak: 'break-word', 
                  lineHeight: '1.45', 
                  fontFamily: 'var(--font-mono)',
                  maxHeight: '180px',
                  overflowY: 'auto'
                }}>
                  {formatSql(result.stage2?.final_sql)}
                </pre>
              </div>

            </div>
          )}

          {/* Direct Baseline Single View */}
          {result.method === 'direct' && (
            <div className="card" style={{ borderTop: '4px solid #4f46e5', padding: '1rem 1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Code2 size={18} color="#4f46e5" />
                  <span style={{ fontWeight: '700', color: '#0f172a', fontSize: '0.9rem' }}>Direct SQL (sinh trực tiếp trên bảng vật lý)</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span className="badge badge-primary" style={{ fontSize: '0.72rem' }}>
                    JOINs: {result.joins}
                  </span>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(result.final_sql, 'direct')}
                    className="btn btn-secondary"
                    style={{ padding: '2px 6px', fontSize: '0.7rem', height: '22px' }}
                  >
                    {copiedSection === 'direct' ? <><Check size={11} /> Đã chép</> : <><Copy size={11} /> Chép</>}
                  </button>
                </div>
              </div>

              <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '8px' }}>
                {result.tokens} tokens • Latency: {result.latency_s}s
              </div>

              <pre style={{ 
                background: '#f8fafc', 
                border: '1px solid #e2e8f0', 
                borderRadius: '8px', 
                padding: '12px', 
                fontSize: '0.8rem', 
                color: '#0f172a', 
                whiteSpace: 'pre-wrap', 
                wordBreak: 'break-word', 
                lineHeight: '1.45', 
                fontFamily: 'var(--font-mono)',
                maxHeight: '220px',
                overflowY: 'auto'
              }}>
                {formatSql(result.final_sql)}
              </pre>
            </div>
          )}

          {/* SQLite Execution Grid Table */}
          <div className="card" style={{ padding: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
              <h4 style={{ fontSize: '0.9rem', fontWeight: '700', color: '#0f172a', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <TableIcon size={18} color="#10b981" />
                <span>Kết quả Thực thi Dữ liệu Thật trên SQLite (<code style={{ color: '#059669' }}>{selectedDb}.sqlite</code>)</span>
              </h4>
              
              {result.execution?.rows && (
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                  {result.execution.rows.length} dòng được trả về (giới hạn 50 dòng xem trước)
                </span>
              )}
            </div>

            {result.execution?.error ? (
              <div style={{ background: '#fef2f2', border: '1px solid #fecaca', padding: '12px', borderRadius: '8px', color: '#b91c1c', fontSize: '0.85rem' }}>
                <b>Lỗi thực thi SQLite:</b> {result.execution.error}
              </div>
            ) : result.execution?.columns && result.execution?.columns.length > 0 ? (
              <div style={{ overflowX: 'auto', maxHeight: '320px', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
                  <thead style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                    <tr style={{ background: '#f8fafc', borderBottom: '2px solid #cbd5e1' }}>
                      <th style={{ padding: '8px 12px', fontWeight: '700', color: '#64748b', width: '40px' }}>#</th>
                      {result.execution.columns.map((col, idx) => (
                        <th key={idx} style={{ padding: '8px 12px', fontWeight: '700', color: '#334155' }}>
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.execution.rows?.length === 0 ? (
                      <tr>
                        <td colSpan={result.execution.columns.length + 1} style={{ padding: '16px', textAlign: 'center', color: '#64748b' }}>
                          (Kết quả rỗng — Không có bản ghi nào khớp với điều kiện)
                        </td>
                      </tr>
                    ) : (
                      result.execution.rows.map((row, rIdx) => (
                        <tr 
                          key={rIdx} 
                          style={{ 
                            borderBottom: '1px solid #f1f5f9',
                            background: rIdx % 2 === 0 ? '#ffffff' : '#fcfdfe'
                          }}
                        >
                          <td style={{ padding: '8px 12px', color: '#94a3b8', fontSize: '0.75rem' }}>{rIdx + 1}</td>
                          {row.map((cell, cIdx) => (
                            <td key={cIdx} style={{ padding: '8px 12px', color: '#0f172a' }}>
                              {cell === null ? (
                                <span style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '0.75rem' }}>NULL</span>
                              ) : (
                                String(cell)
                              )}
                            </td>
                          ))}
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ color: '#64748b', fontSize: '0.85rem', padding: '8px 0' }}>
                Câu truy vấn đã thực thi thành công nhưng không trả về tập bản ghi dữ liệu.
              </div>
            )}
          </div>

        </div>
      )}

      {/* 7. MODAL THÔNG BÁO YÊU CẦU KẾT NỐI LM STUDIO */}
      {showConnectModal && (
        <div 
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(6px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1.25rem'
          }}
          onClick={() => setShowConnectModal(false)}
        >
          <div 
            style={{
              background: '#ffffff',
              borderRadius: '16px',
              maxWidth: '540px',
              width: '100%',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              border: '1px solid #cbd5e1',
              padding: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1.2rem'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ 
                  width: '40px', 
                  height: '40px', 
                  borderRadius: '10px', 
                  background: '#fef2f2', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  border: '1px solid #fecaca'
                }}>
                  <Server size={22} color="#dc2626" />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: '700', color: '#0f172a', margin: 0 }}>
                    Chưa kết nối Local LLM (LM Studio)
                  </h3>
                  <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '2px' }}>
                    Yêu cầu máy chủ suy luận cục bộ để thực thi trực tiếp
                  </div>
                </div>
              </div>

              <button 
                onClick={() => setShowConnectModal(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b', padding: '4px' }}
                title="Đóng modal"
              >
                <X size={20} />
              </button>
            </div>

            {/* Offline Status Badge */}
            <div style={{ 
              background: '#fef2f2', 
              border: '1px solid #fecaca', 
              borderRadius: '8px', 
              padding: '10px 12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.8rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#991b1b' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444' }} />
                <span><b>Cổng dịch vụ:</b> <code>http://localhost:1234/v1</code></span>
              </div>
              <span style={{ color: '#dc2626', fontWeight: '700', fontSize: '0.75rem', background: '#fee2e2', padding: '2px 8px', borderRadius: '4px' }}>
                Offline
              </span>
            </div>

            {/* Instructions */}
            <div style={{ fontSize: '0.85rem', color: '#334155', lineHeight: '1.5' }}>
              <p style={{ margin: '0 0 10px 0' }}>
                Để sinh câu lệnh SQL thời gian thực cho bất kỳ câu hỏi mới nào, hệ thống cần kết nối với <b>LM Studio</b> đang chạy trên máy tính của bạn:
              </p>

              <ol style={{ margin: 0, paddingLeft: '1.25rem', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.82rem' }}>
                <li>
                  Mở ứng dụng <b>LM Studio</b> trên máy tính.
                </li>
                <li>
                  Tải hoặc nạp mô hình: <code style={{ background: '#f1f5f9', padding: '1px 5px', borderRadius: '4px', color: '#4f46e5' }}>qwen2.5-coder-7b-instruct</code> (hoặc model code tương thích OpenAI).
                </li>
                <li>
                  Chuyển sang tab <b>Developer / Local Server</b> (biểu tượng <code>&lt;-&gt;</code>) và nhấn <b>Start Server</b> tại cổng <b>1234</b>.
                </li>
                <li>
                  Bấm nút <b>"Kiểm tra kết nối lại"</b> bên dưới để xác nhận.
                </li>
              </ol>
            </div>

            {/* Success message banner */}
            {connectSuccessMsg && (
              <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', padding: '8px 12px', borderRadius: '8px', color: '#065f46', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle2 size={16} />
                <span>{connectSuccessMsg}</span>
              </div>
            )}

            {/* Error message banner */}
            {connectErrorMsg && (
              <div style={{ background: '#fffbeb', border: '1px solid #fde68a', padding: '8px 12px', borderRadius: '8px', color: '#92400e', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                <span>{connectErrorMsg}</span>
              </div>
            )}

            {/* Alternative notice */}
            <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '10px 12px', fontSize: '0.78rem', color: '#64748b' }}>
              💡 <b>Gợi ý:</b> Nếu bạn chưa muốn bật LM Studio ngay bây giờ, bạn có thể xem đối chiếu toàn bộ 500 câu hỏi benchmark đã được thực nghiệm sẵn tại trang <b>Tra cứu 500 câu hỏi</b>.
            </div>

            {/* Footer Buttons */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', paddingTop: '0.5rem', borderTop: '1px solid #f1f5f9' }}>
              {onNavigateTab ? (
                <button
                  type="button"
                  onClick={() => {
                    setShowConnectModal(false);
                    onNavigateTab('explorer');
                  }}
                  className="btn btn-secondary"
                  style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                >
                  <ExternalLink size={13} /> Tra cứu 500 câu
                </button>
              ) : <div />}

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => setShowConnectModal(false)}
                  className="btn btn-secondary"
                  style={{ padding: '6px 14px', fontSize: '0.8rem' }}
                >
                  Đóng
                </button>

                <button
                  type="button"
                  onClick={handleRetryConnection}
                  disabled={isRetryingConnect}
                  className="btn btn-primary"
                  style={{ padding: '6px 16px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  {isRetryingConnect ? (
                    <>
                      <RefreshCw size={13} className="animate-spin" />
                      <span>Đang kiểm tra...</span>
                    </>
                  ) : (
                    <>
                      <RefreshCw size={13} />
                      <span>Kiểm tra kết nối lại</span>
                    </>
                  )}
                </button>
              </div>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
