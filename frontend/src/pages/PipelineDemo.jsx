import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Check, Circle, Cpu, Database, FileInput, Link2, Loader2, Play, Sparkles, Square, Table2, Target, X } from 'lucide-react';
import { formatSql } from '../utils/sqlFormatter';
import './pipeline.css';

const LANES = {
  direct: {
    label: 'Direct',
    color: 'var(--series-direct)',
    stations: [
      { id: 'input', col: 1, name: 'Đầu vào', icon: FileInput },
      { id: 'mapping', col: 2, name: 'Schema bảng gốc', icon: Database },
      { id: 'direct', col: 3, span: 4, name: 'Sinh SQL', icon: Sparkles, llm: true },
      { id: 'execute', col: 7, name: 'Chạy SQL', icon: Cpu },
      { id: 'score', col: 8, name: 'Chấm điểm', icon: Target },
    ],
  },
  vsql: {
    label: 'V-SQL',
    color: 'var(--series-vsql)',
    stations: [
      { id: 'input', col: 1, name: 'Đầu vào', icon: FileInput },
      { id: 'mapping', col: 2, name: 'Schema view', icon: Table2 },
      { id: 'stage1', col: 3, name: 'Stage 1: Dummy SQL', icon: Sparkles, llm: true },
      { id: 'stage1_exec', col: 4, name: 'Thử Dummy SQL', icon: Cpu },
      { id: 'linking', col: 5, name: 'Schema Linking', icon: Link2 },
      { id: 'stage2', col: 6, name: 'Stage 2: Tái dựng SQL', icon: Sparkles, llm: true },
      { id: 'execute', col: 7, name: 'Chạy SQL', icon: Cpu },
      { id: 'score', col: 8, name: 'Chấm điểm', icon: Target },
    ],
  },
};

const STEP_DOCS = {
  input: 'Lấy câu hỏi và evidence từ BIRD mini-dev, rồi ghép lại thành câu hỏi đưa vào prompt.',
  mapping: {
    direct: 'Đọc DDL của các bảng trong database. Nếu chọn schema có mô tả, thêm mô tả cột từ tài liệu của BIRD.',
    vsql: 'Đọc bộ view đã chọn và trình bày tên view, cột, kiểu dữ liệu, mô tả. Stage 1 chỉ thấy phần này, không thấy bảng gốc.',
  },
  direct: 'Model nhận toàn bộ schema bảng gốc và viết SQL trong một lần gọi. Phải tự nhận ra cần JOIN bảng nào.',
  stage1: 'Lần gọi model thứ nhất. Model viết Dummy SQL trên view nên ít phải nghĩ về JOIN, nhưng chỉ dùng được những gì view có.',
  stage1_exec: 'Bước chẩn đoán, không có trong paper: chạy Dummy SQL trên view tạm để biết Stage 1 đúng hay sai. Không ghi gì vào database.',
  linking: 'Không gọi model. Tìm view mà Dummy SQL đã dùng, rồi chỉ giữ định nghĩa của các view đó và các bảng gốc liên quan.',
  stage2: 'Lần gọi model thứ hai. Model đổi Dummy SQL thành SQL trên bảng gốc, thêm lại JOIN theo định nghĩa view.',
  execute: 'Chạy SQL cuối trên kết nối chỉ đọc tới database gốc, giới hạn 30 giây.',
  score: 'Execution Accuracy: đúng khi tập dòng của SQL cuối bằng tập dòng của gold SQL. Không xét thứ tự dòng.',
};

const SQL_KEYWORDS = /\b(SELECT|FROM|WHERE|LEFT|RIGHT|INNER|OUTER|CROSS|JOIN|ON|GROUP BY|ORDER BY|HAVING|LIMIT|UNION|AND|OR|NOT|IN|AS|DISTINCT|COUNT|SUM|AVG|MIN|MAX|CASE|WHEN|THEN|ELSE|END|CAST|CREATE VIEW|CREATE TABLE|PRIMARY KEY|FOREIGN KEY|REFERENCES|DESC|ASC|BETWEEN|LIKE|IS|NULL)\b/g;

