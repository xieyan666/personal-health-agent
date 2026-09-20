import type { ReportAnalysisOverall as Overall } from '../../../api/healthReports'

const LEVEL_META = {
  good: { label: '整体情况良好', icon: '✓' },
  attention: { label: '整体指标较稳定', icon: '⚠' },
  caution: { label: '需要重点关注', icon: '!' },
} as const

export function ReportOverallCard({ overall }: { overall: Overall }) {
  const meta = LEVEL_META[overall.level] ?? LEVEL_META.attention
  return (
    <section className={`analysis-overall level-${overall.level}`}>
      <div className="analysis-overall-icon">{meta.icon}</div>
      <div>
        <h4>{overall.title || meta.label}</h4>
        <p>{overall.description}</p>
      </div>
    </section>
  )
}
