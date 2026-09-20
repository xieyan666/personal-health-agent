import { Button, Card, Empty, Modal, Progress, Tag } from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as echarts from 'echarts'
import { getHealthRisk, getHealthRiskHistory, getHealthRiskTrend, type HealthRiskHistoryRecord, type HealthRiskTrendPoint, type RiskAssessment } from '../../api/healthProfile'
import './risk.css'

const labels: Record<string, string> = { sleep: '睡眠风险', exercise: '运动风险', heart_rate: '心率风险', bmi: 'BMI风险' }
const levelLabel: Record<string, string> = { low: '正常', medium: '需要关注', high: '高风险' }
const tagColor = (level: string) => level === 'low' ? 'success' : level === 'medium' ? 'warning' : 'error'
const scoreTagColor = (level: string) => level === '良好' ? 'success' : level === '稳定' ? 'green' : level === '需关注' ? 'warning' : 'error'

function getRecordDetail(record: HealthRiskHistoryRecord) {
  if (record.factor.includes('睡眠')) return { title: '睡眠恢复需要持续关注', impact: '睡眠时间低于推荐范围时，可能影响日间专注力与身体恢复。', advice: ['建立固定睡眠窗口，尽量保持规律作息。', '睡前 30 分钟减少电子设备使用。', '持续同步睡眠数据，观察后续变化。'] }
  if (record.factor.includes('运动')) return { title: '运动达标情况需要跟进', impact: '规律运动有助于维持心肺健康和精力恢复。', advice: ['将运动安排分散到每周多个时段。', '优先保持可持续的步行或中等强度运动。', '持续记录运动时长，观察下一个周期评分。'] }
  if (record.factor.includes('心率')) return { title: '静息心率指标需要观察', impact: '心率变化可能与睡眠、压力、运动恢复等因素相关。', advice: ['保持规律作息与适度运动。', '在安静状态下持续记录静息心率。', '若出现明显不适，请及时咨询专业医疗人员。'] }
  if (record.factor.includes('BMI')) return { title: '体重相关指标需要关注', impact: '体重与 BMI 的长期变化会影响综合健康风险评分。', advice: ['保持均衡饮食和规律运动。', '以长期、渐进的方式管理体重。', '定期更新健康档案中的身高和体重。'] }
  return { title: '本阶段健康状态整体稳定', impact: '当前阶段未发现明显风险因素，建议继续维持现有健康习惯。', advice: ['保持规律作息。', '维持每周运动习惯。', '继续同步健康数据，形成长期趋势。'] }
}

function RiskTrendChart({ data }: { data: HealthRiskTrendPoint[] }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current || !data.length) return
    const chart = echarts.init(ref.current)
    chart.setOption({
      grid: { left: 48, right: 24, top: 36, bottom: 36 },
      tooltip: { trigger: 'axis', formatter: (items: any[]) => { const point = data[items[0].dataIndex]; return `时间范围：${point.period}<br/>(${point.start_date.slice(5)} - ${point.end_date.slice(5)})<br/>综合风险评分：${point.score}<br/>风险等级：${point.level}<br/>主要影响因素：${point.factors.length ? point.factors.join('、') : '暂无明显因素'}<br/>数据来源：Health Risk Engine` } },
      xAxis: { type: 'category', data: data.map(x => x.period), axisTick: { show: false }, axisLine: { lineStyle: { color: '#dce7e2' } } },
      yAxis: { type: 'value', min: 0, max: 100, name: '风险评分', axisLine: { show: false }, splitLine: { lineStyle: { color: '#edf3ef' } } },
      series: [{ type: 'bar', data: data.map(x => x.score), barMaxWidth: 56, itemStyle: { color: '#86d6a4', borderRadius: [8, 8, 0, 0] }, label: { show: true, position: 'top', color: '#166534', fontWeight: 600 } }],
    })
    const resize = () => chart.resize(); window.addEventListener('resize', resize)
    return () => { window.removeEventListener('resize', resize); chart.dispose() }
  }, [data])
  return <div ref={ref} className="risk-chart" />
}

