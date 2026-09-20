import type { ReportSuggestion } from '../../../api/healthReports'

export function ReportSuggestions({ items }: { items: ReportSuggestion[] }) {
  if (!items.length) return null
  return (
    <section className="analysis-section">
      <h4>健康建议</h4>
      <div className="analysis-suggestions">
        {items.map((item, index) => (
          <div className="analysis-suggestion" key={`${item.title}-${index}`}>
            <span className="analysis-suggestion-num">{String(index + 1).padStart(2, '0')}</span>
            <div>
              <b>{item.title}</b>
              <p>{item.description}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
