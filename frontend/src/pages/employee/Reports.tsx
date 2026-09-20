import { FileTextOutlined, LoadingOutlined, UploadOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Col, Empty, Modal, Progress, Row, Spin, Tag, Timeline, Upload, message } from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'
import { analyzeHealthCheckReport, getHealthCheckReport, getHealthCheckReportAnalysis, getHealthCheckReportItems, getHealthCheckReports, previewHealthCheckReport, reanalyzeHealthCheckReport, restartHealthCheckReportParsing, uploadHealthCheckReport, type HealthCheckIndicator, type HealthCheckReport, type ReportAnalysisData } from '../../api/healthReports'
import { AIReportAnalysis } from './reports-analysis/AIReportAnalysis'
import './reports.css'

const statusText = { uploaded: '已上传', parsing: '正在解析 PDF…', parsed: '解析完成', failed: '解析失败' } as const
const flagMeta = { normal: ['success', '正常'], high: ['error', '偏高'], low: ['warning', '偏低'], unknown: ['default', '待确认'] } as const
const sourceText = { text: '文字提取', table: '表格识别', ocr: 'OCR 识别', image: '图片识别' } as const

function readReferenceBound(item: HealthCheckIndicator, bound: 'min' | 'max') {
  const direct = bound === 'min' ? item.reference_min : item.reference_max
  if (direct !== null && direct !== undefined) return Number(direct)
  const values = (item.reference_text || '').match(/-?\d+(?:\.\d+)?/g)?.map(Number) || []
  return bound === 'min' ? values[0] : values[values.length - 1]
}

function abnormalDegree(item: HealthCheckIndicator) {
  const boundary = readReferenceBound(item, item.flag === 'high' ? 'max' : 'min')
  if (!Number.isFinite(boundary)) return null
  const difference = item.flag === 'high' ? item.value - boundary : boundary - item.value
  if (difference <= 0) return null
  const unit = item.unit ? ` ${item.unit}` : ''
  const direction = item.flag === 'high' ? '超过参考上限' : '低于参考下限'
  const percentage = boundary ? Math.abs(difference / boundary) * 100 : null
  return `${direction} ${difference.toFixed(3).replace(/\.?(0+)$/, '')}${unit}${percentage ? `（较参考${item.flag === 'high' ? '上限' : '下限'} +${percentage.toFixed(1)}%）` : ''}`
}

function relatedNormalItems(item: HealthCheckIndicator, indicators: HealthCheckIndicator[]) {
  const key = `${item.code} ${item.item_name}`.toUpperCase()
  const thyroidRelated = /FT3|游离三碘甲状腺原氨酸/.test(key)
    ? indicators.filter((candidate) => candidate.flag === 'normal' && /TSH|FT4|促甲状腺|游离甲状腺/.test(`${candidate.code} ${candidate.item_name}`.toUpperCase()))
    : []
  const sameCategory = indicators.filter((candidate) => candidate.flag === 'normal' && candidate.category === item.category)
  return Array.from(new Map([...thyroidRelated, ...sameCategory].map((candidate) => [candidate.id, candidate])).values()).slice(0, 3)
}

function groupIndicators(items: HealthCheckIndicator[]) {
  return Object.entries(items.reduce<Record<string, HealthCheckIndicator[]>>((groups, item) => {
    ;(groups[item.category] ||= []).push(item)
    return groups
  }, {}))
}