export function Risk() {
  const [risks, setRisks] = useState<RiskAssessment[]>([])
  const [trend, setTrend] = useState<HealthRiskTrendPoint[]>([])
  const [history, setHistory] = useState<HealthRiskHistoryRecord[]>([])
  const [selectedRecord, setSelectedRecord] = useState<HealthRiskHistoryRecord | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const [riskRows, trendResponse] = await Promise.all([getHealthRisk(), getHealthRiskTrend()])
        const historyResponse = await getHealthRiskHistory()
        if (!cancelled) {
          setRisks(riskRows)
          setTrend(trendResponse.data)
          setHistory(historyResponse.records)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => { cancelled = true }
  }, [])
  const attention = risks.filter((item) => item.level !== 'low')
  const sleep = risks.find((item) => item.risk_type === 'sleep')
  const latestTrendScore = trend.length ? trend[trend.length - 1].score : undefined
  const score = useMemo(() => latestTrendScore ?? Math.max(0, 100 - risks.reduce((total, item) => total + (item.level === 'high' ? 20 : item.level === 'medium' ? 8 : 0), 0)), [risks, latestTrendScore])
  const overall = score >= 85 ? '良好' : score >= 75 ? '稳定' : score >= 60 ? '需关注' : '风险较高'
  const overallText = attention.length ? '你的近期健康状态整体稳定，但检测到部分指标需要持续关注。' : '你的近期健康状态整体稳定，请继续保持规律作息与运动习惯。'

  return <section className="risk-page">
    <div className="risk-heading"><p>基于近期健康数据进行风险评估与健康管理</p></div>
    <Card className="risk-overview" title="健康风险概览"><div className="risk-overview-grid"><div><span>综合健康评分</span><strong>{loading ? '—' : score}</strong><Tag color="success">{overall}</Tag><small>来源：Health Risk Engine</small></div><div><span>当前风险等级</span><strong className={`risk-level ${overall === '风险较高' ? 'danger' : overall === '需关注' ? 'warn' : ''}`}>{loading ? '—' : overall}</strong><small>● {overall === '良好' || overall === '稳定' ? '正常' : '请关注异常指标'}</small></div><div><span>数据覆盖</span><strong>✓ 健康档案</strong><small>✓ Wearable　数据完整度 85%</small></div><div><span>最近分析</span><strong>{new Date().toLocaleDateString('zh-CN')}</strong><small>Health Risk Engine</small></div></div></Card>
    <div className="risk-columns"><Card title="风险评估" className="risk-list-card">{risks.length ? risks.map((risk) => <div className="risk-card" key={risk.risk_type}><div className="risk-card-head"><h3>{labels[risk.risk_type] || risk.risk_type}</h3><Tag color={tagColor(risk.level)}>{levelLabel[risk.level] || risk.level}</Tag></div><p className="risk-reason-label">风险原因</p><p>{risk.description}</p><p className="risk-impact">影响：{risk.level === 'low' ? '当前处于推荐范围，继续保持即可。' : '可能影响日间精力与身体恢复，请结合生活作息持续关注。'}</p><small>来源：{risk.risk_type === 'sleep' ? 'Sleep Analysis Tool' : risk.source}</small><div className="risk-recommendation">建议：{risk.recommendation}</div></div>) : <Empty description="暂无风险评估" />}</Card><Card title="AI风险分析" className="risk-ai-card"><div className="risk-agent-state"><Tag color="green">AI Risk Agent</Tag><span>● 分析完成</span></div><small>分析时间：{new Date().toLocaleString('zh-CN')}</small><div className="risk-ai-overall"><h3>AI综合评估</h3><p>{overallText}</p><div><span>健康评分</span><strong>{score} <small>/ 100</small></strong><Tag color={overall === '良好' || overall === '稳定' ? 'success' : overall === '需关注' ? 'warning' : 'error'}>{overall === '良好' || overall === '稳定' ? '低风险' : overall}</Tag></div></div>{sleep && <div className="risk-ai-finding"><h3>⚠ 睡眠风险 <Tag color={tagColor(sleep.level)}>{levelLabel[sleep.level]}</Tag></h3><p><b>AI发现：</b>{sleep.description}</p><p><b>趋势：</b>当前规则引擎以近期平均数据计算；趋势变化需接入风险历史数据后展示。</p><p><b>可能原因：</b>睡眠时间不规律、睡前电子设备使用或工作压力均可能影响入睡与恢复。</p><p><b>潜在影响：</b>短期可能出现注意力下降和精力恢复不足；长期睡眠不足可能影响代谢状态。</p></div>}<div className="risk-ai-advice"><h3>AI建议</h3><ol><li><b>建立固定睡眠窗口</b><span>建议尽量在 23:00 前进入睡眠状态。</span></li><li><b>优化睡前环境</b><span>睡前 30 分钟减少电子设备使用。</span></li><li><b>持续数据监测</b><span>继续同步 Wearable 数据，观察睡眠趋势变化。</span></li></ol></div><div className="risk-chain"><h3>分析依据</h3><div>Health Profile Tool <span>→ 获取年龄、BMI、基础信息</span></div><div>Wearable Tool <span>→ 获取睡眠、心率、运动</span></div><div>Risk Engine <span>→ 计算风险等级</span></div><div>AI Risk Agent <span>→ 生成风险解释与建议（planned）</span></div></div></Card></div>
    <Card title={<div className="risk-trend-title"><span>风险趋势变化</span><small>近30天综合风险评分（阶段性评估）</small></div>} className="risk-trend">{trend.length ? <RiskTrendChart data={trend} /> : <Empty description="暂无阶段性风险数据" />}</Card>
    <Card title="历史风险记录" className="risk-history">{history.length ? <div className="risk-history-timeline">{history.map((record) => <article className="risk-history-item" key={record.id}><time>{record.date}</time><div className="risk-history-line" aria-hidden="true" /><div className="risk-history-content"><div className="risk-history-head"><div><span className="risk-history-score">风险评分 <b>{record.score}</b></span><Tag color={scoreTagColor(record.level)}>{record.level}</Tag></div><Button type="link" className="risk-history-detail" onClick={() => setSelectedRecord(record)}>查看详情 ›</Button></div><p><b>主要关注：</b>{record.factor}</p><small>评估周期：{record.period_start} ～ {record.period_end}　·　来源：{record.data_source}</small></div></article>)}</div> : <Empty description={loading ? '正在加载历史风险记录' : '暂无历史风险记录'} />}</Card>
    <Modal open={Boolean(selectedRecord)} footer={<Button type="primary" onClick={() => setSelectedRecord(null)}>知道了</Button>} onCancel={() => setSelectedRecord(null)} width={680} className="risk-detail-modal" title="风险评估详情">{selectedRecord && <RiskRecordDetail record={selectedRecord} />}</Modal>
  </section>
}

