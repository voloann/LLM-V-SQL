import React, { useEffect, useState } from 'react';
import { Play } from 'lucide-react';
import MainConfigTable from '../components/MainConfigTable';
import './pipeline.css';

const SERIES = [
  { key: 'direct', label: 'Direct', color: 'var(--series-direct)' },
  { key: 'stage1', label: 'Stage 1', color: 'var(--series-stage1)' },
  { key: 'vsql', label: 'V-SQL', color: 'var(--series-vsql)' },
];

const VIEW_LABELS = { manual: 'View thủ công', paper: 'Gold chọn lọc theo bài báo', fk: 'View theo khóa ngoại', gold: 'View theo mọi join gold SQL' };
const SCHEMA_LABELS = { described: 'Schema có mô tả', names: 'Schema chỉ tên cột' };
const LEVELS = { simple: 'Dễ', moderate: 'Trung bình', challenging: 'Khó' };

const formatP = (p) => (p < 0.001 ? p.toExponential(1) : p.toFixed(3));

function Bars({ run }) {
  return (
    <div className="jr-bars">
      {SERIES.map((series) => {
        const cell = run[series.key];
        return (
          <div className="jr-bar" key={series.key} title={cell ? `${series.label}: ${cell.correct}/${cell.n} câu đúng` : `${series.label}: lần chạy này không đo`}>
            <span>{series.label}</span>
            <div className="jr-bar-track">{cell && <i style={{ width: `${cell.ex}%`, background: series.color }} />}</div>
            <b>{cell ? `${cell.ex.toFixed(1)}%` : 'Không đo'}</b>
          </div>
        );
      })}
      {run.pairs && (
        <div className="jr-pairs">
          Chỉ Direct đúng {run.pairs.direct_only} câu, chỉ V-SQL đúng {run.pairs.vsql_only} câu, p = {formatP(run.pairs.p)}
        </div>
      )}
    </div>
  );
}

function ViewComparison({ runs, coverage }) {
  const rows = ['manual', 'paper', 'fk', 'gold']
    .map((mode) => ({ mode, run: runs.find((r) => r.view_mode === mode && r.schema_mode === 'described' && r.n === 500 && r.available), stats: coverage[mode] }))
    .filter((row) => row.stats);
  return (
    <div className="pd-panel">
      <div className="pd-panel-head"><h2>Độ phủ của view ảnh hưởng thế nào</h2></div>
      <div style={{ overflowX: 'auto' }}>
        <table className="pd-breakdown">
          <thead>
            <tr>
              <th scope="col">Bộ view</th>
              <th scope="col">Số view</th>
              <th scope="col">Cột bảng gốc được phủ (trên 798)</th>
              <th scope="col">Câu còn thiếu dữ liệu trong view</th>
              <th scope="col">Stage 1</th>
              <th scope="col">V-SQL</th>
              <th scope="col">Direct</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ mode, run, stats }) => (
              <tr key={mode}>
                <td>{VIEW_LABELS[mode]}</td>
                <td>{stats.views}</td>
                <td>{stats.distinct_columns_exposed}</td>
                <td>{stats.questions_with_gap}</td>
                <td>{run?.stage1 ? `${run.stage1.ex.toFixed(1)}%` : 'Chưa có'}</td>
                <td>{run?.vsql ? `${run.vsql.ex.toFixed(1)}%` : 'Chưa có'}</td>
                <td>{run?.direct ? `${run.direct.ex.toFixed(1)}%` : 'Chưa có'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="pd-hint" style={{ padding: '0.7rem 1.1rem' }}>
        Một câu bị tính là thiếu khi view không có bảng, cột, hoặc tổ hợp join mà gold SQL cần. Kết quả Direct của ba dòng là một, vì prompt của Direct không dùng view.
      </p>
    </div>
  );
}

