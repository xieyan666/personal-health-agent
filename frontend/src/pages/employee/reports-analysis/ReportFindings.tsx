import type { ReportFinding } from '../../../api/healthReports'

export function ReportFindings({ findings, onViewAll }: { findings: ReportFinding[]; onViewAll: () => void }) {
  if (!findings.length) return null
  const visible = findings.slice(0, 5)
  return (
    <section className="analysis-section">
      <h4>关键发现 <span className="analysis-section-hint">展示部分正常指标</span></h4>
      <div className="analysis-findings">
        {visible.map((finding) => (
          <div className="analysis-finding" key={`${finding.item_name}-${finding.value}`}>
            <span className="analysis-finding-mark">✓</span>
            <div>
              <b>{finding.item_name}</b>
              <small>{finding.value}</small>
              <p>{finding.description}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="analysis-actions" style={{ marginTop: 10 }}>
        <button className="analysis-link-btn" onClick={onViewAll}>查看全部指标 →</button>
      </div>
    </section>
  )
}
