import React, { useState, useEffect, useMemo } from 'react';
import { 
  Search, 
  Filter, 
  Database, 
  Eye, 
  X, 
  CheckCircle2, 
  AlertTriangle,
  Code2,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  RotateCcw,
  Copy,
  Check,
  PlaySquare,
  SlidersHorizontal,
  Layers,
  ArrowUpDown,
  FileText,
  Clock,
  TrendingDown
} from 'lucide-react';
import { formatSql } from '../utils/sqlFormatter';

function getPaginationItems(current, total) {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const pages = [];
  pages.push(1);
  
  const left = Math.max(2, current - 2);
  const right = Math.min(total - 1, current + 2);
  
  if (left > 2) {
    pages.push('...');
  }
  
  for (let i = left; i <= right; i++) {
    pages.push(i);
  }
  
  if (right < total - 1) {
    pages.push('...');
  }
  
  pages.push(total);
  return pages;
}

export default function Explorer({ databases, onTryQuestion }) {
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);

  // Search & Filter States
  const [search, setSearch] = useState('');
  const [selectedDb, setSelectedDb] = useState('all');
  const [selectedDiff, setSelectedDiff] = useState('all');
  const [filterViewLeak, setFilterViewLeak] = useState('all'); // 'all', 'leak', 'no_leak'
  const [filterJoin, setFilterJoin] = useState('all'); // 'all', 'reduced', 'multi_join', 'zero_join'
  const [filterViewUsage, setFilterViewUsage] = useState('all'); // 'all', 'used', 'unused'
  const [sortBy, setSortBy] = useState('qid_asc');

  // Pagination States
  const [pageSize, setPageSize] = useState(20); // Default: 20 items per page as requested
  const [currentPage, setCurrentPage] = useState(1);
  const [jumpPageInput, setJumpPageInput] = useState('');

  // Modal Inspector State
  const [selectedModalItem, setSelectedModalItem] = useState(null);
  const [modalTab, setModalTab] = useState('compare'); // 'compare', 'vsql', 'direct', 'gold'
  const [copiedSection, setCopiedSection] = useState(null);

  // Fetch all 500 questions once so user can filter, search, sort, and paginate instantly with zero latency
  useEffect(() => {
    fetchQuestions();
  }, []);

  const fetchQuestions = async () => {
    setLoading(true);
    try {
      const resp = await fetch('/api/questions?limit=500');
      const data = await resp.json();
      setQuestions(data.questions || []);
    } catch (err) {
      console.error('Failed to fetch questions:', err);
    } finally {
      setLoading(false);
    }
  };

  // Reset to page 1 whenever any filter or page size changes
  useEffect(() => {
    setCurrentPage(1);
  }, [search, selectedDb, selectedDiff, filterViewLeak, filterJoin, filterViewUsage, sortBy, pageSize]);

  // Compute stats across all 500 questions
  const stats = useMemo(() => {
    const total = questions.length;
    let simple = 0, moderate = 0, challenging = 0;
    let viewLeak = 0, joinReduced = 0, usedViewsCount = 0;

    questions.forEach(q => {
      if (q.difficulty === 'simple') simple++;
      else if (q.difficulty === 'moderate') moderate++;
      else if (q.difficulty === 'challenging') challenging++;

      if (q.vsql?.view_leak) viewLeak++;
      if ((q.vsql?.dummy_joins ?? 0) < (q.direct?.joins ?? 0)) joinReduced++;
      if (q.vsql?.used_views && q.vsql.used_views.length > 0) usedViewsCount++;
    });

    return { total, simple, moderate, challenging, viewLeak, joinReduced, usedViewsCount };
  }, [questions]);

  // DB list with counts
  const dbOptions = useMemo(() => {
    const counts = {};
    questions.forEach(q => {
      counts[q.db_id] = (counts[q.db_id] || 0) + 1;
    });

    if (databases && databases.length > 0) {
      return databases.map(db => ({
        db_id: db.db_id,
        count: counts[db.db_id] || 0
      }));
    }

    return Object.keys(counts).map(id => ({
      db_id: id,
      count: counts[id]
    }));
  }, [questions, databases]);

  // Filter and Sort Pipeline
  const filteredQuestions = useMemo(() => {
    return questions.filter(q => {
      // 1. Text Search (QID, question, evidence, db_id, sql)
      if (search.trim()) {
        const term = search.trim().toLowerCase();
        const matchesQid = String(q.question_id).includes(term) || `#${q.question_id}`.includes(term);
        const matchesQuestion = q.question?.toLowerCase().includes(term);
        const matchesEvidence = q.evidence?.toLowerCase().includes(term);
        const matchesDb = q.db_id?.toLowerCase().includes(term);
        const matchesDirectSql = q.direct?.final_sql?.toLowerCase().includes(term);
        const matchesVsql = q.vsql?.final_sql?.toLowerCase().includes(term) || q.vsql?.dummy_sql?.toLowerCase().includes(term);

        if (!matchesQid && !matchesQuestion && !matchesEvidence && !matchesDb && !matchesDirectSql && !matchesVsql) {
          return false;
        }
      }

      // 2. Database filter
      if (selectedDb !== 'all' && q.db_id !== selectedDb) {
        return false;
      }

      // 3. Difficulty filter
      if (selectedDiff !== 'all' && q.difficulty?.toLowerCase() !== selectedDiff.toLowerCase()) {
        return false;
      }

      // 4. View Leak filter
      if (filterViewLeak === 'leak' && !q.vsql?.view_leak) {
        return false;
      }
      if (filterViewLeak === 'no_leak' && q.vsql?.view_leak) {
        return false;
      }

      // 5. JOIN Mechanism filter
      if (filterJoin === 'reduced') {
        const directJoins = q.direct?.joins ?? 0;
        const dummyJoins = q.vsql?.dummy_joins ?? 0;
        if (!(dummyJoins < directJoins)) return false;
      } else if (filterJoin === 'multi_join') {
        if ((q.direct?.joins ?? 0) < 2) return false;
      } else if (filterJoin === 'zero_join') {
        if ((q.direct?.joins ?? 0) !== 0) return false;
      }

      // 6. View Usage filter
      if (filterViewUsage === 'used') {
        if (!q.vsql?.used_views || q.vsql.used_views.length === 0) return false;
      } else if (filterViewUsage === 'unused') {
        if (q.vsql?.used_views && q.vsql.used_views.length > 0) return false;
      }

      return true;
    }).sort((a, b) => {
      switch (sortBy) {
        case 'qid_asc':
          return Number(a.question_id) - Number(b.question_id);
        case 'qid_desc':
          return Number(b.question_id) - Number(a.question_id);
        case 'diff_asc': {
          const diffRank = { simple: 1, moderate: 2, challenging: 3 };
          return (diffRank[a.difficulty] || 2) - (diffRank[b.difficulty] || 2);
        }
        case 'diff_desc': {
          const diffRank = { simple: 1, moderate: 2, challenging: 3 };
          return (diffRank[b.difficulty] || 2) - (diffRank[a.difficulty] || 2);
        }
        case 'direct_joins_desc':
          return (b.direct?.joins ?? 0) - (a.direct?.joins ?? 0);
        case 'direct_joins_asc':
          return (a.direct?.joins ?? 0) - (b.direct?.joins ?? 0);
        case 'latency_desc':
          return (b.vsql?.latency_s ?? 0) - (a.vsql?.latency_s ?? 0);
        case 'latency_asc':
          return (a.vsql?.latency_s ?? 0) - (b.vsql?.latency_s ?? 0);
        default:
          return 0;
      }
    });
  }, [questions, search, selectedDb, selectedDiff, filterViewLeak, filterJoin, filterViewUsage, sortBy]);

  // Pagination Calculations
  const totalItems = filteredQuestions.length;
  const isAll = pageSize === 'all';
  const effectivePageSize = isAll ? Math.max(1, totalItems) : Number(pageSize);
  const totalPages = Math.max(1, Math.ceil(totalItems / effectivePageSize));
  const validCurrentPage = Math.min(Math.max(1, currentPage), totalPages);

  const startIndex = isAll ? 0 : (validCurrentPage - 1) * effectivePageSize;
  const endIndex = isAll ? totalItems : Math.min(startIndex + effectivePageSize, totalItems);
  const paginatedQuestions = useMemo(() => {
    return filteredQuestions.slice(startIndex, endIndex);
  }, [filteredQuestions, startIndex, endIndex]);

  const paginationPages = useMemo(() => {
    return getPaginationItems(validCurrentPage, totalPages);
  }, [validCurrentPage, totalPages]);

  // Check if any filter is active
  const isFilterActive = search !== '' || 
    selectedDb !== 'all' || 
    selectedDiff !== 'all' || 
    filterViewLeak !== 'all' || 
    filterJoin !== 'all' || 
    filterViewUsage !== 'all' || 
    sortBy !== 'qid_asc';

  const resetAllFilters = () => {
    setSearch('');
    setSelectedDb('all');
    setSelectedDiff('all');
    setFilterViewLeak('all');
    setFilterJoin('all');
    setFilterViewUsage('all');
    setSortBy('qid_asc');
    setCurrentPage(1);
  };

  const handleJumpPage = (e) => {
    e.preventDefault();
    const p = parseInt(jumpPageInput, 10);
    if (!isNaN(p) && p >= 1 && p <= totalPages) {
      setCurrentPage(p);
      setJumpPageInput('');
    }
  };

  const copyToClipboard = (text, sectionKey) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedSection(sectionKey);
    setTimeout(() => {
      setCopiedSection(null);
    }, 2000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      
      {/* SECTION 1: COMPACT & OPTIMIZED FILTER TOOLBAR */}
      <div className="card" style={{ padding: '0.85rem 1.15rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        
        {/* Row 1: Search Bar & Core Controls */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
          
          {/* Main Search Input */}
          <div style={{ 
            flex: '1 1 340px', 
            display: 'flex', 
            alignItems: 'center', 
            background: '#f8fafc', 
            border: '1px solid #cbd5e1', 
            borderRadius: '8px', 
            padding: '0 12px',
            height: '38px',
            transition: 'border-color 0.15s ease'
          }}>
            <Search size={15} color="#64748b" style={{ flexShrink: 0 }} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm kiếm nội dung câu hỏi, QID (#1471), SQL hoặc CSDL..."
              style={{
                width: '100%',
                padding: '0 0.65rem',
                border: 'none',
                background: 'transparent',
                outline: 'none',
                fontSize: '0.85rem',
                color: '#0f172a'
              }}
            />
            {search && (
              <button 
                onClick={() => setSearch('')}
                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', color: '#94a3b8' }}
                title="Xóa tìm kiếm"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Database Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: '600', color: '#475569', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Database size={13} color="#64748b" /> CSDL:
            </span>
            <select
              value={selectedDb}
              onChange={(e) => setSelectedDb(e.target.value)}
              style={{
                height: '38px',
                padding: '0 0.75rem',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                background: '#ffffff',
                fontSize: '0.825rem',
                color: '#0f172a',
                cursor: 'pointer',
                fontWeight: '500'
              }}
            >
              <option value="all">Tất cả 11 CSDL ({questions.length})</option>
              {dbOptions.map(db => (
                <option key={db.db_id} value={db.db_id}>
                  {db.db_id} ({db.count})
                </option>
              ))}
            </select>
          </div>

          {/* Sort By Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: '600', color: '#475569', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <ArrowUpDown size={13} color="#64748b" /> Sắp xếp:
            </span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              style={{
                height: '38px',
                padding: '0 0.75rem',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                background: '#ffffff',
                fontSize: '0.825rem',
                color: '#0f172a',
                cursor: 'pointer',
                fontWeight: '500'
              }}
            >
              <option value="qid_asc">QID tăng dần (#1471 ➔ #2000)</option>
              <option value="qid_desc">QID giảm dần (#2000 ➔ #1471)</option>
              <option value="diff_asc">Độ khó: Dễ ➔ Khó</option>
              <option value="diff_desc">Độ khó: Khó ➔ Dễ</option>
              <option value="direct_joins_desc">Direct JOINs: Nhiều nhất</option>
              <option value="latency_desc">Thời gian chạy lâu nhất</option>
            </select>
          </div>

          {/* Page Size Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: '600', color: '#475569', whiteSpace: 'nowrap' }}>
              Hiển thị:
            </span>
            <select
              value={pageSize}
              onChange={(e) => setPageSize(e.target.value === 'all' ? 'all' : Number(e.target.value))}
              style={{
                height: '38px',
                padding: '0 0.75rem',
                borderRadius: '8px',
                border: '1px solid #c7d2fe',
                background: '#f5f3ff',
                fontSize: '0.825rem',
                color: '#4f46e5',
                cursor: 'pointer',
                fontWeight: '700'
              }}
            >
              <option value={10}>10 / trang</option>
              <option value={20}>20 / trang (Chuẩn)</option>
              <option value={50}>50 / trang</option>
              <option value={100}>100 / trang</option>
              <option value="all">Tất cả (500)</option>
            </select>
          </div>

          {/* Reset Filters Button */}
          {isFilterActive && (
            <button
              onClick={resetAllFilters}
              className="btn btn-secondary"
              style={{
                height: '38px',
                padding: '0 0.75rem',
                fontSize: '0.8rem',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                color: '#b91c1c',
                borderColor: '#fecaca',
                background: '#fff5f5'
              }}
              title="Đặt lại toàn bộ tiêu chí lọc về mặc định"
            >
              <RotateCcw size={13} />
              <span>Đặt lại</span>
            </button>
          )}

        </div>

        {/* Row 2: Status Chips & Result Count */}
        <div style={{ 
          display: 'flex', 
          flexWrap: 'wrap', 
          gap: '6px', 
          alignItems: 'center',
          paddingTop: '0.65rem',
          borderTop: '1px solid #f1f5f9'
        }}>
          <span style={{ fontSize: '0.725rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: '700', letterSpacing: '0.04em' }}>
            LỌC NHANH:
          </span>

          {/* All chip */}
          <button
            onClick={() => { setSelectedDiff('all'); setFilterViewLeak('all'); setFilterJoin('all'); setFilterViewUsage('all'); }}
            style={{
              padding: '3px 10px',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: selectedDiff === 'all' && filterViewLeak === 'all' && filterJoin === 'all' && filterViewUsage === 'all' ? '700' : '500',
              border: selectedDiff === 'all' && filterViewLeak === 'all' && filterJoin === 'all' && filterViewUsage === 'all' ? '1px solid #4f46e5' : '1px solid #e2e8f0',
              background: selectedDiff === 'all' && filterViewLeak === 'all' && filterJoin === 'all' && filterViewUsage === 'all' ? '#eef2ff' : '#ffffff',
              color: selectedDiff === 'all' && filterViewLeak === 'all' && filterJoin === 'all' && filterViewUsage === 'all' ? '#4f46e5' : '#475569',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            Tất cả ({stats.total})
          </button>

          {/* Simple */}
          <button
            onClick={() => setSelectedDiff(selectedDiff === 'simple' ? 'all' : 'simple')}
            style={{
              padding: '3px 10px',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: selectedDiff === 'simple' ? '700' : '500',
              border: selectedDiff === 'simple' ? '1px solid #10b981' : '1px solid #e2e8f0',
              background: selectedDiff === 'simple' ? '#ecfdf5' : '#ffffff',
              color: selectedDiff === 'simple' ? '#065f46' : '#475569',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            🟢 Simple ({stats.simple})
          </button>

          {/* Moderate */}
          <button
            onClick={() => setSelectedDiff(selectedDiff === 'moderate' ? 'all' : 'moderate')}
            style={{
              padding: '3px 10px',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: selectedDiff === 'moderate' ? '700' : '500',
              border: selectedDiff === 'moderate' ? '1px solid #f59e0b' : '1px solid #e2e8f0',
              background: selectedDiff === 'moderate' ? '#fffbeb' : '#ffffff',
              color: selectedDiff === 'moderate' ? '#92400e' : '#475569',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            🟡 Moderate ({stats.moderate})
          </button>

          {/* Challenging */}
          <button
            onClick={() => setSelectedDiff(selectedDiff === 'challenging' ? 'all' : 'challenging')}
            style={{
              padding: '3px 10px',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: selectedDiff === 'challenging' ? '700' : '500',
              border: selectedDiff === 'challenging' ? '1px solid #ef4444' : '1px solid #e2e8f0',
              background: selectedDiff === 'challenging' ? '#fef2f2' : '#ffffff',
              color: selectedDiff === 'challenging' ? '#991b1b' : '#475569',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            🔴 Challenging ({stats.challenging})
          </button>

          {/* Divider */}
          <div style={{ width: '1px', height: '16px', background: '#cbd5e1', margin: '0 2px' }} />

          {/* View Leak Toggle */}
          <button
            onClick={() => setFilterViewLeak(filterViewLeak === 'leak' ? 'all' : 'leak')}
            style={{
              padding: '3px 10px',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: filterViewLeak === 'leak' ? '700' : '500',
              border: filterViewLeak === 'leak' ? '1px solid #ef4444' : '1px solid #fee2e2',
              background: filterViewLeak === 'leak' ? '#fee2e2' : '#ffffff',
              color: filterViewLeak === 'leak' ? '#991b1b' : '#b91c1c',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              transition: 'all 0.15s ease'
            }}
            title="Lọc 21 câu hỏi mà Stage 2 bị rò rỉ bảng ảo v_*"
          >
            <AlertTriangle size={12} />
            <span>21 Câu View Leak</span>
          </button>

          {/* JOIN Reduction Toggle */}
          <button
            onClick={() => setFilterJoin(filterJoin === 'reduced' ? 'all' : 'reduced')}
            style={{
              padding: '3px 10px',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: filterJoin === 'reduced' ? '700' : '500',
              border: filterJoin === 'reduced' ? '1px solid #10b981' : '1px solid #d1fae5',
              background: filterJoin === 'reduced' ? '#d1fae5' : '#ffffff',
              color: '#065f46',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              transition: 'all 0.15s ease'
            }}
            title="Lọc các câu mà V-SQL Stage 1 giảm số JOIN so với Direct Baseline"
          >
            <TrendingDown size={12} />
            <span>V-SQL Giảm JOIN ({stats.joinReduced})</span>
          </button>

          {/* View Usage Toggle */}
          <button
            onClick={() => setFilterViewUsage(filterViewUsage === 'used' ? 'all' : 'used')}
            style={{
              padding: '3px 10px',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: filterViewUsage === 'used' ? '700' : '500',
              border: filterViewUsage === 'used' ? '1px solid #6366f1' : '1px solid #e0e7ff',
              background: filterViewUsage === 'used' ? '#e0e7ff' : '#ffffff',
              color: '#3730a3',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              transition: 'all 0.15s ease'
            }}
            title="Lọc các câu có tham chiếu đến View ảo"
          >
            <Layers size={12} />
            <span>Có Dùng View ({stats.usedViewsCount})</span>
          </button>

          {/* Live Result Indicator on the right */}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: '#64748b' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }}></span>
            <span>Tìm thấy <b style={{ color: '#0f172a' }}>{totalItems}</b> / {questions.length} câu hỏi</span>
          </div>

        </div>

      </div>

      {/* SECTION 2: QUESTIONS DATA TABLE */}
      <div className="card" style={{ padding: '0', overflow: 'hidden', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)' }}>
        {loading ? (
          <div style={{ padding: '4rem', textAlign: 'center', color: '#64748b' }}>
            <Sparkles size={28} className="animate-spin" style={{ margin: '0 auto 12px', color: '#6366f1' }} />
            <div style={{ fontSize: '0.95rem', fontWeight: '600', color: '#0f172a' }}>Đang nạp 500 câu hỏi và vết suy luận...</div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '4px' }}>Dữ liệu kiểm thử BIRD mini-dev với SQLite</div>
          </div>
        ) : filteredQuestions.length === 0 ? (
          <div style={{ padding: '4rem', textAlign: 'center', color: '#64748b' }}>
            <Filter size={32} style={{ margin: '0 auto 12px', color: '#cbd5e1' }} />
            <div style={{ fontSize: '1rem', fontWeight: '600', color: '#1e293b' }}>Không tìm thấy câu hỏi nào phù hợp</div>
            <div style={{ fontSize: '0.825rem', color: '#94a3b8', marginTop: '4px', maxWidth: '400px', margin: '4px auto 16px' }}>
              Hãy thử thay đổi từ khóa tìm kiếm hoặc điều chỉnh lại các tiêu chí bộ lọc.
            </div>
            <button 
              onClick={resetAllFilters}
              className="btn btn-secondary"
              style={{ fontSize: '0.85rem' }}
            >
              <RotateCcw size={14} /> Xóa tất cả bộ lọc
            </button>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ background: '#f8fafc', color: '#475569', borderBottom: '1px solid #e2e8f0', position: 'sticky', top: 0, zIndex: 10 }}>
                  <th style={{ padding: '12px 14px', width: '75px', fontWeight: '700', fontSize: '0.8rem' }}>QID</th>
                  <th style={{ padding: '12px 14px', width: '140px', fontWeight: '700', fontSize: '0.8rem' }}>CSDL</th>
                  <th style={{ padding: '12px 14px', width: '105px', fontWeight: '700', fontSize: '0.8rem' }}>Độ khó</th>
                  <th style={{ padding: '12px 14px', fontWeight: '700', fontSize: '0.8rem' }}>Nội dung câu hỏi</th>
                  <th style={{ padding: '12px 14px', width: '125px', fontWeight: '700', fontSize: '0.8rem' }}>Thời gian (s)</th>
                  <th style={{ padding: '12px 14px', width: '100px', textAlign: 'center', fontWeight: '700', fontSize: '0.8rem' }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {paginatedQuestions.map((q) => {
                  const isLeak = q.vsql?.view_leak;

                  return (
                    <tr 
                      key={q.question_id}
                      style={{ 
                        borderBottom: '1px solid #f1f5f9', 
                        transition: 'background 0.15s ease',
                        background: isLeak ? 'rgba(254, 242, 242, 0.35)' : 'transparent'
                      }}
                      className="table-row-hover"
                    >
                      {/* QID */}
                      <td style={{ padding: '12px 14px', fontWeight: '700', color: '#4f46e5', fontFamily: 'var(--font-mono)' }}>
                        #{q.question_id}
                      </td>

                      {/* CSDL */}
                      <td style={{ padding: '12px 14px' }}>
                        <span 
                          className="badge badge-neutral" 
                          style={{ 
                            fontSize: '0.725rem', 
                            display: 'inline-flex', 
                            alignItems: 'center', 
                            gap: '4px',
                            background: '#f1f5f9',
                            maxWidth: '130px',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                          }}
                          title={q.db_id}
                        >
                          <Database size={11} color="#64748b" />
                          {q.db_id}
                        </span>
                      </td>

                      {/* Difficulty Badge */}
                      <td style={{ padding: '12px 14px' }}>
                        <span 
                          className={`badge ${
                            q.difficulty === 'simple' 
                              ? 'badge-success' 
                              : q.difficulty === 'moderate' 
                              ? 'badge-warning' 
                              : 'badge-danger'
                          }`} 
                          style={{ fontSize: '0.725rem', textTransform: 'capitalize' }}
                        >
                          {q.difficulty}
                        </span>
                      </td>

                      {/* Question Text */}
                      <td style={{ padding: '12px 14px', color: '#0f172a' }}>
                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '10px' }}>
                          <div style={{ fontWeight: '600', fontSize: '0.875rem', lineHeight: '1.45', flex: 1 }}>
                            {q.question}
                          </div>
                          {isLeak && (
                            <span 
                              style={{ 
                                fontSize: '0.675rem', 
                                color: '#b91c1c', 
                                background: '#fee2e2', 
                                padding: '2px 7px', 
                                borderRadius: '4px', 
                                fontWeight: '700', 
                                border: '1px solid #fca5a5',
                                whiteSpace: 'nowrap',
                                flexShrink: 0
                              }}
                              title="Câu hỏi này gặp hiện tượng View Leak tại Stage 2"
                            >
                              ⚠️ View Leak
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Latency */}
                      <td style={{ padding: '12px 14px', fontSize: '0.75rem', color: '#64748b' }}>
                        <div>Direct: <b>{q.direct?.latency_s ? `${q.direct.latency_s.toFixed(1)}s` : '-'}</b></div>
                        <div>V-SQL: <b>{q.vsql?.latency_s ? `${q.vsql.latency_s.toFixed(1)}s` : '-'}</b></div>
                      </td>

                      {/* Actions */}
                      <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                        <div style={{ display: 'flex', justifyContent: 'center', gap: '6px' }}>
                          <button
                            onClick={() => setSelectedModalItem(q)}
                            className="btn btn-secondary"
                            style={{ padding: '5px 8px', fontSize: '0.75rem', borderRadius: '6px' }}
                            title="Xem đối chiếu chi tiết 3 câu SQL (Gold, Direct, V-SQL)"
                          >
                            <Eye size={14} color="#4f46e5" />
                          </button>
                          {onTryQuestion && (
                            <button
                              onClick={() => onTryQuestion(q)}
                              className="btn btn-secondary"
                              style={{ padding: '5px 8px', fontSize: '0.75rem', borderRadius: '6px' }}
                              title="Thử câu hỏi này trong Phòng thử nghiệm (Playground)"
                            >
                              <PlaySquare size={14} color="#059669" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* SECTION 3: PAGINATION CONTROLS BAR (Explicit Requirement) */}
        {!loading && filteredQuestions.length > 0 && (
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            padding: '0.85rem 1.25rem',
            background: '#ffffff',
            borderTop: '1px solid #e2e8f0',
            fontSize: '0.825rem'
          }}>
            
            {/* Left: Summary Info & Page Size */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', color: '#64748b' }}>
              <div>
                Hiển thị từ <b>{startIndex + 1}</b> - <b>{endIndex}</b> trong <b>{totalItems}</b> câu hỏi 
                {!isAll && (
                  <span> (Trang <b>{validCurrentPage}</b> / {totalPages})</span>
                )}
              </div>
            </div>

            {/* Center: Pagination Button Controls */}
            {!isAll && totalPages > 1 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                
                {/* First Page */}
                <button
                  onClick={() => setCurrentPage(1)}
                  disabled={validCurrentPage === 1}
                  className="btn btn-secondary"
                  style={{ padding: '5px 8px', minWidth: '32px', height: '32px' }}
                  title="Về trang đầu tiên"
                >
                  <ChevronsLeft size={14} />
                </button>

                {/* Prev Page */}
                <button
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={validCurrentPage === 1}
                  className="btn btn-secondary"
                  style={{ padding: '5px 8px', minWidth: '32px', height: '32px' }}
                  title="Trang trước"
                >
                  <ChevronLeft size={14} />
                </button>

                {/* Page Number Buttons */}
                {paginationPages.map((p, idx) => {
                  if (p === '...') {
                    return (
                      <span key={`dots-${idx}`} style={{ padding: '0 6px', color: '#94a3b8', userSelect: 'none' }}>
                        ...
                      </span>
                    );
                  }
                  const isActive = p === validCurrentPage;
                  return (
                    <button
                      key={p}
                      onClick={() => setCurrentPage(p)}
                      style={{
                        minWidth: '34px',
                        height: '32px',
                        padding: '0 8px',
                        borderRadius: '6px',
                        fontSize: '0.8rem',
                        fontWeight: isActive ? '700' : '500',
                        cursor: 'pointer',
                        border: isActive ? '1px solid #4f46e5' : '1px solid #cbd5e1',
                        background: isActive ? '#4f46e5' : '#ffffff',
                        color: isActive ? '#ffffff' : '#334155',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      {p}
                    </button>
                  );
                })}

                {/* Next Page */}
                <button
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={validCurrentPage === totalPages}
                  className="btn btn-secondary"
                  style={{ padding: '5px 8px', minWidth: '32px', height: '32px' }}
                  title="Trang kế tiếp"
                >
                  <ChevronRight size={14} />
                </button>

                {/* Last Page */}
                <button
                  onClick={() => setCurrentPage(totalPages)}
                  disabled={validCurrentPage === totalPages}
                  className="btn btn-secondary"
                  style={{ padding: '5px 8px', minWidth: '32px', height: '32px' }}
                  title="Đến trang cuối cùng"
                >
                  <ChevronsRight size={14} />
                </button>

              </div>
            )}

            {/* Right: Quick Jump to Page Form */}
            {!isAll && totalPages > 1 && (
              <form onSubmit={handleJumpPage} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ color: '#64748b', fontSize: '0.8rem' }}>Đến trang:</span>
                <input
                  type="number"
                  min="1"
                  max={totalPages}
                  value={jumpPageInput}
                  onChange={(e) => setJumpPageInput(e.target.value)}
                  placeholder={String(validCurrentPage)}
                  style={{
                    width: '50px',
                    padding: '4px 6px',
                    borderRadius: '6px',
                    border: '1px solid #cbd5e1',
                    fontSize: '0.8rem',
                    textAlign: 'center'
                  }}
                />
                <button
                  type="submit"
                  className="btn btn-secondary"
                  style={{ padding: '4px 10px', fontSize: '0.78rem', height: '28px' }}
                >
                  Đi
                </button>
              </form>
            )}

          </div>
        )}
      </div>

      {/* SECTION 4: OPTIMIZED QUERY INSPECTOR MODAL */}
      {selectedModalItem && (
        <div 
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15, 23, 42, 0.55)',
            backdropFilter: 'blur(6px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1.25rem'
          }}
          onClick={() => setSelectedModalItem(null)}
        >
          <div 
            style={{
              background: '#ffffff',
              borderRadius: '16px',
              maxWidth: '1000px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              border: '1px solid #cbd5e1',
              padding: '1.25rem 1.5rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* 1. Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <span className="badge badge-primary" style={{ fontSize: '0.825rem', fontFamily: 'var(--font-mono)' }}>
                  QID #{selectedModalItem.question_id}
                </span>
                <span className="badge badge-neutral" style={{ fontSize: '0.825rem' }}>
                  <Database size={12} /> {selectedModalItem.db_id}
                </span>
                <span className={`badge ${
                  selectedModalItem.difficulty === 'simple' 
                    ? 'badge-success' 
                    : selectedModalItem.difficulty === 'moderate' 
                    ? 'badge-warning' 
                    : 'badge-danger'
                }`} style={{ fontSize: '0.825rem', textTransform: 'capitalize' }}>
                  {selectedModalItem.difficulty}
                </span>
                {selectedModalItem.vsql?.view_leak && (
                  <span className="badge badge-danger" style={{ fontSize: '0.75rem' }}>
                    <AlertTriangle size={12} /> View Leak (v_*)
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {onTryQuestion && (
                  <button
                    onClick={() => {
                      onTryQuestion(selectedModalItem);
                      setSelectedModalItem(null);
                    }}
                    className="btn btn-primary"
                    style={{ padding: '5px 12px', fontSize: '0.8rem', borderRadius: '6px' }}
                  >
                    <PlaySquare size={14} /> Thử trong Playground
                  </button>
                )}
                <button 
                  onClick={() => setSelectedModalItem(null)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b', padding: '4px' }}
                  title="Đóng modal"
                >
                  <X size={20} />
                </button>
              </div>
            </div>

            {/* 2. Natural Question & Evidence Banner */}
            <div style={{ background: '#f8fafc', padding: '0.85rem 1rem', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: '0.72rem', fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                CÂU HỎI TỰ NHIÊN (BIRD BENCHMARK)
              </div>
              <div style={{ fontSize: '0.98rem', fontWeight: '600', color: '#0f172a', marginTop: '3px', lineHeight: '1.45' }}>
                {selectedModalItem.question}
              </div>

              {selectedModalItem.evidence && (
                <div style={{ 
                  marginTop: '6px', 
                  padding: '5px 8px', 
                  background: '#fffbeb', 
                  borderRadius: '6px', 
                  border: '1px solid #fde68a',
                  fontSize: '0.8rem', 
                  color: '#92400e' 
                }}>
                  <b>💡 Gợi ý (Evidence): </b>
                  <span style={{ fontStyle: 'italic' }}>{selectedModalItem.evidence}</span>
                </div>
              )}
            </div>

            {/* 3. Sleek Key Metrics Strip */}
            <div style={{ 
              display: 'flex', 
              flexWrap: 'wrap', 
              alignItems: 'center', 
              justifyContent: 'space-between',
              gap: '0.75rem',
              padding: '0.6rem 0.85rem',
              background: '#f1f5f9',
              borderRadius: '8px',
              fontSize: '0.8rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                <div>
                  <span style={{ color: '#64748b' }}>Direct Baseline: </span>
                  <b style={{ color: '#4f46e5' }}>{selectedModalItem.direct?.joins ?? 0} JOINs</b>
                  <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}> ({selectedModalItem.direct?.latency_s?.toFixed(1) || 0}s • {selectedModalItem.direct?.tokens ?? 0} tok)</span>
                </div>
                <div style={{ width: '1px', height: '14px', background: '#cbd5e1' }} />
                <div>
                  <span style={{ color: '#64748b' }}>V-SQL Pipeline: </span>
                  <b style={{ color: '#0284c7' }}>{selectedModalItem.vsql?.dummy_joins ?? 0} (S1)</b>
                  <span style={{ color: '#64748b' }}> ➔ </span>
                  <b style={{ color: '#0f172a' }}>{selectedModalItem.vsql?.final_joins ?? 0} (S2)</b>
                  <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}> ({selectedModalItem.vsql?.latency_s?.toFixed(1) || 0}s)</span>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ color: '#64748b', fontSize: '0.75rem' }}>Views ảo:</span>
                {selectedModalItem.vsql?.used_views && selectedModalItem.vsql.used_views.length > 0 ? (
                  selectedModalItem.vsql.used_views.map((v, i) => (
                    <span key={i} style={{ fontSize: '0.7rem', background: '#e0e7ff', color: '#3730a3', padding: '1px 6px', borderRadius: '4px', fontFamily: 'var(--font-mono)' }}>
                      {v}
                    </span>
                  ))
                ) : (
                  <span style={{ fontSize: '0.72rem', color: '#94a3b8', fontStyle: 'italic' }}>Không dùng View</span>
                )}
              </div>
            </div>

            {/* 4. Tab Navigation for Clean Views */}
            <div style={{ display: 'flex', gap: '6px', borderBottom: '1px solid #e2e8f0', paddingBottom: '2px' }}>
              <button
                onClick={() => setModalTab('compare')}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px 6px 0 0',
                  fontSize: '0.8rem',
                  fontWeight: modalTab === 'compare' ? '700' : '500',
                  border: 'none',
                  borderBottom: modalTab === 'compare' ? '2px solid #4f46e5' : '2px solid transparent',
                  background: modalTab === 'compare' ? '#eef2ff' : 'transparent',
                  color: modalTab === 'compare' ? '#4f46e5' : '#64748b',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                ⚖️ Đối chiếu Song song (Side-by-Side)
              </button>
              <button
                onClick={() => setModalTab('vsql')}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px 6px 0 0',
                  fontSize: '0.8rem',
                  fontWeight: modalTab === 'vsql' ? '700' : '500',
                  border: 'none',
                  borderBottom: modalTab === 'vsql' ? '2px solid #4f46e5' : '2px solid transparent',
                  background: modalTab === 'vsql' ? '#eef2ff' : 'transparent',
                  color: modalTab === 'vsql' ? '#4f46e5' : '#64748b',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                🟣 Chi tiết V-SQL (Stage 1 &amp; 2)
              </button>
              <button
                onClick={() => setModalTab('direct')}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px 6px 0 0',
                  fontSize: '0.8rem',
                  fontWeight: modalTab === 'direct' ? '700' : '500',
                  border: 'none',
                  borderBottom: modalTab === 'direct' ? '2px solid #4f46e5' : '2px solid transparent',
                  background: modalTab === 'direct' ? '#eef2ff' : 'transparent',
                  color: modalTab === 'direct' ? '#4f46e5' : '#64748b',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                🔵 Direct Baseline SQL
              </button>
              <button
                onClick={() => setModalTab('gold')}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px 6px 0 0',
                  fontSize: '0.8rem',
                  fontWeight: modalTab === 'gold' ? '700' : '500',
                  border: 'none',
                  borderBottom: modalTab === 'gold' ? '2px solid #10b981' : '2px solid transparent',
                  background: modalTab === 'gold' ? '#ecfdf5' : 'transparent',
                  color: modalTab === 'gold' ? '#065f46' : '#64748b',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                🟢 Gold SQL (Chuẩn Benchmark)
              </button>
            </div>

            {/* 5. TAB CONTENTS */}
            
            {/* VIEW MODE 1: SIDE-BY-SIDE (Symmetric 2-column layout - Extremely intuitive!) */}
            {modalTab === 'compare' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem' }}>
                
                {/* LEFT COLUMN: BASELINE & GROUND TRUTH */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  
                  {/* Direct Baseline */}
                  <div style={{ borderRadius: '8px', border: '1px solid #cbd5e1', overflow: 'hidden' }}>
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center', 
                      background: '#f1f5f9', 
                      padding: '6px 10px',
                      borderBottom: '1px solid #cbd5e1'
                    }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: '700', color: '#334155' }}>
                        🔵 DIRECT BASELINE SQL ({selectedModalItem.direct?.joins ?? 0} JOINs)
                      </div>
                      <button
                        onClick={() => copyToClipboard(formatSql(selectedModalItem.direct?.final_sql), 'direct')}
                        className="btn btn-secondary"
                        style={{ padding: '2px 6px', fontSize: '0.7rem', height: '22px' }}
                      >
                        {copiedSection === 'direct' ? <><Check size={11} /> Đã chép</> : <><Copy size={11} /> Chép</>}
                      </button>
                    </div>
                    <pre style={{ 
                      background: '#f8fafc', 
                      padding: '10px 12px', 
                      fontSize: '0.785rem', 
                      color: '#0f172a', 
                      margin: 0,
                      maxHeight: '150px',
                      overflowY: 'auto',
                      whiteSpace: 'pre-wrap', 
                      wordBreak: 'break-word',
                      lineHeight: '1.45',
                      fontFamily: 'var(--font-mono)'
                    }}>
                      {formatSql(selectedModalItem.direct?.final_sql) || 'Chưa có dự đoán'}
                    </pre>
                  </div>

                  {/* Gold Ground Truth */}
                  <div style={{ borderRadius: '8px', border: '1px solid #a7f3d0', overflow: 'hidden' }}>
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center', 
                      background: '#ecfdf5', 
                      padding: '6px 10px',
                      borderBottom: '1px solid #a7f3d0'
                    }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: '700', color: '#065f46' }}>
                        🟢 GOLD SQL (Truy vấn Chuẩn Benchmark)
                      </div>
                      <button
                        onClick={() => copyToClipboard(formatSql(selectedModalItem.gold_sql), 'gold')}
                        className="btn btn-secondary"
                        style={{ padding: '2px 6px', fontSize: '0.7rem', height: '22px', borderColor: '#a7f3d0', color: '#065f46' }}
                      >
                        {copiedSection === 'gold' ? <><Check size={11} /> Đã chép</> : <><Copy size={11} /> Chép</>}
                      </button>
                    </div>
                    <pre style={{ 
                      background: '#f0fdf4', 
                      padding: '10px 12px', 
                      fontSize: '0.785rem', 
                      color: '#064e3b', 
                      margin: 0,
                      maxHeight: '150px',
                      overflowY: 'auto',
                      whiteSpace: 'pre-wrap', 
                      wordBreak: 'break-word',
                      lineHeight: '1.45',
                      fontFamily: 'var(--font-mono)'
                    }}>
                      {formatSql(selectedModalItem.gold_sql) || 'Chưa có dữ liệu Gold SQL'}
                    </pre>
                  </div>

                </div>

                {/* RIGHT COLUMN: V-SQL TWO-STAGE PIPELINE */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  
                  {/* Stage 1: Dummy SQL */}
                  <div style={{ borderRadius: '8px', border: '1px solid #bae6fd', overflow: 'hidden' }}>
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center', 
                      background: '#f0f9ff', 
                      padding: '6px 10px',
                      borderBottom: '1px solid #bae6fd'
                    }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: '700', color: '#0369a1' }}>
                        🟣 V-SQL: STAGE 1 DUMMY SQL ({selectedModalItem.vsql?.dummy_joins ?? 0} JOINs)
                      </div>
                      <button
                        onClick={() => copyToClipboard(formatSql(selectedModalItem.vsql?.dummy_sql), 'dummy')}
                        className="btn btn-secondary"
                        style={{ padding: '2px 6px', fontSize: '0.7rem', height: '22px' }}
                      >
                        {copiedSection === 'dummy' ? <Check size={11} /> : <Copy size={11} />}
                      </button>
                    </div>
                    <pre style={{ 
                      background: '#ffffff', 
                      padding: '10px 12px', 
                      fontSize: '0.785rem', 
                      color: '#0f172a', 
                      margin: 0,
                      maxHeight: '130px',
                      overflowY: 'auto',
                      whiteSpace: 'pre-wrap', 
                      wordBreak: 'break-word',
                      lineHeight: '1.45',
                      fontFamily: 'var(--font-mono)'
                    }}>
                      {formatSql(selectedModalItem.vsql?.dummy_sql) || 'N/A (Chưa sinh Stage 1)'}
                    </pre>
                  </div>

                  {/* Transition Indicator */}
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center', 
                    gap: '6px', 
                    fontSize: '0.72rem', 
                    color: '#6366f1', 
                    fontWeight: '600'
                  }}>
                    <span>⬇️ Stage 2: Thay thế ngược về schema database thật</span>
                  </div>

                  {/* Stage 2: Final SQL */}
                  <div style={{ borderRadius: '8px', border: '1px solid #c7d2fe', overflow: 'hidden' }}>
                    <div style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center', 
                      background: '#eef2ff', 
                      padding: '6px 10px',
                      borderBottom: '1px solid #c7d2fe'
                    }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: '700', color: '#4338ca' }}>
                        🟣 V-SQL: STAGE 2 FINAL SQL ({selectedModalItem.vsql?.final_joins ?? 0} JOINs)
                      </div>
                      <button
                        onClick={() => copyToClipboard(formatSql(selectedModalItem.vsql?.final_sql), 'vfinal')}
                        className="btn btn-secondary"
                        style={{ padding: '2px 6px', fontSize: '0.7rem', height: '22px' }}
                      >
                        {copiedSection === 'vfinal' ? <Check size={11} /> : <Copy size={11} />}
                      </button>
                    </div>
                    <pre style={{ 
                      background: '#ffffff', 
                      padding: '10px 12px', 
                      fontSize: '0.785rem', 
                      color: '#0f172a', 
                      margin: 0,
                      maxHeight: '130px',
                      overflowY: 'auto',
                      whiteSpace: 'pre-wrap', 
                      wordBreak: 'break-word',
                      lineHeight: '1.45',
                      fontFamily: 'var(--font-mono)'
                    }}>
                      {formatSql(selectedModalItem.vsql?.final_sql) || 'N/A (Chưa sinh Stage 2)'}
                    </pre>
                  </div>

                  {/* View Leak Warning (if any) */}
                  {selectedModalItem.vsql?.view_leak && (
                    <div style={{ 
                      background: '#fef2f2', 
                      border: '1px solid #fecaca', 
                      borderRadius: '6px', 
                      padding: '6px 10px', 
                      fontSize: '0.75rem', 
                      color: '#991b1b',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}>
                      <AlertTriangle size={13} style={{ flexShrink: 0 }} />
                      <span><b>Phát hiện View Leak:</b> Stage 2 vẫn còn chứa tiền tố <code>v_*</code> do mô hình không unroll triệt để.</span>
                    </div>
                  )}

                </div>

              </div>
            )}

            {/* VIEW MODE 2: V-SQL PIPELINE FULL DETAIL */}
            {modalTab === 'vsql' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ borderRadius: '8px', border: '1px solid #bae6fd', overflow: 'hidden' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f0f9ff', padding: '8px 12px' }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: '700', color: '#0369a1' }}>
                      Stage 1: Dummy SQL (Viết trên Views ảo — Giảm số lượng JOINs)
                    </span>
                    <button onClick={() => copyToClipboard(formatSql(selectedModalItem.vsql?.dummy_sql), 'dummy')} className="btn btn-secondary" style={{ padding: '2px 8px', fontSize: '0.72rem' }}>
                      {copiedSection === 'dummy' ? 'Đã sao chép' : 'Sao chép'}
                    </button>
                  </div>
                  <pre style={{ background: '#ffffff', padding: '12px 14px', fontSize: '0.82rem', margin: 0, maxHeight: '240px', overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: '1.45', fontFamily: 'var(--font-mono)' }}>
                    {formatSql(selectedModalItem.vsql?.dummy_sql) || 'N/A'}
                  </pre>
                </div>

                <div style={{ textAlign: 'center', color: '#4f46e5', fontWeight: '600', fontSize: '0.78rem' }}>
                  ⬇️ Quá trình Thay thế ngược (View Substitution / Unrolling) vào schema SQLite thật
                </div>

                <div style={{ borderRadius: '8px', border: '1px solid #c7d2fe', overflow: 'hidden' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#eef2ff', padding: '8px 12px' }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: '700', color: '#4338ca' }}>
                      Stage 2: Final SQL (Truy vấn hoàn chỉnh sau khi unroll)
                    </span>
                    <button onClick={() => copyToClipboard(formatSql(selectedModalItem.vsql?.final_sql), 'vfinal')} className="btn btn-secondary" style={{ padding: '2px 8px', fontSize: '0.72rem' }}>
                      {copiedSection === 'vfinal' ? 'Đã sao chép' : 'Sao chép'}
                    </button>
                  </div>
                  <pre style={{ background: '#ffffff', padding: '12px 14px', fontSize: '0.82rem', margin: 0, maxHeight: '240px', overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: '1.45', fontFamily: 'var(--font-mono)' }}>
                    {formatSql(selectedModalItem.vsql?.final_sql) || 'N/A'}
                  </pre>
                </div>
              </div>
            )}

            {/* VIEW MODE 3: DIRECT BASELINE DETAIL */}
            {modalTab === 'direct' && (
              <div style={{ borderRadius: '8px', border: '1px solid #cbd5e1', overflow: 'hidden' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f1f5f9', padding: '8px 12px' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: '700', color: '#334155' }}>
                    Direct Baseline SQL (Sinh trực tiếp 1 chặng trên toàn bộ bảng gốc)
                  </span>
                  <button onClick={() => copyToClipboard(formatSql(selectedModalItem.direct?.final_sql), 'direct')} className="btn btn-secondary" style={{ padding: '2px 8px', fontSize: '0.72rem' }}>
                    {copiedSection === 'direct' ? 'Đã sao chép' : 'Sao chép'}
                  </button>
                </div>
                <pre style={{ background: '#f8fafc', padding: '14px', fontSize: '0.82rem', margin: 0, maxHeight: '350px', overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: '1.45', fontFamily: 'var(--font-mono)' }}>
                  {formatSql(selectedModalItem.direct?.final_sql) || 'Chưa có dự đoán'}
                </pre>
              </div>
            )}

            {/* VIEW MODE 4: GOLD SQL DETAIL */}
            {modalTab === 'gold' && (
              <div style={{ borderRadius: '8px', border: '1px solid #a7f3d0', overflow: 'hidden' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#ecfdf5', padding: '8px 12px' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: '700', color: '#065f46' }}>
                    Gold Standard SQL (Đáp án Chuẩn Ground Truth của BIRD Benchmark)
                  </span>
                  <button onClick={() => copyToClipboard(formatSql(selectedModalItem.gold_sql), 'gold')} className="btn btn-secondary" style={{ padding: '2px 8px', fontSize: '0.72rem', color: '#065f46', borderColor: '#a7f3d0' }}>
                    {copiedSection === 'gold' ? 'Đã sao chép' : 'Sao chép'}
                  </button>
                </div>
                <pre style={{ background: '#f0fdf4', padding: '14px', fontSize: '0.82rem', color: '#064e3b', margin: 0, maxHeight: '350px', overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: '1.45', fontFamily: 'var(--font-mono)' }}>
                  {formatSql(selectedModalItem.gold_sql) || 'Chưa có dữ liệu Gold SQL'}
                </pre>
              </div>
            )}

          </div>
        </div>
      )}

    </div>
  );
}