function GapGroups({ analysis }) {
  if (!analysis?.groups?.length) return null;
  const modes = analysis.modes;
  return (
    <div className="pd-panel">
      <div className="pd-panel-head"><h2>Cùng một câu hỏi, đổi bộ view</h2></div>
      <div style={{ overflowX: 'auto' }}>
        <table className="pd-breakdown">
          <thead>
            <tr>
              <th scope="col">Nhóm câu hỏi</th>
              <th scope="col">Số câu</th>
              <th scope="col">Direct</th>
              {modes.map((mode) => <th scope="col" key={mode}>V-SQL, {VIEW_LABELS[mode].toLowerCase()}</th>)}
            </tr>
          </thead>
          <tbody>
            {analysis.groups.filter((row) => row.n).map((row) => (
              <tr key={row.group}>
                <td>{row.label}</td>
                <td>{row.n}</td>
                <td>{row.direct.ex.toFixed(1)}%</td>
                {modes.map((mode) => <td key={mode}>{row.vsql[mode].ex.toFixed(1)}%</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="pd-hint" style={{ padding: '0.7rem 1.1rem' }}>
        Nhóm được chia sau khi có kết quả và dựa trên gold SQL, nên bảng này giúp giải thích chênh lệch chứ không phải một phép kiểm định độc lập.
      </p>
    </div>
  );
}

function DifficultyTable({ runs }) {
  const shown = runs.filter((r) => r.available && r.n === 500 && r.valid && r.by_difficulty);
  if (!shown.length) return null;
  return (
    <div className="pd-panel">
      <div className="pd-panel-head"><h2>Theo độ khó, các lần chạy đủ 500 câu</h2></div>
      <div style={{ overflowX: 'auto' }}>
        <table className="pd-breakdown">
          <thead>
            <tr>
              <th scope="col">Lần chạy</th>
              {Object.values(LEVELS).map((label) => <React.Fragment key={label}><th scope="col">{label}: Direct</th><th scope="col">{label}: V-SQL</th></React.Fragment>)}
            </tr>
          </thead>
          <tbody>
            {shown.map((run) => (
              <tr key={run.key}>
                <td>{run.title}</td>
                {Object.keys(LEVELS).map((level) => (
                  <React.Fragment key={level}>
                    <td>{run.by_difficulty[level]?.direct?.ex?.toFixed(1)}%</td>
                    <td>{run.by_difficulty[level]?.vsql?.ex?.toFixed(1)}%</td>
                  </React.Fragment>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function conclusion(runs, mainKeys) {
  const rows = (mainKeys || []).map((key) => runs.find((r) => r.key === key && r.available && r.complete)).filter(Boolean);
  if (!rows.length) return null;
  const names = (group) => {
    const models = group.map((r) => r.model);
    return models.length > 1 ? `${models.slice(0, -1).join(', ')} và ${models[models.length - 1]}` : models[0];
  };
  const higher = rows.filter((r) => r.pairs.p < 0.05 && r.vsql.ex > r.direct.ex);
  const lower = rows.filter((r) => r.pairs.p < 0.05 && r.vsql.ex < r.direct.ex);
  const unclear = rows.filter((r) => r.pairs.p >= 0.05);
  const title = [
    higher.length ? `V-SQL cao hơn rõ so với Direct trên ${names(higher)}.` : '',
    lower.length ? `V-SQL thấp hơn rõ so với Direct trên ${names(lower)}.` : '',
    unclear.length ? `Trên ${names(unclear)}, chênh lệch chưa đủ để kết luận.` : '',
  ].filter(Boolean).join(' ');
  return {
    title,
    body: 'Mọi số dưới đây được chấm trên bảng gốc theo cùng cách tính Execution Accuracy. Mỗi bước đổi một yếu tố để trả lời một câu hỏi.',
  };
}

export default function Journey({ onReplay }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch('/api/runs').then((r) => r.json()).then(setData).catch(() => setError('Không kết nối được backend. Hãy khởi động api_server.py.'));
  }, []);

  if (error) return <div className="pd-alert">{error}</div>;
  if (!data) return <div className="pd-empty-note">Đang tải các lần chạy.</div>;

  const summary = conclusion(data.runs, data.main_runs);
  const totalCost = data.runs.reduce((sum, run) => sum + (run.cost_usd || 0), 0);

  return (
    <div className="pd-page">
      {summary && (
        <div className="pd-panel jr-conclusion">
          <h2>{summary.title}</h2>
          <p>{summary.body} Tổng chi phí API khoảng ${totalCost.toFixed(2)}.</p>
        </div>
      )}
      <MainConfigTable runs={data.runs} mainKeys={data.main_runs} mechanism={data.mechanism} />
      <div className="pd-panel">
        <div className="pd-panel-head"><h2>Các lần chạy theo thứ tự thực hiện</h2></div>
        <div className="jr-legend">
          {SERIES.map((s) => <span key={s.key}><span className="pd-dot" style={{ background: s.color }} />{s.label}</span>)}
        </div>
        {data.runs.map((run) => (
          <div className={`jr-step ${run.valid ? '' : 'invalid'}`} key={run.key}>
            <div className="jr-num">{run.step}</div>
            <div>
              <h3>
                {run.title}
                {!run.valid && <span className="badge badge-warning">Không dùng để kết luận</span>}
                {run.tag && <span className={`badge ${run.tag === 'Cấu hình chính' ? 'badge-success' : 'badge-neutral'}`}>{run.tag}</span>}
                {!run.available && <span className="badge badge-neutral">Đang chạy</span>}
              </h3>
              <p className="jr-why">{run.why}</p>
              {run.finding && <p className="jr-finding">{run.finding}</p>}
              <div className="jr-config">
                <span className="badge badge-neutral">{run.model}</span>
                <span className="badge badge-neutral">{run.n || '?'} câu</span>
                <span className="badge badge-neutral">{VIEW_LABELS[run.view_mode]}</span>
                <span className="badge badge-neutral">{SCHEMA_LABELS[run.schema_mode]}</span>
                {run.replayable && (
                  <button type="button" className="btn btn-secondary" style={{ padding: '0.25rem 0.65rem', fontSize: '0.78rem' }} onClick={() => onReplay(run.key)}>
                    <Play size={12} />Phát lại
                  </button>
                )}
              </div>
            </div>
            {run.available ? <Bars run={run} /> : <div className="pd-empty-note">Chưa có kết quả.</div>}
          </div>
        ))}
      </div>
      <ViewComparison runs={data.runs} coverage={data.coverage || {}} />
      <GapGroups analysis={data.analysis} />
      <DifficultyTable runs={data.runs} />
    </div>
  );
}