const formatCost = (usd) => (usd === 0 ? '$0' : usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`);

function formatDuration(seconds) {
  const s = Math.round(seconds);
  if (s < 60) return `${s} giây`;
  if (s < 3600) return `${Math.round(s / 60)} phút`;
  return `${(s / 3600).toFixed(1)} giờ`;
}

function SqlText({ text }) {
  const parts = text.split(SQL_KEYWORDS);
  return parts.map((part, i) => (i % 2 ? <span className="pd-kw" key={i}>{part}</span> : part));
}

function CodeBlock({ value, kind }) {
  const [copied, setCopied] = useState(false);
  const text = useMemo(() => {
    const raw = String(value ?? '');
    return kind === 'sql' && /^\s*(SELECT|WITH)\b/i.test(raw) ? formatSql(raw) : raw;
  }, [value, kind]);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };
  let body = text;
  if (kind === 'sql') body = <SqlText text={text} />;
  if (kind === 'prompt') {
    body = text.split('\n').map((line, i) => (
      <React.Fragment key={i}>
        {line.startsWith('# ') ? <span className="pd-prompt-head">{line}</span> : line}
        {'\n'}
      </React.Fragment>
    ));
  }
  return (
    <div className="pd-item">
      <button type="button" className="pd-copy" style={{ justifySelf: 'end' }} onClick={copy}>{copied ? 'Đã chép' : 'Chép'}</button>
      <pre className="pd-code" tabIndex={0}>{body}</pre>
    </div>
  );
}

function RowsTable({ value }) {
  if (value.error) return <div className="pd-alert">{value.error}</div>;
  if (!value.columns.length) return <div className="pd-empty-note">Câu lệnh không trả về cột nào.</div>;
  return (
    <div className="pd-item">
      <div className="pd-tablewrap" tabIndex={0}>
        <table className="pd-table">
          <thead><tr>{value.columns.map((c, i) => <th key={i} scope="col">{c}</th>)}</tr></thead>
          <tbody>
            {value.rows.map((row, r) => (
              <tr key={r}>{row.map((v, c) => <td key={c} title={String(v)}>{v === null ? 'NULL' : String(v)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
      <span className="pd-hint">
        {value.total_rows > value.rows.length ? `Hiện ${value.rows.length} trong ${value.total_rows} dòng` : `${value.total_rows} dòng`}, {value.distinct_rows} dòng khác nhau, chạy {value.seconds}s
      </span>
    </div>
  );
}

const CLASS_LABELS = {
  correct: 'đúng',
  wrong_values: 'đúng số cột, sai giá trị',
  wrong_column_count: 'sai số cột',
  'no such column': 'cột không tồn tại',
  'no such table': 'bảng không tồn tại',
  'no such function': 'hàm không tồn tại',
  syntax: 'lỗi cú pháp',
  other_error: 'lỗi khi chạy',
  timeout: 'quá 30 giây',
  too_many_rows: 'quá nhiều dòng',
};

function Verdict({ value }) {
  return (
    <div className={`pd-verdict ${value.ok ? 'ok' : 'bad'}`}>
      <strong>{value.ok ? <Check size={17} /> : <X size={17} />}{value.ok ? 'Khớp gold' : `Không khớp: ${CLASS_LABELS[value.class] || value.class}`}</strong>
      {value.error && <span className="pd-hint">{value.error}</span>}
      <div className="pd-sets">
        <span>Gold: {value.gold_rows} dòng</span>
        <span>Dự đoán: {value.pred_rows} dòng</span>
        <span>Trùng nhau: {value.matching}</span>
        <span>Chỉ có ở dự đoán: {value.only_pred}</span>
        <span>Chỉ có ở gold: {value.only_gold}</span>
      </div>
    </div>
  );
}

function StepItem({ item }) {
  let content;
  switch (item.type) {
    case 'sql': content = <CodeBlock value={item.value} kind="sql" />; break;
    case 'code': content = <CodeBlock value={item.value} kind="code" />; break;
    case 'prompt': content = <CodeBlock value={item.value} kind="prompt" />; break;
    case 'rows': content = <RowsTable value={item.value} />; break;
    case 'verdict': content = <Verdict value={item.value} />; break;
    case 'chips':
      content = <div className="pd-chips">{item.value.map((c) => <span className="badge badge-neutral" key={c}>{c}</span>)}</div>;
      break;
    case 'error': content = <div className="pd-alert">{item.value}</div>; break;
    case 'warning': content = <div className="pd-alert warn">{item.value}</div>; break;
    default: content = <div className="pd-item-text">{String(item.value)}</div>;
  }
  return (
    <div className="pd-item">
      <div className="pd-item-label">{item.label}</div>
      {content}
    </div>
  );
}

function stationResult(step) {
  if (step?.id === 'score' && step.status === 'done' && step.meta) return step.meta.ok ? 'right' : 'wrong';
  return null;
}

function Station({ station, step, lane, selected, onSelect }) {
  const status = step?.status || 'pending';
  const result = stationResult(step);
  const Icon = station.icon;
  let glyph = station.llm ? <Square size={12} /> : <Circle size={10} />;
  if (status === 'running') glyph = <Loader2 size={16} className="pd-spin" />;
  else if (status === 'error') glyph = <X size={16} />;
  else if (result === 'right') glyph = <Check size={16} />;
  else if (result === 'wrong') glyph = <X size={16} />;
  else if (status === 'done') glyph = <Icon size={15} />;
  const stateName = { pending: 'chưa chạy', running: 'đang chạy', done: 'xong', error: 'có lỗi' }[status];
  return (
    <button
      type="button"
      className={`pd-station ${station.llm ? 'llm' : ''} ${status} ${result || ''}`}
      style={{ gridColumn: `${station.col + 1} / span ${station.span || 1}`, '--lane': lane.color }}
      aria-pressed={selected}
      aria-label={`${lane.label}, ${station.name}, ${stateName}`}
      onClick={onSelect}
    >
      <span className="pd-node">{glyph}</span>
      <span className="pd-station-name">{station.name}</span>
      <span className="pd-station-sum">{step?.summary || ''}</span>
    </button>
  );
}

function Lane({ framework, steps, selected, onSelect }) {
  const lane = LANES[framework];
  const finished = lane.stations.filter((s) => steps?.[s.id] && steps[s.id].status !== 'running');
  const last = finished.length ? finished[finished.length - 1] : null;
  const progress = last ? ((last.col - 1) / 7) * 100 : 0;
  return (
    <div className="pd-lane" style={{ '--lane': lane.color }}>
      <div className="pd-lane-name"><span className="pd-dot" style={{ background: lane.color }} />{lane.label}</div>
      <div className="pd-lane-rail"><i style={{ width: `${progress}%` }} /></div>
      {lane.stations.map((station) => (
        <Station
          key={station.id}
          station={station}
          lane={lane}
          step={steps?.[station.id]}
          selected={selected?.framework === framework && selected?.id === station.id}
          onSelect={() => onSelect({ framework, id: station.id })}
        />
      ))}
    </div>
  );
}

function Inspector({ selected, steps, loading }) {
  if (!selected) return null;
  const lane = LANES[selected.framework];
  const station = lane.stations.find((s) => s.id === selected.id);
  if (!station) return null;
  const step = steps?.[selected.framework]?.[selected.id];
  const doc = STEP_DOCS[selected.id];
  const meta = step?.meta || {};
  const chips = [];
  if (meta.latency_s !== undefined) chips.push(`${meta.latency_s.toFixed(2)}s`);
  if (meta.prompt_tokens) chips.push(`${meta.prompt_tokens} token vào`);
  if (meta.completion_tokens) chips.push(`${meta.completion_tokens} token ra`);
  if (meta.cost_usd) chips.push(formatCost(meta.cost_usd));
  if (meta.joins !== undefined) chips.push(`${meta.joins} JOIN`);
  if (meta.views !== undefined) chips.push(`${meta.views} view, ${meta.view_columns} cột`);
  return (
    <div className="pd-inspector">
      <div className="pd-inspector-head">
        <h3>
          <span className="pd-dot" style={{ background: lane.color }} />
          {lane.label}: {step?.title || station.name}
          {chips.map((c) => <span className="badge badge-neutral" key={c}>{c}</span>)}
        </h3>
        <p>{typeof doc === 'string' ? doc : doc[selected.framework]}</p>
      </div>
      {step && step.inputs ? (
        <div className="pd-io">
          <section>
            <h4>Đầu vào</h4>
            {step.inputs.map((item, i) => <StepItem item={item} key={i} />)}
            {!step.inputs.length && <div className="pd-empty-note">Không có.</div>}
          </section>
          <section>
            <h4>Đầu ra</h4>
            {step.outputs.map((item, i) => <StepItem item={item} key={i} />)}
            {!step.outputs.length && <div className="pd-empty-note">{step.status === 'running' ? 'Đang chạy bước này.' : 'Không có.'}</div>}
          </section>
        </div>
      ) : (
        <div style={{ padding: '0 1.1rem 1rem' }} className="pd-empty-note">
          {loading ? 'Đang tải chi tiết.' : 'Bước này chưa chạy. Chọn câu hỏi và bấm chạy để xem đầu vào và đầu ra thật.'}
        </div>
      )}
    </div>
  );
}

function ScoreStrip({ summary, status, message, config, onCancel }) {
  const fw = summary.frameworks;
  const direct = fw.direct;
  const vsql = fw.vsql;
  const done = Object.values(fw).reduce((acc, f) => acc + f.done, 0);
  const total = summary.total_questions * Object.keys(fw).length;
  const running = status === 'running' || status === 'queued';
  const statusLabel = { queued: 'Đang chuẩn bị', running: 'Đang chạy', done: 'Hoàn tất', cancelled: 'Đã dừng', budget_stopped: 'Dừng do chạm hạn mức', error: 'Dừng do lỗi' }[status];
  const single = summary.total_questions === 1;
  const scoreText = (cell, ex, correct, words) => {
    if (!cell.done) return '...';
    return single ? (correct ? words[0] : words[1]) : `${ex.toFixed(1)}%`;
  };
  const tile = (name, color, value, sub) => (
    <div className="pd-score" key={name}>
      <span className="pd-score-name"><span className="pd-dot" style={{ background: color }} />{name}</span>
      <span className="pd-score-val">{value}</span>
      <span className="pd-score-sub">{sub}</span>
    </div>
  );
  return (
    <div className="pd-panel">
      <div className="pd-scores">
        {direct && tile('Direct', 'var(--series-direct)', scoreText(direct, direct.ex, direct.correct, ['Đúng', 'Sai']), single ? `${direct.avg_latency_s}s gọi model` : `${direct.correct}/${direct.done} đúng, trung bình ${direct.avg_latency_s}s`)}
        {vsql && tile('Stage 1', 'var(--series-stage1)', scoreText(vsql, vsql.stage1_ex, vsql.stage1_correct, ['Khớp gold', 'Chưa khớp']), single ? 'Dummy SQL trên view' : `${vsql.stage1_correct}/${vsql.done} Dummy SQL khớp gold`)}
        {vsql && tile('V-SQL', 'var(--series-vsql)', scoreText(vsql, vsql.ex, vsql.correct, ['Đúng', 'Sai']), single ? `${vsql.avg_latency_s}s gọi model` : `${vsql.correct}/${vsql.done} đúng, trung bình ${vsql.avg_latency_s}s`)}
        {summary.pairs && summary.pairs.n > 0 && (
          <div className="pd-score">
            <span className="pd-score-name">Cùng câu hỏi</span>
            <span className="pd-score-val" style={{ fontSize: '1.1rem' }}>{summary.pairs.direct_only} và {summary.pairs.vsql_only}</span>
            <span className="pd-score-sub">Chỉ Direct đúng và chỉ V-SQL đúng{summary.pairs.n > 20 ? `, p = ${summary.pairs.p < 0.001 ? summary.pairs.p.toExponential(1) : summary.pairs.p.toFixed(3)}` : ''}</span>
          </div>
        )}
        <div className="pd-run-state">
          <b>{statusLabel}</b>
          <div className="pd-progress" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done}><i style={{ width: `${total ? (done / total) * 100 : 0}%` }} /></div>
          <span>{done}/{total} lượt, {formatDuration(summary.elapsed_s || 0)}{config.source === 'live' ? `, ${formatCost(summary.cost_usd)}` : ', không tốn tiền'}</span>
          {running && <button type="button" className="btn btn-secondary" style={{ padding: '0.3rem 0.7rem', fontSize: '0.8rem' }} onClick={onCancel}>Dừng</button>}
        </div>
      </div>
      {message && status !== 'done' && <div className="pd-alert" style={{ margin: '0 1.1rem 1rem' }}>{message}</div>}
    </div>
  );
}

const LEVEL_LABELS = { simple: 'Dễ', moderate: 'Trung bình', challenging: 'Khó' };

function Breakdown({ summary, frameworks }) {
  const pct = (cell) => (cell && cell.done ? `${((cell.correct / cell.done) * 100).toFixed(1)}% (${cell.correct}/${cell.done})` : 'Chưa có');
  const dbs = Object.keys(summary.by_db).sort();
  return (
    <div className="pd-panel">
      <div className="pd-panel-head"><h2>Kết quả theo nhóm</h2></div>
      <div style={{ overflowX: 'auto' }}>
        <table className="pd-breakdown">
          <thead>
            <tr>
              <th scope="col">Nhóm</th>
              {frameworks.map((f) => <th scope="col" key={f}>{LANES[f].label}</th>)}
            </tr>
          </thead>
          <tbody>
            {Object.entries(LEVEL_LABELS).map(([level, label]) => (
              <tr key={level}><td>{label}</td>{frameworks.map((f) => <td key={f}>{pct(summary.by_difficulty[level]?.[f])}</td>)}</tr>
            ))}
            {dbs.map((db) => (
              <tr key={db}><td>{db}</td>{frameworks.map((f) => <td key={f}>{pct(summary.by_db[db]?.[f])}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const OUTCOME_FILTERS = [
  { id: 'all', label: 'Tất cả' },
  { id: 'direct_only', label: 'Chỉ Direct đúng' },
  { id: 'vsql_only', label: 'Chỉ V-SQL đúng' },
  { id: 'both', label: 'Cả hai đúng' },
  { id: 'neither', label: 'Cả hai sai' },
];

function QuestionList({ questions, results, focus, onFocus, frameworks }) {
  const [filter, setFilter] = useState('all');
  const paired = frameworks.length === 2;
  const shown = questions.filter((q) => {
    if (filter === 'all' || !paired) return true;
    const r = results[q.question_id];
    if (!r?.direct || !r?.vsql) return false;
    if (filter === 'direct_only') return r.direct.ok && !r.vsql.ok;
    if (filter === 'vsql_only') return r.vsql.ok && !r.direct.ok;
    if (filter === 'both') return r.direct.ok && r.vsql.ok;
    return !r.direct.ok && !r.vsql.ok;
  });
  const mini = (label, record) => (
    <span className={`pd-mini ${record ? (record.ok ? 'ok' : 'bad') : ''}`} title={record ? `${label}: ${record.ok ? 'đúng' : 'sai'}` : `${label}: chưa chạy`}>
      {label[0]}{record ? (record.ok ? '✓' : '✗') : ''}
    </span>
  );
  return (
    <div className="pd-panel" style={{ alignSelf: 'start' }}>
      <div className="pd-panel-head"><h2>{shown.length} câu hỏi</h2></div>
      {paired && (
        <div className="pd-filter">
          <select className="pd-select" aria-label="Lọc theo kết quả" value={filter} onChange={(e) => setFilter(e.target.value)}>
            {OUTCOME_FILTERS.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        </div>
      )}
      <div className="pd-qlist">
        {shown.map((q) => (
          <button type="button" className="pd-qitem" key={q.question_id} aria-current={focus === q.question_id} onClick={() => onFocus(q.question_id)}>
            <span className="pd-qitem-text">{q.question}</span>
            <span className="pd-verdicts">
              {frameworks.map((f) => <React.Fragment key={f}>{mini(LANES[f].label, results[q.question_id]?.[f])}</React.Fragment>)}
            </span>
            <span className="pd-qitem-meta">Câu {q.question_id}, {q.db_id}, {LEVEL_LABELS[q.difficulty]}</span>
          </button>
        ))}
        {!shown.length && <div className="pd-empty-note" style={{ padding: '0.8rem' }}>Không có câu nào trong nhóm này.</div>}
      </div>
    </div>
  );
}

const QUESTION_MODES = [
  { id: 'one', label: 'Một câu' },
  { id: 'many', label: 'Nhiều câu' },
  { id: 'random', label: 'n câu ngẫu nhiên' },
  { id: 'all', label: 'Toàn bộ' },
];

const SPEEDS = [
  { id: 1.2, label: 'Chậm, để giải thích' },
  { id: 0.5, label: 'Vừa' },
  { id: 0, label: 'Nhanh nhất' },
];

function Settings({ options, runs, form, setForm, onStart, busy, error }) {
  const [questions, setQuestions] = useState([]);
  const [estimate, setEstimate] = useState(null);
  const set = (patch) => setForm((prev) => ({ ...prev, ...patch }));
  const replay = form.source === 'replay';
  const replayRuns = runs.filter((r) => r.replayable);
  const replayEntry = replayRuns.find((r) => r.key === form.replay_run);

  useEffect(() => {
    const params = new URLSearchParams({ limit: '500' });
    if (form.db !== 'all') params.set('db', form.db);
    if (form.difficulty !== 'all') params.set('difficulty', form.difficulty);
    if (form.search) params.set('search', form.search);
    let active = true;
    fetch(`/api/pipeline/questions?${params}`).then((r) => r.json()).then((data) => active && setQuestions(data.questions || [])).catch(() => {});
    return () => { active = false; };
  }, [form.db, form.difficulty, form.search]);

  const request = useMemo(() => buildRequest(form), [form]);
  const requestKey = JSON.stringify(request);
  useEffect(() => {
    if (replay || !form.frameworks.length) { setEstimate(null); return undefined; }
    let active = true;
    fetch('/api/pipeline/estimate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: requestKey })
      .then((r) => (r.ok ? r.json() : null)).then((data) => active && setEstimate(data)).catch(() => {});
    return () => { active = false; };
  }, [requestKey, replay, form.frameworks.length]);

  const model = options.models.find((m) => m.id === form.model);
  const chosen = form.ids.length;
  const needsChoice = (form.questionMode === 'one' || form.questionMode === 'many') && !chosen;
  const unavailable = !replay && model && !model.available;
  const overBudget = estimate && !replay && estimate.cost_usd > form.budget_usd;
  const pick = (id) => {
    if (form.questionMode === 'one') set({ ids: [id] });
    else set({ ids: form.ids.includes(id) ? form.ids.filter((x) => x !== id) : [...form.ids, id] });
  };
  const toggleFramework = (id) => set({ frameworks: form.frameworks.includes(id) ? form.frameworks.filter((x) => x !== id) : [...form.frameworks, id] });
  const canStart = !busy && form.frameworks.length && !needsChoice && !unavailable && (!replay || form.replay_run);
  const count = estimate?.questions;

  return (
    <div className="pd-panel">
      <div className="pd-panel-head">
        <h2>Cấu hình lần chạy</h2>
        <div className="pd-segment" role="group" aria-label="Nguồn kết quả">
          <button type="button" aria-pressed={!replay} onClick={() => set({ source: 'live' })}>Gọi model thật</button>
          <button type="button" aria-pressed={replay} onClick={() => set({ source: 'replay' })}>Phát lại kết quả đã lưu</button>
        </div>
      </div>
      <div className="pd-panel-body">
        <div className="pd-settings">
          {replay ? (
            <div className="pd-field">
              <label htmlFor="pd-replay">Lần chạy đã lưu</label>
              <select id="pd-replay" className="pd-select" value={form.replay_run || ''} onChange={(e) => set({ replay_run: e.target.value })}>
                <option value="" disabled>Chọn một lần chạy</option>
                {replayRuns.map((r) => <option key={r.key} value={r.key}>{r.step}. {r.title} ({r.n} câu)</option>)}
              </select>
              <span className="pd-hint">{replayEntry ? `${replayEntry.model}, bộ view ${replayEntry.view_mode}, schema ${replayEntry.schema_mode === 'described' ? 'có mô tả' : 'chỉ tên cột'}. Prompt và điểm được tính lại thật, chỉ câu trả lời của model lấy từ kết quả đã lưu.` : 'Không gọi model nên không tốn tiền và không cần mạng.'}</span>
            </div>
          ) : (
            <>
              <div className="pd-field">
                <label htmlFor="pd-model">Model</label>
                <select id="pd-model" className="pd-select" value={form.model} onChange={(e) => set({ model: e.target.value })}>
                  {options.models.map((m) => <option key={m.id} value={m.id} disabled={!m.available}>{m.label}{m.available ? '' : ` (${m.unavailable_reason})`}</option>)}
                </select>
                <span className="pd-hint">{model?.note}</span>
              </div>
              <div className="pd-field">
                <label htmlFor="pd-view">Bộ view cho V-SQL</label>
                <select id="pd-view" className="pd-select" value={form.view_mode} onChange={(e) => set({ view_mode: e.target.value })}>
                  {options.view_modes.map((v) => <option key={v.id} value={v.id}>{v.label}</option>)}
                </select>
                <span className="pd-hint">{options.view_modes.find((v) => v.id === form.view_mode)?.description}</span>
              </div>
              <div className="pd-field">
                <label htmlFor="pd-schema">Schema trong prompt</label>
                <select id="pd-schema" className="pd-select" value={form.schema_mode} onChange={(e) => set({ schema_mode: e.target.value })}>
                  {options.schema_modes.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
                <span className="pd-hint">{options.schema_modes.find((s) => s.id === form.schema_mode)?.description}</span>
              </div>
              <div className="pd-field">
                <label htmlFor="pd-budget">Hạn mức cho lần chạy này (USD)</label>
                <input id="pd-budget" className="pd-input" type="number" min="0.01" step="0.05" max={options.budget.max} value={form.budget_usd} onChange={(e) => set({ budget_usd: Number(e.target.value) })} />
                <span className="pd-hint">Tự dừng khi chạm mức này, tối đa ${options.budget.max}.</span>
              </div>
            </>
          )}
          <div className="pd-field">
            <span className="pd-label">Framework</span>
            <div style={{ display: 'flex', gap: '1rem', paddingTop: 4 }}>
              {options.frameworks.map((f) => (
                <label className="pd-check" key={f.id} title={f.description}>
                  <input type="checkbox" checked={form.frameworks.includes(f.id)} onChange={() => toggleFramework(f.id)} />
                  {f.label}
                </label>
              ))}
            </div>
            <span className="pd-hint">Chọn cả hai để so sánh trên cùng câu hỏi.</span>
          </div>
          {replay && (
            <div className="pd-field">
              <label htmlFor="pd-speed">Tốc độ phát lại</label>
              <select id="pd-speed" className="pd-select" value={form.step_delay_s} onChange={(e) => set({ step_delay_s: Number(e.target.value) })}>
                {SPEEDS.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
              </select>
            </div>
          )}
        </div>

        <div className="pd-field" style={{ marginTop: '1.1rem' }}>
          <span className="pd-label">Câu hỏi</span>
          <div className="pd-segment" role="group" aria-label="Cách chọn câu hỏi" style={{ justifySelf: 'start' }}>
            {QUESTION_MODES.map((m) => (
              <button type="button" key={m.id} aria-pressed={form.questionMode === m.id} onClick={() => set({ questionMode: m.id, ids: m.id === 'one' ? form.ids.slice(0, 1) : form.ids })}>{m.label}</button>
            ))}
          </div>
        </div>

        {form.questionMode !== 'all' && (
          <div className="pd-settings" style={{ marginTop: '0.75rem' }}>
            <div className="pd-field">
              <label htmlFor="pd-db">Database</label>
              <select id="pd-db" className="pd-select" value={form.db} onChange={(e) => set({ db: e.target.value })}>
                <option value="all">Tất cả (500 câu)</option>
                {options.databases.map((d) => <option key={d.db_id} value={d.db_id}>{d.db_id} ({d.count} câu)</option>)}
              </select>
            </div>
            <div className="pd-field">
              <label htmlFor="pd-diff">Độ khó</label>
              <select id="pd-diff" className="pd-select" value={form.difficulty} onChange={(e) => set({ difficulty: e.target.value })}>
                <option value="all">Tất cả</option>
                {options.difficulties.map((d) => <option key={d.id} value={d.id}>{LEVEL_LABELS[d.id]} ({d.count} câu)</option>)}
              </select>
            </div>
            {form.questionMode === 'random' ? (
              <>
                <div className="pd-field">
                  <label htmlFor="pd-n">Số câu (n)</label>
                  <input id="pd-n" className="pd-input" type="number" min="1" max="500" value={form.limit} onChange={(e) => set({ limit: Number(e.target.value) })} />
                </div>
                <div className="pd-field">
                  <label htmlFor="pd-seed">Seed</label>
                  <input id="pd-seed" className="pd-input" type="number" value={form.seed} onChange={(e) => set({ seed: Number(e.target.value) })} />
                  <span className="pd-hint">Cùng seed sẽ chọn lại đúng các câu đó.</span>
                </div>
              </>
            ) : (
              <div className="pd-field">
                <label htmlFor="pd-search">Tìm trong câu hỏi</label>
                <input id="pd-search" className="pd-input" type="search" value={form.search} placeholder="Ví dụ: superhero" onChange={(e) => set({ search: e.target.value })} />
              </div>
            )}
          </div>
        )}

        {(form.questionMode === 'one' || form.questionMode === 'many') && (
          <>
            <div className="pd-picker">
              {questions.map((q) => (
                <button type="button" key={q.question_id} className="pd-pick" aria-pressed={form.ids.includes(q.question_id)} onClick={() => pick(q.question_id)}>
                  <span aria-hidden="true">{form.ids.includes(q.question_id) ? <Check size={14} /> : ''}</span>
                  <small>Câu {q.question_id}</small>
                  <span>{q.question}</span>
                  <small>{q.db_id}, {LEVEL_LABELS[q.difficulty]}</small>
                </button>
              ))}
              {!questions.length && <div className="pd-empty-note" style={{ padding: '0.7rem' }}>Không có câu nào khớp bộ lọc. Hãy xóa bớt điều kiện.</div>}
            </div>
            <span className="pd-hint" style={{ marginTop: 4, display: 'block' }}>
              {form.questionMode === 'many' ? `Đã chọn ${chosen} câu. Bấm lại để bỏ chọn.` : chosen ? `Đã chọn câu ${form.ids[0]}.` : 'Bấm vào một câu để chọn.'}
            </span>
          </>
        )}

        {error && <div className="pd-alert" style={{ marginTop: '0.9rem' }}>{error}</div>}

        <div className="pd-actionbar">
          <div className="pd-estimate">
            {replay ? (
              <>Phát lại không gọi model. <span className="pd-params">Tham số của lần chạy giữ nguyên.</span></>
            ) : estimate ? (
              <>
                <b>{estimate.questions} câu, {estimate.llm_calls} lần gọi model</b>. Ước tính {formatCost(estimate.cost_usd)}, khoảng {formatDuration(estimate.seconds)}.{' '}
                <span className="pd-params">temperature {options.parameters.temperature}, top_p {options.parameters.top_p}, max tokens {options.parameters.max_tokens}, giống paper.</span>
                {overBudget && <div className="pd-alert warn" style={{ marginTop: 6 }}>Ước tính cao hơn hạn mức, lần chạy sẽ dừng giữa chừng. Hãy tăng hạn mức hoặc giảm số câu.</div>}
              </>
            ) : 'Đang ước tính.'}
          </div>
          <button type="button" className="btn btn-primary" disabled={!canStart} onClick={() => onStart(request)}>
            <Play size={15} />
            {replay ? 'Phát lại' : count ? `Chạy ${count} câu` : 'Chạy'}
          </button>
        </div>
      </div>
    </div>
  );
}

function describeRun(form, runs, options) {
  const names = { direct: 'Direct', vsql: 'V-SQL' };
  const frameworks = form.frameworks.map((f) => names[f]).join(' và ');
  if (form.source === 'replay') {
    const stored = runs.find((r) => r.key === form.replay_run);
    return `Phát lại "${stored?.title || form.replay_run}", ${frameworks}`;
  }
  const model = options.models.find((m) => m.id === form.model);
  const view = options.view_modes.find((v) => v.id === form.view_mode);
  return `${model?.label}, ${frameworks}, ${view?.label.toLowerCase()}`;
}

function buildRequest(form) {
  let selection;
  if (form.questionMode === 'all') selection = { mode: 'all' };
  else if (form.questionMode === 'random') selection = { mode: 'filter', db: form.db, difficulty: form.difficulty, limit: form.limit, seed: form.seed };
  else selection = { mode: 'ids', ids: form.ids };
  const request = {
    selection,
    frameworks: form.frameworks,
    source: form.source,
    budget_usd: form.budget_usd,
    step_delay_s: form.source === 'replay' ? form.step_delay_s : 0,
  };
  if (form.source === 'replay') request.replay_run = form.replay_run;
  else Object.assign(request, { model: form.model, view_mode: form.view_mode, schema_mode: form.schema_mode });
  return request;
}

const DEFAULT_FORM = {
  source: 'replay',
  replay_run: 'luna_500_paper',
  model: 'gpt-6-luna',
  view_mode: 'paper',
  schema_mode: 'described',
  budget_usd: 0.25,
  frameworks: ['direct', 'vsql'],
  questionMode: 'one',
  ids: [],
  db: 'all',
  difficulty: 'all',
  search: '',
  limit: 10,
  seed: 42,
  step_delay_s: 1.2,
};

export default function PipelineDemo({ prefill }) {
  const [options, setOptions] = useState(null);
  const [runs, setRuns] = useState([]);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [error, setError] = useState('');
  const [run, setRun] = useState(null);
  const [selected, setSelected] = useState({ framework: 'vsql', id: 'stage1' });
  const [focus, setFocus] = useState(null);
  const [follow, setFollow] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(true);
  const [, setTick] = useState(0);
  const stepsRef = useRef({});
  const sourceRef = useRef(null);
  const followRef = useRef(true);
  const scheduled = useRef(false);

  const rerender = useCallback(() => {
    if (scheduled.current) return;
    scheduled.current = true;
    setTimeout(() => {
      scheduled.current = false;
      setTick((t) => t + 1);
    }, 80);
  }, []);

  useEffect(() => {
    fetch('/api/pipeline/options').then((r) => r.json()).then(setOptions).catch(() => setError('Không kết nối được backend. Hãy khởi động api_server.py.'));
    fetch('/api/runs').then((r) => r.json()).then((d) => setRuns(d.runs || [])).catch(() => {});
    return () => sourceRef.current?.close();
  }, []);

  useEffect(() => {
    if (prefill?.replay_run) setForm((prev) => ({ ...prev, source: 'replay', replay_run: prefill.replay_run }));
  }, [prefill]);

  useEffect(() => { followRef.current = follow; }, [follow]);

  const loadDetail = useCallback(async (runId, questionId) => {
    setDetailLoading(true);
    try {
      const response = await fetch(`/api/pipeline/runs/${runId}/questions/${questionId}`);
      const data = await response.json();
      const entry = stepsRef.current[questionId] || (stepsRef.current[questionId] = {});
      Object.entries(data.steps).forEach(([framework, steps]) => {
        entry[framework] = Object.fromEntries(steps.map((s) => [s.id, s]));
      });
      rerender();
    } finally {
      setDetailLoading(false);
    }
  }, [rerender]);

  const start = async (request) => {
    setError('');
    sourceRef.current?.close();
    let response;
    try {
      response = await fetch('/api/pipeline/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request) });
    } catch {
      setError('Không kết nối được backend. Hãy khởi động api_server.py.');
      return;
    }
    const data = await response.json();
    if (!response.ok) {
      setError(data.detail || 'Không bắt đầu được lần chạy.');
      return;
    }
    stepsRef.current = {};
    setSettingsOpen(false);
    const light = data.light_events;
    const state = {
      id: data.run_id,
      light,
      status: 'queued',
      message: '',
      config: request,
      frameworks: data.frameworks,
      summary: { total_questions: data.total_questions, frameworks: Object.fromEntries(data.frameworks.map((f) => [f, { done: 0, correct: 0, ex: 0, avg_latency_s: 0, stage1_correct: 0, stage1_ex: 0 }])), by_difficulty: {}, by_db: {}, pairs: null, cost_usd: 0, elapsed_s: 0 },
      questions: [],
      results: {},
    };
    setRun(state);
    setFocus(null);
    setFollow(!light);
    followRef.current = !light;
    let lastSeq = -1;
    const source = new EventSource(`/api/pipeline/runs/${data.run_id}/events`);
    sourceRef.current = source;
    source.onmessage = (message) => {
      const event = JSON.parse(message.data);
      if (event.seq <= lastSeq) return;
      lastSeq = event.seq;
      setRun((prev) => applyEvent(prev, event, stepsRef.current));
      if (event.type === 'question_start' && followRef.current) setFocus(event.question.question_id);
      if (event.type === 'question_start' && light && event.index === 0) setFocus(event.question.question_id);
      if (event.type === 'step' && followRef.current) setSelected({ framework: event.step.framework, id: event.step.id });
      if (event.type === 'run_done') source.close();
      rerender();
    };
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) setError('Mất kết nối tới backend.');
    };
  };

  useEffect(() => {
    if (!run?.light || focus === null) return;
    loadDetail(run.id, focus);
  }, [focus, run?.id, run?.light, loadDetail, run?.results?.[focus]?.vsql?.ok, run?.results?.[focus]?.direct?.ok]);

  const cancel = () => run && fetch(`/api/pipeline/runs/${run.id}/cancel`, { method: 'POST' });
  const selectStation = (next) => {
    setSelected(next);
    setFollow(false);
  };

  if (!options) {
    return <div className="pd-page">{error ? <div className="pd-alert">{error}</div> : <div className="pd-empty-note">Đang tải cấu hình.</div>}</div>;
  }

  const frameworks = run?.frameworks?.length ? run.frameworks : ['direct', 'vsql'];
  const focusQuestion = run?.questions.find((q) => q.question_id === focus);
  const steps = focus !== null ? stepsRef.current[focus] : null;
  const focusResults = run?.results?.[focus];
  const running = run && (run.status === 'queued' || run.status === 'running');
  const showList = run && run.summary.total_questions > 1;

  return (
    <div className="pd-page">
      {!run && <p className="pd-intro">Xem từng câu hỏi đi qua pipeline. Mỗi trạm là một bước: bấm vào trạm để xem đúng dữ liệu đi vào và đi ra ở bước đó.</p>}
      {settingsOpen ? (
        <Settings options={options} runs={runs} form={form} setForm={setForm} onStart={start} busy={running} error={error} />
      ) : (
        <div className="pd-panel">
          <div className="pd-panel-head">
            <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>{describeRun(form, runs, options)}</span>
            <button type="button" className="btn btn-secondary" style={{ padding: '0.35rem 0.8rem', fontSize: '0.82rem', flex: 'none' }} onClick={() => setSettingsOpen(true)}>Đổi cấu hình</button>
          </div>
        </div>
      )}
      {run && <ScoreStrip summary={run.summary} status={run.status} message={run.message} config={run.config} onCancel={cancel} />}
      <div className={`pd-workspace ${showList ? 'has-list' : ''}`}>
        {showList && <QuestionList questions={run.questions} results={run.results} focus={focus} onFocus={(id) => { setFocus(id); setFollow(false); }} frameworks={frameworks} />}
        <div className="pd-panel" style={{ minWidth: 0 }}>
          {focusQuestion ? (
            <div className="pd-question">
              <div className="pd-chips">
                <span className="badge badge-neutral">Câu {focusQuestion.question_id}</span>
                <span className="badge badge-neutral">{focusQuestion.db_id}</span>
                <span className="badge badge-neutral">{LEVEL_LABELS[focusQuestion.difficulty]}</span>
                {focusResults?.direct && <span className={`badge ${focusResults.direct.ok ? 'badge-success' : 'badge-danger'}`}>Direct {focusResults.direct.ok ? 'đúng' : 'sai'}</span>}
                {focusResults?.vsql && <span className={`badge ${focusResults.vsql.ok ? 'badge-success' : 'badge-danger'}`}>V-SQL {focusResults.vsql.ok ? 'đúng' : 'sai'}</span>}
                {running && !follow && !run.light && <button type="button" className="pd-copy" onClick={() => setFollow(true)}>Theo dõi bước mới nhất</button>}
              </div>
              <h3>{focusQuestion.question}</h3>
              {focusQuestion.evidence && <p>Evidence: {focusQuestion.evidence}</p>}
            </div>
          ) : (
            <div className="pd-question">
              <h3>Sơ đồ pipeline</h3>
              <p>Bấm vào một trạm để đọc bước đó làm gì. Sau khi chạy, trạm sẽ hiện đầu vào và đầu ra thật.</p>
            </div>
          )}
          <div className="pd-tracks">
            <div className="pd-track-grid">
              {frameworks.map((framework) => (
                <Lane key={framework} framework={framework} steps={steps?.[framework]} selected={selected} onSelect={selectStation} />
              ))}
            </div>
          </div>
          <div className="pd-legend">
            <span><i className="square" />Gọi model</span>
            <span><i className="circle" />Tính toán trên máy, không tốn token</span>
          </div>
          <Inspector selected={selected} steps={steps} loading={detailLoading} />
        </div>
      </div>
      {run && run.summary.total_questions > 1 && Object.keys(run.summary.by_db).length > 0 && <Breakdown summary={run.summary} frameworks={frameworks} />}
    </div>
  );
}

function applyEvent(state, event, steps) {
  if (!state) return state;
  switch (event.type) {
    case 'run_start':
      return { ...state, status: 'running' };
    case 'question_start':
      if (state.questions.some((q) => q.question_id === event.question.question_id)) return state;
      return { ...state, questions: [...state.questions, event.question] };
    case 'step': {
      const { step } = event;
      const entry = steps[step.question_id] || (steps[step.question_id] = {});
      const lane = entry[step.framework] || (entry[step.framework] = {});
      lane[step.id] = { ...lane[step.id], ...step };
      return state;
    }
    case 'question_done':
      return {
        ...state,
        summary: event.summary,
        results: { ...state.results, [event.question_id]: { ...state.results[event.question_id], [event.framework]: event.result } },
      };
    case 'run_done':
      return { ...state, status: event.status, message: event.message, summary: event.summary };
    default:
      return state;
  }
}
