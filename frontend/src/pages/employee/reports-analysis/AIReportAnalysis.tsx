import { Alert, Button, Card, Empty, Tag } from 'antd'
import { useEffect, useState } from 'react'
import { getHealthCheckReportAnalysis, reanalyzeHealthCheckReport, type ReportAnalysisData } from '../../../api/healthReports'
import { ReportOverallCard } from './ReportOverallCard'
import { ReportSuggestions } from './ReportSuggestions'
import type { HealthCheckIndicator } from '../../../api/healthReports'
import '../reports-analysis.css'

const STEPS = ['加载体检指标', '读取健康档案', '构造 Report Context', 'AI Report Agent 分析中', 'Safety Guard', '生成解读']

function AnalysisLoading() {
  const [index, setIndex] = useState(0)
  useEffect(() => {
    const timer = window.setInterval(() => setIndex((current) => Math.min(current + 1, STEPS.length - 1)), 1100)
    return () => window.clearInterval(timer)
  }, [])
  return (
    <div className="analysis-loading">
      {STEPS.map((step, stepIndex) => {
        if (stepIndex < index) return <div className="analysis-step done" key={step}>✓ {step}</div>
        if (stepIndex === index) return <div className="analysis-step active" key={step}>● {step}</div>
        return <div className="analysis-step wait" key={step}>○ {step}</div>
      })}
    </div>
  )
}

function AnalysisBasis({ totalItems, profileAvailable, model }: { totalItems: number; profileAvailable: boolean; model: string }) {
  return (
    <section className="analysis-section">
      <h4>分析依据</h4>
      <div className="analysis-basis">
        <div className="analysis-basis-item"><small>体检报告</small><b>{totalItems} 项指标</b><span>结构化解析</span></div>
        <div className="analysis-basis-item"><small>Health Profile</small><b>{profileAvailable ? '已读取' : '暂无数据'}</b><span>{profileAvailable ? '健康档案' : '未录入档案'}</span></div>
        <div className="analysis-basis-item"><small>AI Report Agent</small><b>{model || 'DeepSeek'}</b><span>Report Analysis</span></div>
        <div className="analysis-basis-item"><small>Safety Guard</small><b>已通过</b><span>安全校验</span></div>
      </div>
    </section>
  )
}

export function AIReportAnalysis({
  reportId,
  totalItems,
  ocrUsed,
  analysis,
  selectedItem,
  onReanalyze,
  onViewAllIndicators,
}: {
  reportId: string
  totalItems: number
  ocrUsed: boolean
  analysis: ReportAnalysisData | null
  selectedItem: HealthCheckIndicator | null
  onReanalyze: () => void
  onViewAllIndicators: () => void
}) {
  const [reanalyzing, setReanalyzing] = useState(false)
  const status = analysis?.status
  const data = analysis?.analysis ?? null
  const statusMeta = status === 'completed'
    ? { label: '分析完成', color: 'success' as const }
    : status === 'failed'
      ? { label: '分析失败', color: 'error' as const }
      : status === 'processing' || status === 'pending'
        ? { label: '分析中', color: 'processing' as const }
        : { label: 'AI Report Agent', color: 'green' as const }

  const handleReanalyze = async () => {
    setReanalyzing(true)
    try {
      await reanalyzeHealthCheckReport(reportId)
      onReanalyze()
    } catch {
      /* the parent polling will surface the failure state */
    } finally {
      setReanalyzing(false)
    }
  }

  const updatedAt = analysis?.updated_at ? new Date(analysis.updated_at).toLocaleString('zh-CN', { hour12: false }) : null
  const selectedName = selectedItem?.item_name
  const normalizedName = (value?: string) => (value || '').replace(/\s+/g, '').toLowerCase()
  const selectedInterpretation = selectedName
    ? data?.attention.find((item) => normalizedName(item.item_name) === normalizedName(selectedName))?.description
      || data?.findings.find((item) => normalizedName(item.item_name) === normalizedName(selectedName))?.description
    : null
  const coreFindings = data ? [
    ...data.attention.slice(0, 2).map((item) => `${item.item_name}${item.status === 'high' ? '高于' : '低于'}参考范围`),
    ...data.findings.filter((item) => item.status === 'normal').slice(0, 2).map((item) => `${item.item_name}正常`),
  ].slice(0, 4) : []

  return (
    <Card className="report-analysis-card" style={{ flex: 1, width: '100%' }} bodyStyle={{ height: '100%', display: 'flex', flexDirection: 'column' }} title={<div className="report-analysis-head"><span>AI体检解读</span><div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Tag color="green">AI Report Agent</Tag><Tag color={statusMeta.color}>{statusMeta.label}</Tag>{updatedAt ? <span className="report-analysis-meta">更新时间：{updatedAt}</span> : null}</div></div>}>
      {status === 'processing' || status === 'pending' ? (
        <AnalysisLoading />
      ) : status === 'failed' ? (
        <Alert
          className="analysis-error-note"
          type="error"
          showIcon
          message="AI解读暂时失败，请稍后重试"
          description={analysis?.error_message || '生成解读时发生异常，您可以稍后重新分析。'}
          action={<Button size="small" onClick={() => void handleReanalyze()} loading={reanalyzing}>重新分析</Button>}
        />
      ) : status === 'completed' && data ? (
        <>
          <section className="analysis-summary-conclusion">
            <h4>总体结论</h4>
            <ReportOverallCard overall={data.overall} />
            <p>本次体检共识别 {data.summary.total_items || totalItems} 项指标，其中 {data.summary.normal_count} 项位于参考范围，{data.summary.attention_count} 项需要关注。</p>
          </section>
          <section className="analysis-section report-core-findings">
            <h4>核心发现</h4>
            {coreFindings.length ? <ul>{coreFindings.map((finding) => <li key={finding}>{finding}</li>)}</ul> : <p>暂无可展示的核心发现。</p>}
            <button className="analysis-link-btn" onClick={onViewAllIndicators}>查看全部指标 →</button>
          </section>
          <section className="analysis-section report-current-interpretation">
            <h4>当前指标解读{selectedName ? `：${selectedName}` : ''}</h4>
            <p>{selectedName ? selectedInterpretation || '暂无该指标的独立AI解读，可参考总体分析。' : '当前报告未识别到需要重点关注的指标。'}</p>
          </section>
          <ReportSuggestions items={data.suggestions} />
          <AnalysisBasis totalItems={totalItems} profileAvailable={Boolean(analysis?.meta?.profile_available)} model={analysis?.meta?.model ?? 'DeepSeek'} />
          {ocrUsed && <div className="analysis-disclaimer">本次体检报告部分指标来自 OCR 识别，AI 解读内容已提示核对原始报告。</div>}
          <div className="analysis-disclaimer">{data.disclaimer}</div>
        </>
      ) : (
        <div className="analysis-empty">
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="点击「AI智能解读」生成体检报告分析" />
        </div>
      )}
    </Card>
  )
}
