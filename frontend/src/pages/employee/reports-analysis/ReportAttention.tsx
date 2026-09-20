import { Tag } from 'antd'
import type { ReportAttention } from '../../../api/healthReports'

export function ReportAttention({ items }: { items: ReportAttention[] }) {
  if (!items.length) return null
  return (
    <section className="analysis-section">
      <h4>需要关注 <Tag color="warning">Attention</Tag></h4>
      <div className="analysis-attention">
        {items.map((item, index) => (
          <div className={`analysis-attention-card status-${item.status}`} key={`${item.item_name}-${index}`}>
            <h5>
              <span>{item.item_name}</span>
              <Tag color={item.status === 'high' ? 'error' : 'warning'}>
                {item.status === 'high' ? '偏高' : '偏低'}
              </Tag>
            </h5>
            <div className="analysis-attention-value">
              <strong>{item.value}</strong>
              {item.reference ? <span>报告参考范围：{item.reference}</span> : null}
            </div>
            <p className="analysis-attention-desc">{item.description}</p>
            {item.source_type === 'ocr' && (
              <span className="analysis-ocr-note">📷 OCR识别 · 建议核对原始报告</span>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}
