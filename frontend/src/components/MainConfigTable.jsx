import React from 'react';
import '../pages/pipeline.css';

const formatP = (p) => (p < 0.001 ? '< 0.001' : p.toFixed(3));

function cost(run) {
  if (run.cost_usd === undefined) return '';
  return run.cost_usd > 0 ? `$${run.cost_usd.toFixed(2)}` : 'Miễn phí';
}

export default function MainConfigTable({ runs, mainKeys, mechanism }) {
  const rows = (mainKeys || []).map((key) => (runs || []).find((r) => r.key === key)).filter(Boolean);
  if (!rows.length) return null;
  return (
    <div className="pd-panel">
      <div className="pd-panel-head"><h2>Cấu hình chính trên 4 model</h2></div>
      <div style={{ overflowX: 'auto' }}>
        <table className="pd-breakdown">
          <thead>
            <tr>
              <th scope="col">Model</th>
              <th scope="col">Direct</th>
              <th scope="col">Stage 1</th>
              <th scope="col">V-SQL</th>
              <th scope="col">Chỉ Direct đúng</th>
              <th scope="col">Chỉ V-SQL đúng</th>
              <th scope="col">p</th>
              <th scope="col">Giây mỗi câu, Direct</th>
              <th scope="col">Giây mỗi câu, V-SQL</th>
              <th scope="col">Tiền API</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((run) => {
              if (!run.available) {
                return (
                  <tr key={run.key}>
                    <td>{run.model}</td>
                    <td colSpan={9}>Đang chạy, chưa có kết quả.</td>
                  </tr>
                );
              }
              const latency = mechanism?.[run.key]?.latency;
              return (
                <tr key={run.key}>
                  <td>{run.model}</td>
                  <td>{run.direct.ex.toFixed(1)}%</td>
                  <td>{run.stage1.ex.toFixed(1)}%</td>
                  <td>{run.vsql.ex.toFixed(1)}%</td>
                  <td>{run.pairs.direct_only}</td>
                  <td>{run.pairs.vsql_only}</td>
                  <td>{formatP(run.pairs.p)}</td>
                  <td>{latency ? latency.direct.toFixed(1) : ''}</td>
                  <td>{latency ? latency.vsql.toFixed(1) : ''}</td>
                  <td>{cost(run)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="pd-hint" style={{ padding: '0.7rem 1.1rem' }}>
        Cùng 500 câu, chấm trên bảng gốc. View gold chọn lọc gồm 43 view, schema có kiểu và mô tả cột. Mỗi model chạy một lần, và p so sánh Direct với V-SQL trên từng câu của chính model đó.
      </p>
    </div>
  );
}