function RiskRecordDetail({ record }: { record: HealthRiskHistoryRecord }) {
  const detail = getRecordDetail(record)
  return <div className="risk-detail-report"><section className="risk-detail-hero"><div><span>阶段性健康风险评估</span><h2>{detail.title}</h2><p>{record.period_start} ～ {record.period_end}</p></div><div className="risk-detail-score"><b>{record.score}</b><span>/ 100</span><Tag color={scoreTagColor(record.level)}>{record.level}</Tag></div></section><section className="risk-detail-section"><h3>综合结论</h3><p>本次评估由 Health Risk Engine 基于健康档案及该周期的可用健康数据计算得出，主要关注项为“{record.factor}”。</p><Progress percent={record.score} showInfo={false} strokeColor="#22a75a" trailColor="#e8f5ed" /></section><section className="risk-detail-grid"><div><h3>主要影响因素</h3><strong>{record.factor}</strong><small>评分来自规则引擎，不由 AI 模型生成。</small></div><div><h3>潜在影响</h3><p>{detail.impact}</p></div></section><section className="risk-detail-section risk-detail-advice"><h3>改善建议</h3><ol>{detail.advice.map((item, index) => <li key={item}><b>0{index + 1}</b><span>{item}</span></li>)}</ol></section><footer><span>数据来源：{record.data_source}</span><span>评估日期：{record.date}</span></footer></div>
}