export function Reports() {
  const [reports, setReports] = useState<HealthCheckReport[]>([])
  const [selectedId, setSelectedId] = useState<string>()
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string>()
  const selected = useMemo(() => reports.find((report) => report.id === selectedId) || reports[0], [reports, selectedId])
  const abnormal = selected?.indicators.filter((item) => item.flag === 'high' || item.flag === 'low') || []
  const replaceReport = (next: HealthCheckReport) => setReports((rows) => rows.map((row) => row.id === next.id ? next : row))
  const loadReports = async () => {
    try {
      const rows = await getHealthCheckReports()
      setReports(rows)
      setSelectedId((current) => current && rows.some((row) => row.id === current) ? current : rows[0]?.id)
    } catch { message.error('体检报告加载失败') } finally { setLoading(false) }
  }
  useEffect(() => { void loadReports() }, [])
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])
  useEffect(() => {
    if (!selected || !['uploaded', 'parsing'].includes(selected.parse_status)) return
    const timer = window.setInterval(() => void (async () => {
      try {
        const report = await getHealthCheckReport(selected.id)
        if (report.parse_status === 'parsed') {
          const result = await getHealthCheckReportItems(report.id)
          replaceReport({ ...report, indicators: result.items, parse_mode: result.parse_mode as HealthCheckReport['parse_mode'], ocr_used: result.ocr_used, parse_warnings: result.warnings })
          message.success('PDF 解析完成，结构化指标已同步')
        } else replaceReport(report)
      } catch { /* polling will retry while parsing */ }
    })(), 1500)
    return () => window.clearInterval(timer)
  }, [selected?.id, selected?.parse_status])
  const [analysis, setAnalysis] = useState<ReportAnalysisData | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [selectedAbnormalItem, setSelectedAbnormalItem] = useState<HealthCheckIndicator | null>(null)
  const indicatorsRef = useRef<HTMLDivElement>(null)
  useEffect(() => { setSelectedAbnormalItem(abnormal[0] || null) }, [selected?.id, abnormal[0]?.id])
  useEffect(() => {
    if (!selected || selected.parse_status !== 'parsed') { setAnalysis(null); return }
    let cancelled = false
    getHealthCheckReportAnalysis(selected.id)
      .then((data) => {
        if (cancelled) return
        // "pending" without content means no analysis has ever run; treat as idle.
        setAnalysis(data.status === 'pending' && !data.analysis ? null : data)
      })
      .catch(() => { if (!cancelled) setAnalysis(null) })
    return () => { cancelled = true }
  }, [selected?.id, selected?.parse_status])
  useEffect(() => {
    if (!selected || !analysis || analysis.status !== 'processing') return
    const timer = window.setInterval(() => void (async () => {
      try {
        const data = await getHealthCheckReportAnalysis(selected.id)
        setAnalysis(data)
        if (data.status === 'completed' || data.status === 'failed') setAnalyzing(false)
      } catch { /* polling will retry while processing */ }
    })(), 1500)
    return () => window.clearInterval(timer)
  }, [selected?.id, analysis?.status])
  const startAnalysis = async () => {
    if (!selected) return
    setAnalyzing(true)
    try {
      const trigger = await analyzeHealthCheckReport(selected.id)
      if (trigger.status === 'completed') {
        const data = await getHealthCheckReportAnalysis(selected.id)
        setAnalysis(data)
        setAnalyzing(false)
        if (trigger.cached) message.success('已展示最近一次 AI 解读（指标未变化，直接使用缓存）')
      } else {
        setAnalysis({ analysis_id: trigger.analysis_id, report_id: selected.id, status: 'processing' })
      }
    } catch (error: any) {
      message.error(error?.response?.data?.detail || 'AI 解读触发失败')
      setAnalyzing(false)
    }
  }
  const restartAnalysis = async () => {
    if (!selected) return
    setAnalyzing(true)
    try {
      await reanalyzeHealthCheckReport(selected.id)
      setAnalysis({ analysis_id: '', report_id: selected.id, status: 'processing' })
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '重新分析失败')
      setAnalyzing(false)
    }
  }
  const scrollToIndicators = () => indicatorsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  const upload = async (file: File) => {
    setUploading(true)
    try {
      const report = await uploadHealthCheckReport(file)
      setReports((rows) => [report, ...rows]); setSelectedId(report.id)
      message.success('报告已上传，正在自动解析 PDF')
    } catch (error: any) { message.error(error?.response?.data?.detail || '报告上传失败') } finally { setUploading(false) }
    return false
  }
  const restartParsing = async () => {
    if (!selected) return
    try {
      const report = await restartHealthCheckReportParsing(selected.id)
      replaceReport(report)
      message.info('已重新提交 PDF 解析任务')
    } catch (error: any) { message.error(error?.response?.data?.detail || '重新解析失败') }
  }
  const openPreview = async () => {
    if (!selected) return
    setPreviewLoading(true)
    try {
      const file = await previewHealthCheckReport(selected.id)
      const nextUrl = URL.createObjectURL(file)
      setPreviewUrl((current) => { if (current) URL.revokeObjectURL(current); return nextUrl })
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '报告预览加载失败')
    } finally { setPreviewLoading(false) }
  }
  const closePreview = () => setPreviewUrl((current) => { if (current) URL.revokeObjectURL(current); return undefined })
  if (loading) return <div className="reports-loading"><Spin /></div>
  return <section className="reports-page">
    <div className="reports-heading"><p>上传文字、表格或扫描版 PDF，系统会自动选择原生文字、表格识别与 OCR 解析。</p><Upload accept="application/pdf,.pdf" showUploadList={false} beforeUpload={upload}><Button type="primary" icon={uploading ? <LoadingOutlined /> : <UploadOutlined />} loading={uploading}>上传体检报告 PDF</Button></Upload></div>
    {!selected ? <Card className="reports-empty"><Empty description="暂无体检报告"><Upload accept="application/pdf,.pdf" showUploadList={false} beforeUpload={upload}><Button type="primary">上传第一份 PDF 报告</Button></Upload></Empty></Card> : <>
      <Card className="report-latest"><div className="report-latest-icon"><FileTextOutlined /></div><div className="report-latest-main"><span>最新体检报告</span><h2>{selected.report_name}</h2><p>上传日期：{selected.report_date}　·　体检机构：{selected.hospital || '待报告解析后补充'}</p><Tag color={selected.parse_status === 'parsed' ? 'success' : selected.parse_status === 'failed' ? 'error' : 'processing'}>{statusText[selected.parse_status]}</Tag></div><div className="report-latest-actions">
        <Button type="primary" icon={<FileTextOutlined />} onClick={() => void startAnalysis()} loading={analyzing} disabled={selected.parse_status !== 'parsed'}>{selected.parse_status !== 'parsed' ? '等待指标解析' : analyzing || analysis?.status === 'processing' ? 'AI分析中...' : analysis?.status === 'completed' ? '查看AI解读' : analysis?.status === 'failed' ? '重新分析' : 'AI智能解读'}</Button>
        <Button onClick={() => void openPreview()} loading={previewLoading} disabled={!selected.file_name}>查看报告</Button>
      </div></Card>
      {selected.parse_status === 'failed' && <Alert className="report-parser-note" type="error" showIcon message="PDF 解析失败" description={<div className="report-progress"><span>{selected.parse_error || '请确认 PDF 未加密或损坏后重新解析。'}</span><Button size="small" onClick={() => void restartParsing()}>重新解析</Button></div>} />}
      {['uploaded', 'parsing'].includes(selected.parse_status) && <Alert className="report-parser-note" type="info" showIcon message="正在自动解析体检报告" description={<div className="report-progress"><Progress percent={selected.parse_progress} status="active" strokeColor="#16a34a" /><span>{selected.parse_status === 'uploaded' ? '报告已入队，正在分析 PDF 类型' : selected.parse_progress < 35 ? '正在读取原生文字与图片区域' : selected.parse_progress < 80 ? '正在提取文字、识别表格与 OCR 扫描区域' : '正在提取体检指标并保存结果'}</span>{selected.parse_status === 'uploaded' && <Button size="small" onClick={() => void restartParsing()}>重新开始解析</Button>}</div>} />}
      {selected.parse_status === 'parsed' && <Alert className="report-parser-note" type="success" showIcon message={`解析完成：已识别 ${selected.indicators.length} 项体检指标`} description={<span>解析模式：{selected.parse_mode || 'TEXT'}{selected.ocr_used ? ' · 已使用 OCR' : ''}{selected.parse_warnings.length ? ` · ${selected.parse_warnings.join('；')}` : ''}</span>} />}
      <Row gutter={[16, 16]} className="reports-main-grid"><Col xs={24} xl={7}><Card title="历史体检记录" className="report-history"><Timeline items={reports.map((report) => ({ color: report.id === selected.id ? '#16a34a' : '#cbd5e1', children: <button className={`report-history-item ${report.id === selected.id ? 'active' : ''}`} onClick={() => setSelectedId(report.id)}><b>{report.report_date}</b><span>{report.report_name}</span><small>{statusText[report.parse_status]}</small></button> }))} /></Card></Col><Col xs={24} xl={17}><Card title="检查指标" className="report-indicators"><div ref={indicatorsRef}>{selected.indicators.length ? groupIndicators(selected.indicators).map(([category, items]) => <section key={category} className="indicator-category"><h3>{category}</h3><div className="indicator-grid">{items.map((item) => { const [color, text] = flagMeta[item.flag]; return <div className={`indicator-item ${item.flag}`} key={item.id}><span>{item.item_name}</span><strong>{item.value_text || item.value} <small>{item.unit}</small></strong><Tag color={color}>{text}</Tag><small>参考范围：{item.reference_text || '报告未提供'}</small><small>来源：{sourceText[item.source_type] || '文字提取'}{item.confidence !== null && item.confidence !== undefined ? ` · 可信度 ${Math.round(item.confidence * 100)}%` : item.source_type === 'ocr' ? ' · 建议人工确认' : ''}</small></div> })}</div></section>) : <Empty description={selected.parse_status === 'parsed' ? '未识别到可可靠提取的结构化指标' : '等待 PDF 解析完成'} />}</div></Card></Col></Row>
      <Row gutter={[16, 16]} align="stretch" className="reports-bottom-grid" style={{ display: 'flex', alignItems: 'stretch' }}>
        <Col xs={24} xl={10} style={{ display: 'flex' }}>
          <Card title="重点异常指标" className="report-attention report-key-abnormal" style={{ flex: 1, width: '100%' }}>
            {abnormal.length ? <>
              <section className="abnormal-overview">
                <div><small>异常概览</small><strong>{abnormal.length} 项</strong></div>
                <div><small>重点关注系统</small><b>{Array.from(new Set(abnormal.map((item) => item.category))).join('、')}</b></div>
                <Tag color="warning">需要关注</Tag>
              </section>
              <div className="abnormal-item-list">
                {abnormal.map((item) => {
                  const active = selectedAbnormalItem?.id === item.id
                  const degree = abnormalDegree(item)
                  const related = relatedNormalItems(item, selected.indicators)
                  return <button type="button" key={item.id} className={`abnormal-item-card ${item.flag} ${active ? 'selected' : ''}`} onClick={() => setSelectedAbnormalItem(item)}>
                    <div className="abnormal-item-head"><b>{item.item_name}</b><Tag color={item.flag === 'high' ? 'error' : 'warning'}>{item.flag === 'high' ? '偏高' : '偏低'}</Tag></div>
                    <strong className="abnormal-item-value">{item.value_text || item.value} <small>{item.unit || ''}</small></strong>
                    <span>参考范围：{item.reference_text || '请以原始报告为准'}</span>
                    <span>所属系统：{item.category || '未分类'}</span>
                    <span>来源：{sourceText[item.source_type] || 'OCR 识别'}</span>
                    {degree ? <em>{degree}</em> : null}
                    <div className="related-normal"><small>相关指标</small>{related.length ? related.map((relatedItem) => <span key={relatedItem.id}>{relatedItem.item_name} 正常</span>) : <span>暂无相关指标</span>}</div>
                  </button>
                })}
              </div>
              <p className="abnormal-ocr-disclaimer">OCR识别结果可能存在误差，重要异常指标建议与原始报告核对。</p>
            </> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂未发现偏高或偏低的已识别指标" />}
          </Card>
        </Col>
        <Col xs={24} xl={14} style={{ display: 'flex' }}><AIReportAnalysis reportId={selected.id} totalItems={selected.indicators.length} ocrUsed={selected.ocr_used} analysis={analysis} selectedItem={selectedAbnormalItem} onReanalyze={() => void restartAnalysis()} onViewAllIndicators={scrollToIndicators} /></Col>
      </Row>
      <Modal open={Boolean(previewUrl)} title={selected.report_name} footer={<Button onClick={closePreview}>关闭预览</Button>} onCancel={closePreview} width="min(1180px, 92vw)" destroyOnClose styles={{ body: { height: 'calc(100vh - 220px)', padding: 0 } }}><iframe className="report-pdf-preview" title={`${selected.report_name} PDF 预览`} src={previewUrl} /></Modal>
    </>}
  </section>
}
