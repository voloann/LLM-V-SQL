import React, { useState } from 'react';
import { 
  Layers, 
  ArrowRight, 
  ArrowDown, 
  Database, 
  Code2, 
  Sparkles, 
  CheckCircle2, 
  AlertTriangle,
  Zap,
  Cpu,
  TrendingDown,
  Clock,
  Copy,
  Check,
  FileCode,
  GitBranch,
  ShieldCheck,
  ChevronRight,
  Eye,
  Server,
  Terminal,
  HelpCircle,
  FileText
} from 'lucide-react';
import { formatSql } from '../utils/sqlFormatter';

export default function Architecture() {
  const [activeTab, setActiveTab] = useState('pipeline'); // 'pipeline', 'casestudy', 'comparison'
  const [copiedSection, setCopiedSection] = useState(null);
  const [selectedPipelineStep, setSelectedPipelineStep] = useState(null);

  const copyToClipboard = (text, key) => {
    if (!text) return;
    navigator.clipboard.writeText(formatSql(text));
    setCopiedSection(key);
    setTimeout(() => {
      setCopiedSection(null);
    }, 2000);
  };

  // Dữ liệu chi tiết cho 8 bước Case Study Q724
  const caseStudySteps = [
    {
      num: 1,
      phase: 'INPUT',
      title: 'Câu hỏi Tự nhiên (Natural Language Question)',
      badge: 'Đầu vào Người dùng',
      badgeColor: 'badge-primary',
      desc: 'Câu hỏi người dùng nhập vào hệ thống, yêu cầu tìm kiếm thuộc tính liên quan đến nhiều bảng trong cơ sở dữ liệu.',
      content: 'Please list the superhero names of all the superheroes that have blue eyes and blond hair.',
      type: 'text'
    },
    {
      num: 2,
      phase: 'EVIDENCE',
      title: 'Tri thức Bổ trợ ngoài (External Knowledge / Evidence)',
      badge: 'BIRD Benchmark Domain Hint',
      badgeColor: 'badge-warning',
      desc: 'Cung cấp ánh xạ ngữ nghĩa giữa ngôn ngữ tự nhiên và giá trị/thuộc tính trong CSDL (đặc trưng quan trọng của BIRD).',
      content: "blue eyes refers to colour = 'Blue' and eye_colour_id = colour.id; blond hair refers to colour = 'Blond' and hair_colour_id = colour.id",
      type: 'evidence'
    },
    {
      num: 3,
      phase: 'PHA 1',
      title: 'Định nghĩa View Khái niệm (Conceptual View Schema)',
      badge: 'Pha 1: Chuẩn bị Offline',
      badgeColor: 'badge-neutral',
      desc: 'View ảo gộp các bảng liên kết khóa ngoại (1-N, N-N) thành một bảng phẳng duy nhất, ẩn các quan hệ FK phức tạp.',
      content: 'v_superhero (superhero_name, full_name, eye_colour, hair_colour, skin_colour, publisher_name, alignment, gender, height_cm, weight_kg)',
      type: 'schema'
    },
    {
      num: 4,
      phase: 'STAGE 1',
      title: 'Stage 1 — Sinh Dummy SQL (Trước JOIN — 0 JOINs)',
      badge: 'Triệt tiêu JOIN (0 JOIN)',
      badgeColor: 'badge-success',
      desc: 'Mô hình sinh câu lệnh SQL trên View phẳng. LLM không bị rối loạn khóa ngoại (FK Hallucination) và chỉ tập trung vào mệnh đề SELECT & WHERE.',
      joins: 0,
      sql: "SELECT v_superhero.superhero_name\nFROM v_superhero\nWHERE v_superhero.eye_colour = 'Blue'\n  AND v_superhero.hair_colour = 'Blond'",
      type: 'sql'
    },
    {
      num: 5,
      phase: 'SCHEMA LINKING',
      title: 'Mapping Rules & Cơ chế Thay thế ngược (View Substitution)',
      badge: 'Cơ chế Chuyển tiếp',
      badgeColor: 'badge-primary',
      desc: 'Hệ thống nhận diện view `v_superhero` được dùng ở Stage 1, trích xuất mapping rule định nghĩa tương ứng và đưa vào prompt Stage 2.',
      sql: "CREATE VIEW v_superhero AS\nSELECT superhero.superhero_name,\n       eye_colour.colour AS eye_colour,\n       hair_colour.colour AS hair_colour\nFROM superhero\nLEFT JOIN colour AS eye_colour ON superhero.eye_colour_id = eye_colour.id\nLEFT JOIN colour AS hair_colour ON superhero.hair_colour_id = hair_colour.id",
      type: 'sql'
    },
    {
      num: 6,
      phase: 'STAGE 2',
      title: 'Stage 2 — Sinh Final SQL (Sau JOIN — Phục hồi bảng gốc)',
      badge: 'Phục hồi 2 JOINs',
      badgeColor: 'badge-primary',
      desc: 'LLM nhận Dummy SQL và Mapping Rules, unroll View ảo trở lại bảng vật lý SQLite gốc với các mệnh đề JOIN và alias chính xác.',
      joins: 2,
      sql: "SELECT superhero.superhero_name\nFROM superhero\nINNER JOIN colour AS eye_colour ON superhero.eye_colour_id = eye_colour.id\nINNER JOIN colour AS hair_colour ON superhero.hair_colour_id = hair_colour.id\nWHERE eye_colour.colour = 'Blue'\n  AND hair_colour.colour = 'Blond'",
      type: 'sql'
    },
    {
      num: 7,
      phase: 'GROUND TRUTH',
      title: 'Gold SQL Chuẩn Đối chứng (BIRD Benchmark Ground Truth)',
      badge: 'Đáp án Chuẩn',
      badgeColor: 'badge-neutral',
      desc: 'Câu truy vấn chuẩn do các chuyên gia dữ liệu của BIRD Benchmark biên soạn để làm mốc đánh giá.',
      joins: 2,
      sql: "SELECT T1.superhero_name\nFROM superhero AS T1\nINNER JOIN colour AS T2 ON T1.eye_colour_id = T2.id\nINNER JOIN colour AS T3 ON T1.hair_colour_id = T3.id\nWHERE T2.colour = 'Blue'\n  AND T3.colour = 'Blond'",
      type: 'sql'
    },
    {
      num: 8,
      phase: 'EVALUATION',
      title: 'Đánh giá Thực thi & So khớp Cú pháp',
      badge: 'Thành công Tuyệt đối ✅',
      badgeColor: 'badge-success',
      desc: 'Thực thi trên SQLite database thật (`superhero.sqlite`) và so sánh đối chiếu giữa Final SQL và Gold SQL.',
      stats: [
        { label: 'Execution Accuracy (EX)', value: '1.0 (100% Khớp kết quả thực thi)', color: '#16a34a' },
        { label: 'Exact Match AST (EM-Norm)', value: '1.0 (100% Khớp cú pháp chuẩn hóa)', color: '#2563eb' },
        { label: 'Số lượng JOINs Stage 1', value: '0 JOINs (giảm 100% so với gốc)', color: '#0891b2' },
        { label: 'Số lượng JOINs Stage 2', value: '2 JOINs (phục hồi chuẩn 2 alias bảng colour)', color: '#4f46e5' }
      ],
      type: 'eval'
    }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      
      {/* 1. Header Hero Card */}
      <div className="card" style={{ padding: '1.5rem', background: 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span className="badge badge-primary" style={{ fontSize: '0.75rem' }}>
                HuaweiSoft • 2024
              </span>
              <span className="badge badge-neutral" style={{ fontSize: '0.75rem' }}>
                You et al. • EMNLP / arXiv:2403.02984
              </span>
            </div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: '800', color: '#0f172a', margin: '4px 0 8px 0', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Layers size={24} color="#4f46e5" />
              <span>Kiến trúc Framework V-SQL (View-based Two-stage Text-to-SQL)</span>
            </h2>
            <p style={{ margin: 0, fontSize: '0.875rem', color: '#475569', lineHeight: '1.6', maxWidth: '900px' }}>
              Framework <b>V-SQL</b> giải quyết điểm yếu cốt lõi của các mô hình LLM khi sinh SQL: <b>Foreign-Key Hallucination</b> (nhầm lẫn giữa các khóa ngoại và liên kết sai bảng khi câu hỏi yêu cầu nhiều mệnh đề JOIN phức tạp). Phương pháp chia quá trình suy luận làm <b>2 Pha độc lập</b>: làm phẳng lược đồ trước khi sinh SQL (Stage 1), sau đó phục hồi về bảng vật lý (Stage 2).
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'flex-end' }}>
            <div style={{ display: 'flex', gap: '6px' }}>
              <span className="badge badge-success" style={{ fontSize: '0.8rem', padding: '5px 10px' }}>
                Giảm 56.2% JOINs (Stage 1)
              </span>
              <span className="badge badge-primary" style={{ fontSize: '0.8rem', padding: '5px 10px' }}>
                Chia để trị (Divide & Conquer)
              </span>
            </div>
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
              Thực nghiệm trên 500 câu BIRD mini-dev
            </span>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div style={{ display: 'flex', gap: '8px', marginTop: '1.5rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '2px' }}>
          <button
            onClick={() => setActiveTab('pipeline')}
            style={{
              padding: '8px 16px',
              borderRadius: '8px 8px 0 0',
              fontSize: '0.85rem',
              fontWeight: activeTab === 'pipeline' ? '700' : '500',
              border: 'none',
              borderBottom: activeTab === 'pipeline' ? '2px solid #4f46e5' : '2px solid transparent',
              background: activeTab === 'pipeline' ? '#eef2ff' : 'transparent',
              color: activeTab === 'pipeline' ? '#4f46e5' : '#64748b',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease'
            }}
          >
            <GitBranch size={16} /> Sơ đồ Luồng Pipeline Toàn cảnh
          </button>

          <button
            onClick={() => setActiveTab('casestudy')}
            style={{
              padding: '8px 16px',
              borderRadius: '8px 8px 0 0',
              fontSize: '0.85rem',
              fontWeight: activeTab === 'casestudy' ? '700' : '500',
              border: 'none',
              borderBottom: activeTab === 'casestudy' ? '2px solid #4f46e5' : '2px solid transparent',
              background: activeTab === 'casestudy' ? '#eef2ff' : 'transparent',
              color: activeTab === 'casestudy' ? '#4f46e5' : '#64748b',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease'
            }}
          >
            <Sparkles size={16} /> Case Study Minh chứng 8 Bước (Q724)
          </button>

          <button
            onClick={() => setActiveTab('comparison')}
            style={{
              padding: '8px 16px',
              borderRadius: '8px 8px 0 0',
              fontSize: '0.85rem',
              fontWeight: activeTab === 'comparison' ? '700' : '500',
              border: 'none',
              borderBottom: activeTab === 'comparison' ? '2px solid #4f46e5' : '2px solid transparent',
              background: activeTab === 'comparison' ? '#eef2ff' : 'transparent',
              color: activeTab === 'comparison' ? '#4f46e5' : '#64748b',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease'
            }}
          >
            <ShieldCheck size={16} /> Đối chiếu Cơ chế & Đánh giá Thực nghiệm
          </button>
        </div>
      </div>

      {/* TAB 1: SƠ ĐỒ LUỒNG PIPELINE TOÀN CẢNH */}
      {activeTab === 'pipeline' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          
          {/* Phase 1 vs Phase 2 High-level architecture */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.25rem' }}>
            
            {/* PHA 1 */}
            <div className="card" style={{ borderTop: '4px solid #3b82f6', padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span className="badge badge-primary" style={{ fontSize: '0.75rem' }}>
                  PHA 1: Chuẩn bị Offline (Chạy 1 lần / CSDL)
                </span>
                <span style={{ fontSize: '0.72rem', color: '#64748b' }}>Offline Step</span>
              </div>
              <h3 style={{ fontSize: '1rem', fontWeight: '700', color: '#0f172a', margin: '4px 0 8px 0' }}>
                Table Mapping & Thiết kế Conceptual Views
              </h3>
              <p style={{ fontSize: '0.825rem', color: '#475569', lineHeight: '1.5', margin: '0 0 12px 0' }}>
                Phân tích cấu trúc bảng vật lý trong SQLite, tự động gom các bảng có quan hệ khóa ngoại (1-N hoặc N-N) thành một <b>VIEW khái niệm</b> (bảng phẳng) có tiền tố <code style={{ color: '#2563eb' }}>v_*</code>.
              </p>

              <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '10px 12px', fontSize: '0.78rem' }}>
                <div style={{ fontWeight: '700', color: '#334155', marginBottom: '4px' }}>
                  🔑 Nguyên lý cốt lõi:
                </div>
                <div style={{ color: '#64748b', lineHeight: '1.45' }}>
                  • <b>Không</b> tạo bảng View thật trong file SQLite gốc để tránh tốn dung lượng và không làm thay đổi CSDL.<br />
                  • Chỉ sinh các câu lệnh <code style={{ color: '#4f46e5' }}>CREATE VIEW v_* AS SELECT ...</code> lưu dưới dạng <b>Mapping Rules (JSON)</b> dùng để tiêm vào Prompt của mô hình.
                </div>
              </div>
            </div>

            {/* PHA 2 */}
            <div className="card" style={{ borderTop: '4px solid #10b981', padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span className="badge badge-success" style={{ fontSize: '0.75rem' }}>
                  PHA 2: Suy luận Trực tuyến 2 Giai đoạn (Mỗi câu hỏi)
                </span>
                <span style={{ fontSize: '0.72rem', color: '#64748b' }}>Online Inference</span>
              </div>
              <h3 style={{ fontSize: '1rem', fontWeight: '700', color: '#0f172a', margin: '4px 0 8px 0' }}>
                Stage 1 (Dummy SQL) ➔ Stage 2 (Final SQL)
              </h3>
              <p style={{ fontSize: '0.825rem', color: '#475569', lineHeight: '1.5', margin: '0 0 12px 0' }}>
                Chia việc suy luận SQL làm 2 giai đoạn riêng biệt nhằm giảm tải nhận thức (cognitive load) của LLM khi đối mặt với nhiều bảng liên kết:
              </p>

              <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '10px 12px', fontSize: '0.78rem' }}>
                <div style={{ fontWeight: '700', color: '#065f46', marginBottom: '4px' }}>
                  ⚙️ 2 Chặng thực thi tuần tự:
                </div>
                <div style={{ color: '#166534', lineHeight: '1.45' }}>
                  • <b>Stage 1:</b> LLM viết Dummy SQL trên View ảo. Mọi trường thông tin nằm trong cùng 1 bảng phẳng ➔ <b>Số JOIN giảm về 0</b>.<br />
                  • <b>Stage 2:</b> LLM nhận Dummy SQL và quy tắc mapping của các View đã dùng để phục hồi (unroll) về các bảng vật lý thật.
                </div>
              </div>
            </div>

          </div>

          {/* Interactive Pipeline Step-by-Step Flow */}
          <div className="card" style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: '700', color: '#0f172a', margin: 0 }}>
                  Quy trình Luồng Dữ liệu Chi tiết trong V-SQL Engine
                </h3>
                <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
                  Từ câu hỏi tự nhiên đến khi thực thi thành công tập dữ liệu thật trên SQLite
                </span>
              </div>
              <span className="badge badge-neutral" style={{ fontSize: '0.72rem' }}>
                Luồng 5 Chặng Tuần Tự
              </span>
            </div>

            {/* Pipeline Visual Stepper Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
              
              {/* Step 1 */}
              <div style={{
                background: '#f8fafc',
                border: '1px solid #cbd5e1',
                borderRadius: '10px',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                position: 'relative'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ width: '22px', height: '22px', borderRadius: '50%', background: '#475569', color: '#fff', fontSize: '0.72rem', fontWeight: '700', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>1</span>
                  <span style={{ fontSize: '0.68rem', fontWeight: '700', color: '#64748b' }}>INPUT</span>
                </div>
                <div style={{ fontWeight: '700', fontSize: '0.85rem', color: '#0f172a' }}>Câu hỏi & Evidence</div>
                <div style={{ fontSize: '0.75rem', color: '#64748b', lineHeight: '1.4' }}>
                  Tiếp nhận câu hỏi tự nhiên + External Evidence từ BIRD Benchmark.
                </div>
              </div>

              {/* Step 2 */}
              <div style={{
                background: '#f0f9ff',
                border: '1px solid #bae6fd',
                borderRadius: '10px',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ width: '22px', height: '22px', borderRadius: '50%', background: '#0284c7', color: '#fff', fontSize: '0.72rem', fontWeight: '700', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>2</span>
                  <span style={{ fontSize: '0.68rem', fontWeight: '700', color: '#0369a1' }}>STAGE 1</span>
                </div>
                <div style={{ fontWeight: '700', fontSize: '0.85rem', color: '#0369a1' }}>Sinh Dummy SQL</div>
                <div style={{ fontSize: '0.75rem', color: '#475569', lineHeight: '1.4' }}>
                  LLM sinh câu truy vấn trên View ảo <code style={{ color: '#0284c7' }}>v_*</code> (Gần như 0 JOIN).
                </div>
              </div>

              {/* Step 3 */}
              <div style={{
                background: '#fdf4ff',
                border: '1px solid #f5d0fe',
                borderRadius: '10px',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ width: '22px', height: '22px', borderRadius: '50%', background: '#c026d3', color: '#fff', fontSize: '0.72rem', fontWeight: '700', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>3</span>
                  <span style={{ fontSize: '0.68rem', fontWeight: '700', color: '#a21caf' }}>MAPPING</span>
                </div>
                <div style={{ fontWeight: '700', fontSize: '0.85rem', color: '#a21caf' }}>Trích xuất Rules</div>
                <div style={{ fontSize: '0.75rem', color: '#475569', lineHeight: '1.4' }}>
                  Phân tích Dummy SQL, lọc lấy các bảng View được dùng và nạp rule định nghĩa tương ứng.
                </div>
              </div>

              {/* Step 4 */}
              <div style={{
                background: '#eef2ff',
                border: '1px solid #c7d2fe',
                borderRadius: '10px',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ width: '22px', height: '22px', borderRadius: '50%', background: '#4f46e5', color: '#fff', fontSize: '0.72rem', fontWeight: '700', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>4</span>
                  <span style={{ fontSize: '0.68rem', fontWeight: '700', color: '#4338ca' }}>STAGE 2</span>
                </div>
                <div style={{ fontWeight: '700', fontSize: '0.85rem', color: '#4338ca' }}>Unroll về Bảng thật</div>
                <div style={{ fontSize: '0.75rem', color: '#475569', lineHeight: '1.4' }}>
                  LLM thay thế View thành các bảng vật lý với các mệnh đề JOIN và ON chính xác.
                </div>
              </div>

              {/* Step 5 */}
              <div style={{
                background: '#f0fdf4',
                border: '1px solid #bbf7d0',
                borderRadius: '10px',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ width: '22px', height: '22px', borderRadius: '50%', background: '#16a34a', color: '#fff', fontSize: '0.72rem', fontWeight: '700', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>5</span>
                  <span style={{ fontSize: '0.68rem', fontWeight: '700', color: '#15803d' }}>EXECUTION</span>
                </div>
                <div style={{ fontWeight: '700', fontSize: '0.85rem', color: '#15803d' }}>Thực thi SQLite</div>
                <div style={{ fontSize: '0.75rem', color: '#475569', lineHeight: '1.4' }}>
                  Chạy Final SQL trên SQLite DB thật để lấy kết quả bản ghi và đối chiếu với Gold SQL.
                </div>
              </div>

            </div>
          </div>

        </div>
      )}

      {/* TAB 2: CASE STUDY MINH CHỨNG 8 BƯỚC */}
      {activeTab === 'casestudy' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          
          {/* Case Study Meta Strip */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            padding: '10px 16px', 
            background: '#f1f5f9', 
            borderRadius: '10px',
            border: '1px solid #cbd5e1',
            flexWrap: 'wrap',
            gap: '10px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <span className="badge badge-primary" style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
                QID #724
              </span>
              <span className="badge badge-neutral" style={{ fontSize: '0.8rem' }}>
                <Database size={12} /> superhero
              </span>
              <span className="badge badge-danger" style={{ fontSize: '0.8rem' }}>
                Challenging (Nhiều JOIN)
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.8rem' }}>
              <div>
                <span style={{ color: '#64748b' }}>Giảm JOINs: </span>
                <b style={{ color: '#0284c7' }}>0 (Stage 1)</b>
                <span style={{ color: '#64748b' }}> ➔ </span>
                <b style={{ color: '#4f46e5' }}>2 (Stage 2)</b>
              </div>
              <div style={{ width: '1px', height: '14px', background: '#cbd5e1' }} />
              <div>
                <span style={{ color: '#64748b' }}>Kết quả: </span>
                <b style={{ color: '#16a34a' }}>EX = 100% (Khớp 100% Gold)</b>
              </div>
            </div>
          </div>

          {/* 8 Steps List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {caseStudySteps.map((s, idx) => (
              <div 
                key={idx}
                style={{
                  display: 'flex',
                  gap: '14px',
                  alignItems: 'flex-start',
                  padding: '14px 16px',
                  background: idx === 3 ? '#f0f9ff' : idx === 5 ? '#eef2ff' : idx === 7 ? '#f0fdf4' : '#ffffff',
                  border: idx === 3 ? '1px solid #bae6fd' : idx === 5 ? '1px solid #c7d2fe' : idx === 7 ? '1px solid #bbf7d0' : '1px solid #e2e8f0',
                  borderRadius: '12px',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                }}
              >
                {/* Step Number Circle */}
                <div 
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    background: idx === 3 ? '#0284c7' : idx === 5 ? '#4f46e5' : idx === 7 ? '#16a34a' : '#475569',
                    color: '#ffffff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: '700',
                    fontSize: '0.85rem',
                    flexShrink: 0,
                    marginTop: '2px'
                  }}
                >
                  {s.num}
                </div>

                {/* Step Body */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px', flexWrap: 'wrap', gap: '6px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontWeight: '700', fontSize: '0.9rem', color: '#0f172a' }}>{s.title}</span>
                      <span className={`badge ${s.badgeColor}`} style={{ fontSize: '0.68rem' }}>{s.badge}</span>
                    </div>

                    {s.sql && (
                      <button
                        onClick={() => copyToClipboard(s.sql, `step_${s.num}`)}
                        className="btn btn-secondary"
                        style={{ padding: '2px 8px', fontSize: '0.72rem', height: '24px' }}
                      >
                        {copiedSection === `step_${s.num}` ? <><Check size={11} /> Đã chép</> : <><Copy size={11} /> Sao chép</>}
                      </button>
                    )}
                  </div>

                  <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '8px' }}>
                    {s.desc}
                  </div>

                  {/* Text Content */}
                  {s.type === 'text' && (
                    <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '10px 12px', fontSize: '0.85rem', fontWeight: '600', color: '#1e293b' }}>
                      "{s.content}"
                    </div>
                  )}

                  {/* Evidence Content */}
                  {s.type === 'evidence' && (
                    <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '8px', padding: '10px 12px', fontSize: '0.82rem', color: '#92400e' }}>
                      <b>💡 Evidence: </b>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{s.content}</span>
                    </div>
                  )}

                  {/* Schema Content */}
                  {s.type === 'schema' && (
                    <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '8px', padding: '10px 12px', fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: '#334155' }}>
                      <span style={{ color: '#4f46e5', fontWeight: '700' }}>v_superhero</span> (superhero_name, full_name, eye_colour, hair_colour, skin_colour, publisher_name, alignment, gender, height_cm, weight_kg)
                    </div>
                  )}

                  {/* SQL Code Block */}
                  {s.type === 'sql' && (
                    <pre style={{
                      background: idx === 3 ? '#ffffff' : idx === 5 ? '#ffffff' : '#f8fafc',
                      border: '1px solid #cbd5e1',
                      borderRadius: '8px',
                      padding: '12px',
                      fontSize: '0.8rem',
                      color: '#0f172a',
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      lineHeight: '1.45',
                      fontFamily: 'var(--font-mono)'
                    }}>
                      {formatSql(s.sql)}
                    </pre>
                  )}

                  {/* Evaluation Grid */}
                  {s.type === 'eval' && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '8px', marginTop: '6px' }}>
                      {s.stats.map((st, i) => (
                        <div key={i} style={{ background: '#ffffff', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '8px 12px' }}>
                          <div style={{ fontSize: '0.72rem', color: '#64748b' }}>{st.label}</div>
                          <div style={{ fontSize: '0.825rem', fontWeight: '700', color: st.color, marginTop: '2px' }}>
                            {st.value}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                </div>
              </div>
            ))}
          </div>

        </div>
      )}

      {/* TAB 3: ĐỐI CHIẾU CƠ CHẾ & ĐÁNH GIÁ THỰC NGHIỆM */}
      {activeTab === 'comparison' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          
          {/* Comparison Cards: Direct vs V-SQL */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.25rem' }}>
            
            {/* Direct Baseline Column */}
            <div className="card" style={{ borderTop: '4px solid #64748b', padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span className="badge badge-neutral" style={{ fontSize: '0.75rem' }}>
                  Direct Baseline (1-Stage)
                </span>
                <span style={{ fontSize: '0.72rem', color: '#64748b' }}>Mô hình truyền thống</span>
              </div>
              <h3 style={{ fontSize: '0.95rem', fontWeight: '700', color: '#0f172a', margin: '4px 0 10px 0' }}>
                Sinh trực tiếp trên toàn bộ Bảng gốc
              </h3>
              
              <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.8rem', color: '#475569', lineHeight: '1.5', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <li><b>Cơ chế:</b> Nạp toàn bộ schema SQLite gốc (bảng thật, khóa chính, khóa ngoại) vào 1 prompt duy nhất.</li>
                <li><b>Ưu điểm:</b> Tốc độ nhanh (độ trễ ~27.5s trên local GPU), tiết kiệm số lượt gọi API LLM (chỉ 1 lần sinh).</li>
                <li><b>Nhược điểm cốt tử:</b> LLM phải đồng thời hiểu ngữ nghĩa câu hỏi và nhớ chính xác mọi khóa ngoại ➔ <b>Dễ bị Foreign-Key Hallucination</b> khi có từ 2-3 bảng JOIN trở lên.</li>
                <li><b>Độ chính xác trên BIRD:</b> EX đạt <b>47.4%</b> trên Qwen2.5-Coder-7B (giảm mạnh ở mức Challenging: 27.5%).</li>
              </ul>
            </div>

            {/* V-SQL Column */}
            <div className="card" style={{ borderTop: '4px solid #4f46e5', padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span className="badge badge-primary" style={{ fontSize: '0.75rem' }}>
                  V-SQL Pipeline (2-Stage)
                </span>
                <span style={{ fontSize: '0.72rem', color: '#4f46e5', fontWeight: '700' }}>Đề xuất Paper</span>
              </div>
              <h3 style={{ fontSize: '0.95rem', fontWeight: '700', color: '#0f172a', margin: '4px 0 10px 0' }}>
                Chia để trị qua Lớp View Khái niệm
              </h3>
              
              <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.8rem', color: '#475569', lineHeight: '1.5', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <li><b>Cơ chế:</b> Tách làm 2 chặng: Stage 1 làm việc trên View phẳng (0 JOIN) ➔ Stage 2 chỉ unroll các View xuất hiện trong câu lệnh.</li>
                <li><b>Ưu điểm lớn nhất:</b> <b>Triệt tiêu nhầm lẫn khóa ngoại</b>. Các câu hỏi khó với nhiều JOIN (như Q724) được giải quyết chuẩn xác nhờ unroll từng View một cách có cấu trúc.</li>
                <li><b>Hiện tượng View Leak (Phát hiện thực nghiệm):</b> Mô hình nhỏ 7B gặp 21 câu sót tiền tố <code>v_*</code> ở Stage 2 do unroll chưa triệt để (điểm khác biệt quan trọng so với GPT-4 trong bài báo).</li>
                <li><b>Đánh đổi (Trade-off):</b> Thời gian suy luận gấp đôi (~64.9s) và lượng token xử lý tăng do phải gọi LLM qua 2 chặng.</li>
              </ul>
            </div>

          </div>

          {/* 3 Academic Takeaways / Insights */}
          <div className="card" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: '700', color: '#0f172a', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Cpu size={18} color="#06b6d4" />
              <span>3 Phát Hiện Thực Nghiệm Đắt Giá Cho Báo Cáo &amp; Đồ Án</span>
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
              
              <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '12px' }}>
                <div style={{ fontWeight: '700', fontSize: '0.85rem', color: '#0f172a', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ color: '#2563eb' }}>1.</span> Khả năng triệt tiêu JOIN
                </div>
                <p style={{ margin: 0, fontSize: '0.78rem', color: '#64748b', lineHeight: '1.45' }}>
                  V-SQL giảm trung bình <b>56.2%</b> số lượng JOINs ở Stage 1 trên toàn bộ 500 câu. Đặc biệt ở <code style={{ color: '#0f172a' }}>california_schools</code> (giảm <b>92.5%</b>) và <code style={{ color: '#0f172a' }}>superhero</code> (giảm <b>62.5%</b>), chứng minh tính hiệu quả của tầng View trong việc làm phẳng cấu trúc quan hệ.
                </p>
              </div>

              <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '10px', padding: '12px' }}>
                <div style={{ fontWeight: '700', fontSize: '0.85rem', color: '#991b1b', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <AlertTriangle size={15} color="#dc2626" />
                  <span>2. Vấn đề View Leak ở SLM (7B)</span>
                </div>
                <p style={{ margin: 0, fontSize: '0.78rem', color: '#7f1d1d', lineHeight: '1.45' }}>
                  Paper gốc dùng GPT-4 không ghi nhận View Leak, nhưng với mô hình local <b>7B</b>, có <b>21/500 câu</b> bị rò rỉ <code>v_*</code> ở Stage 2. Đây là minh chứng rõ rệt cho thấy mô hình nhỏ cần bổ sung quy tắc cấm <code>v_*</code> rõ ràng hơn trong prompt Stage 2.
                </p>
              </div>

              <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '10px', padding: '12px' }}>
                <div style={{ fontWeight: '700', fontSize: '0.85rem', color: '#166534', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <CheckCircle2 size={15} color="#16a34a" />
                  <span>3. Khuyến nghị Ứng dụng Thực tế</span>
                </div>
                <p style={{ margin: 0, fontSize: '0.78rem', color: '#15803d', lineHeight: '1.45' }}>
                  Nên sử dụng <b>Cơ chế Định tuyến Thông minh (Hybrid Routing)</b>: với câu hỏi Simple (0-1 JOIN), dùng Direct Baseline để đạt tốc độ cao; với câu hỏi Challenging (từ 2 JOIN trở lên), kích hoạt V-SQL 2-Stage để đảm bảo độ chính xác tuyệt đối.
                </p>
              </div>

            </div>
          </div>

        </div>
      )}

    </div>
  );
}
