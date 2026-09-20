import { CheckCircleOutlined, ClockCircleOutlined, FileDoneOutlined, FileTextOutlined, MedicineBoxOutlined, ReloadOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { Button, Card, Col, Drawer, Empty, Form, Input, Modal, Progress, Row, Select, Skeleton, Spin, Table, Tag, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import * as echarts from 'echarts'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  getCheckup, getCheckups, getCheckupSummary, reparseCheckup, reviewIndicator,
  type CheckupDetail, type CheckupIndicator, type CheckupListItem, type CheckupSummary,
} from '../../api/checkups'
import './checkup-management.css'

const STATUS_COLORS: Record<string, string> = { 待解析: 'default', 解析中: 'processing', 解析完成: 'green', 部分解析: 'cyan', 待人工确认: 'orange', 解析失败: 'red' }
const SOURCE_TYPE_LABELS: Record<string, string> = { text: 'TEXT', table: 'TABLE', ocr: 'OCR', ocr_layout: 'OCR_LAYOUT' }
const FLAG_LABELS: Record<string, string> = { high: '偏高', low: '偏低', normal: '正常', unknown: '—' }

function useChart(id: string, option: echarts.EChartsOption | null, deps: unknown[]) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current || !option) return
    const chart = echarts.init(ref.current)
    chart.setOption(option)
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps
  return ref
}

export function CheckupManagement() {
  const [summary, setSummary] = useState<CheckupSummary | null>(null)
  const [items, setItems] = useState<CheckupListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ period: '30d', department: undefined as string | undefined, status: undefined as string | undefined })
  const [detail, setDetail] = useState<CheckupDetail | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [reparseLoading, setReparseLoading] = useState(false)
  const [reviewTarget, setReviewTarget] = useState<CheckupIndicator | null>(null)
  const [reviewMode, setReviewMode] = useState<'confirm' | 'modify' | 'ignore'>('confirm')
  const [reviewValue, setReviewValue] = useState('')
  const [reviewNote, setReviewNote] = useState('')

  const load = useCallback(async (next = filters) => {
    setLoading(true)
    try {
      const [summaryResult, itemsResult] = await Promise.all([getCheckupSummary(next.period), getCheckups(next)])
      setSummary(summaryResult)
      setItems(itemsResult)
    } catch { message.error('体检数据加载失败') } finally { setLoading(false) }
  }, [filters])
  useEffect(() => { void load() }, [load])

  const openDetail = async (id: string) => {
    try { setDetail(await getCheckup(id)); setDrawerOpen(true) }
    catch { message.error('报告详情加载失败') }
  }

  const refreshAfter = async (id: string) => {
    setDetail(await getCheckup(id))
    await load()
  }

  const kpis = [
    { icon: <FileTextOutlined />, label: '体检报告总数', value: summary?.stats.total_reports ?? 0, note: '近 30 天上传报告', color: '#16A34A' },
    { icon: <CheckCircleOutlined />, label: '解析完成', value: summary?.stats.parsed_count ?? 0, note: '成功解析的报告', color: '#0EA5B7' },
    { icon: <ClockCircleOutlined />, label: '待人工确认', value: summary?.stats.pending_review_reports ?? 0, note: '含待确认指标的报告', color: '#F59E0B' },
    { icon: <MedicineBoxOutlined />, label: '存在异常', value: summary?.stats.abnormal_reports ?? 0, note: '至少 1 项异常指标', color: '#EF4444' },
  ]

  const statusDistRef = useChart('status-dist', summary?.status_distribution.length ? {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 份 ({d}%)' },
    legend: { bottom: 0, icon: 'circle', itemWidth: 8, itemHeight: 8, textStyle: { color: '#64748B', fontSize: 11 } },
    color: ['#16A34A', '#0EA5B7', '#F59E0B', '#EF4444', '#94A3B8'],
    series: [{ type: 'pie', radius: ['45%', '70%'], center: ['50%', '44%'], label: { show: false }, data: summary!.status_distribution.map(item => ({ name: item.label, value: item.count })) }],
  } as echarts.EChartsOption : null, [summary])

  const methodDistRef = useChart('method-dist', summary?.method_distribution.length ? {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (params: any) => `${params[0].name}：${params[0].value} 份` },
    grid: { left: 8, right: 36, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: '#EEF2F6' } }, axisLabel: { color: '#7D91AA' } },
    yAxis: { type: 'category', data: summary!.method_distribution.map(item => item.label).reverse(), axisLabel: { color: '#475569', fontSize: 11 }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{ type: 'bar', barWidth: 14, data: summary!.method_distribution.map(item => item.count).reverse(), itemStyle: { color: '#16A34A', borderRadius: [0, 7, 7, 0] }, label: { show: true, position: 'right', color: '#94A3B8', fontSize: 11 } }],
  } as echarts.EChartsOption : null, [summary])

  const pendingReviews = useMemo(() => items.filter(item => item.pending_review).slice(0, 5), [items])

  const columns: ColumnsType<CheckupListItem> = [
    { title: '员工', dataIndex: 'employee_name', key: 'employee_name', width: 110, render: (value, row) => <span className="c-employee"><b>{value ?? '—'}</b><small>{row.employee_no ?? ''}</small></span> },
    { title: '报告名称', dataIndex: 'report_name', key: 'report_name', render: (value) => <span className="c-report-name">{value}</span> },
    { title: '体检机构', dataIndex: 'hospital', key: 'hospital', width: 150, render: (value) => value ?? '—' },
    { title: '上传时间', dataIndex: 'uploaded_at', key: 'uploaded_at', width: 140, render: (value) => <span className="c-muted">{new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })}</span> },
    { title: '解析方式', dataIndex: 'parse_mode', key: 'parse_mode', width: 110, render: (value, row) => <Tag color="green" style={{ margin: 0 }}>{row.ocr_used ? 'OCR' : value ?? row.parse_method ?? '—'}</Tag> },
    { title: '指标数', dataIndex: 'indicator_count', key: 'indicator_count', width: 74, align: 'center', render: (value) => <span className="c-num">{value}</span> },
    { title: '异常数', dataIndex: 'abnormal_count', key: 'abnormal_count', width: 74, align: 'center', render: (value) => value > 0 ? <Tag color="red">{value} 项</Tag> : <span className="c-muted">0</span> },
    { title: '解析状态', dataIndex: 'display_status', key: 'display_status', width: 104, render: (value) => <Tag color={STATUS_COLORS[value] ?? 'default'}>{value}</Tag> },
    { title: '操作', key: 'action', width: 150, render: (_, record) => (
      <span className="c-actions">
        <Button type="link" size="small" onClick={() => void openDetail(record.id)}>查看</Button>
        {record.parse_status === 'failed' && <Button type="link" size="small" icon={<ReloadOutlined />} onClick={() => void handleReparse(record)}>重新解析</Button>}
        {record.pending_review && <Button type="link" size="small" onClick={() => void openDetail(record.id)}>处理确认</Button>}
      </span>
    ) },
  ]

  const handleReparse = async (record: CheckupListItem) => {
    setReparseLoading(true)
    try {
      const updated = await reparseCheckup(record.id)
      setDetail(updated)
      message.success('已重新加入解析队列')
      await load()
    } catch (error: any) { message.error(error?.response?.data?.detail || '重新解析失败') } finally { setReparseLoading(false) }
  }

  const submitReview = async () => {
    if (!reviewTarget) return
    try {
      if (reviewMode === 'modify' && !reviewValue) { message.warning('请输入修正后的数值'); return }
      await reviewIndicator(reviewTarget.id, {
        action: reviewMode,
        reviewed_value: reviewMode === 'modify' ? Number(reviewValue) : undefined,
        note: reviewNote || undefined,
      })
      message.success('已保存确认结果')
      setReviewTarget(null)
      setReviewValue('')
      setReviewNote('')
      if (detail) await refreshAfter(detail.id)
    } catch (error: any) { message.error(error?.response?.data?.detail || '操作失败') }
  }

  const summaryDiag = (detail?.parse_warnings ?? null) as Record<string, any> | null

  return <section className="c-page checkup-management-page">
    <p className="c-subtitle">统一管理企业体检报告、解析进度、识别质量与异常指标流转。</p>

    <Row gutter={[16, 16]} className="c-kpi-row">
      {kpis.map((item) => (
        <Col xs={12} xl={6} key={item.label}>
          <Card className="c-kpi" style={{ borderLeft: `3px solid ${item.color}` }}>
            <div className="c-kpi-icon" style={{ color: item.color, background: `${item.color}14` }}>{item.icon}</div>
            <div className="c-kpi-body"><small>{item.label}</small><b>{item.value}</b><p>{item.note}</p></div>
          </Card>
        </Col>
      ))}
    </Row>

    <Card className="c-card" title="体检报告管理">
      <div className="c-filters">
        <Select value={filters.department ?? 'all'} style={{ width: 140 }} listHeight={300} filterOption={false} placeholder="全部部门" options={[{ value: 'all', label: '全部部门' }, ...(summary?.departments ?? []).map(item => ({ value: item, label: item }))]} onChange={(value) => setFilters({ ...filters, department: value === 'all' ? undefined : value })} />
        <Select value={filters.status ?? 'all'} style={{ width: 130 }} options={[{ value: 'all', label: '全部状态' }, { value: '待解析', label: '待解析' }, { value: '解析中', label: '解析中' }, { value: '解析完成', label: '解析完成' }, { value: '待人工确认', label: '待人工确认' }, { value: '解析失败', label: '解析失败' }]} onChange={(value) => setFilters({ ...filters, status: value === 'all' ? undefined : value })} />
        <Select value={filters.period} style={{ width: 96 }} options={[{ value: '7d', label: '近7天' }, { value: '30d', label: '近30天' }, { value: '90d', label: '近90天' }]} onChange={(value) => setFilters({ ...filters, period: value })} />
      </div>
      {loading ? <Skeleton active paragraph={{ rows: 6 }} /> : items.length
        ? <Table rowKey="id" columns={columns} dataSource={items} pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 份` }} size="middle" />
        : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无体检报告" />}
    </Card>

    <Row gutter={[16, 16]} className="c-bottom-row">
      <Col xs={24} lg={12}>
        <Card className="c-card" title="解析质量概览">
          {summary?.status_distribution.length ? <div className="c-quality">
            <div ref={statusDistRef} className="c-chart c-chart-donut" />
            <div className="c-dist-list">
              {summary.status_distribution.map(item => (
                <div className="c-dist-item" key={item.label}>
                  <span className="c-dot" style={{ background: { 解析完成: '#16A34A', 部分解析: '#0EA5B7', 待人工确认: '#F59E0B', 解析失败: '#EF4444', 解析中: '#94A3B8', 待解析: '#94A3B8' }[item.label] ?? '#94A3B8' }} />
                  <span>{item.label}</span><span className="c-dist-count">{item.count} 份 · {item.percent}%</span>
                </div>
              ))}
            </div>
          </div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无数据" />}
          <div className="c-quality-title">解析方式分布</div>
          {summary?.method_distribution.length ? <div ref={methodDistRef} className="c-chart c-chart-bar" /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无数据" />}
        </Card>
      </Col>
      <Col xs={24} lg={12}>
        <Card className="c-card" title="待人工确认">
          {pendingReviews.length ? pendingReviews.map((report) => (
            <div className="c-review-item" key={report.id}>
              <div className="c-review-main">
                <b>{report.employee_name ?? '员工'}</b>
                <span className="c-review-report">{report.report_name}</span>
                <Tag color="orange">{report.abnormal_count} 项异常指标待确认</Tag>
              </div>
              <Button size="small" type="primary" ghost onClick={() => void openDetail(report.id)}>处理</Button>
            </div>
          )) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无待人工确认内容" />}
        </Card>
      </Col>
    </Row>

    <Drawer title="体检报告详情" width={640} open={drawerOpen} onClose={() => setDrawerOpen(false)}>
      {detail ? <div className="c-detail">
        <div className="c-detail-head">
          <h3>{detail.report_name}</h3>
          <Tag color={STATUS_COLORS[detail.display_status] ?? 'default'}>{detail.display_status}</Tag>
        </div>
        <div className="c-detail-meta">
          <span>员工编号</span><b>{detail.employee_no ?? '—'}</b>
          <span>体检机构</span><b>{detail.hospital ?? '—'}</b>
          <span>上传时间</span><b>{new Date(detail.uploaded_at).toLocaleString('zh-CN')}</b>
          <span>解析方式</span><b>{detail.parse_mode ?? detail.parse_method ?? '—'}{detail.ocr_used ? ' + OCR' : ''}</b>
        </div>

        <div className="c-section-title">① 解析摘要</div>
        <div className="c-summary-grid">
          <span>PDF页数</span><b>{summaryDiag?.page_count ?? '—'}</b>
          <span>识别指标数</span><b>{detail.indicator_count} 项</b>
          <span>异常指标数</span><b className="c-abnormal-num">{detail.abnormal_count} 项</b>
          <span>OCR引擎</span><b>{summaryDiag?.selected_ocr_engine ?? (detail.ocr_used ? 'RapidOCR / PaddleOCR' : '—')}</b>
          <span>解析模式</span><b>{detail.parse_mode ?? '—'}</b>
          <span>解析耗时</span><b>{summaryDiag?.parse_duration_s ? `${summaryDiag.parse_duration_s}s` : '—'}</b>
        </div>

        <div className="c-section-title">② 检查指标</div>
        <Table
          rowKey="id" size="small" pagination={false}
          dataSource={detail.items}
          columns={[
            { title: '指标', dataIndex: 'item_name', key: 'item_name', render: (value) => <span className="c-item-name">{value}</span> },
            { title: '结果', key: 'value', width: 92, render: (_, row) => <span className={row.flag === 'normal' ? 'c-value' : 'c-value c-value-abnormal'}>{row.reviewed_value ?? row.value_text ?? row.value}</span> },
            { title: '单位', dataIndex: 'unit', key: 'unit', width: 70, render: (value) => value ?? '—' },
            { title: '参考范围', dataIndex: 'reference_text', key: 'reference_text', width: 96, render: (value) => <span className="c-muted">{value ?? '—'}</span> },
            { title: '状态', dataIndex: 'flag', key: 'flag', width: 70, render: (value) => value === 'normal' ? <Tag color="green" style={{ margin: 0 }}>正常</Tag> : <Tag color={value === 'high' ? 'red' : 'orange'} style={{ margin: 0 }}>{FLAG_LABELS[value]}</Tag> },
            { title: '来源', dataIndex: 'source_type', key: 'source_type', width: 86, render: (value) => <Tag color="blue" style={{ margin: 0 }}>{SOURCE_TYPE_LABELS[value] ?? value}</Tag> },
          ]}
        />
        <div className="c-review-list">
          {detail.items.filter(item => item.flag !== 'normal').map((item) => (
            <div className="c-review-row" key={item.id}>
              <span>{item.item_name}：<b>{item.value_text ?? item.value}</b> {item.unit ?? ''}</span>
              {item.review_status ? <Tag color="green">已{item.review_status === 'confirmed' ? '确认' : item.review_status === 'modified' ? '修正' : '忽略'}</Tag>
                : <span className="c-review-actions">
                  <Button size="small" onClick={() => { setReviewTarget(item); setReviewMode('confirm') }}>确认</Button>
                  <Button size="small" onClick={() => { setReviewTarget(item); setReviewMode('modify'); setReviewValue(String(item.value_text ?? item.value)) }}>修改</Button>
                  <Button size="small" onClick={() => { setReviewTarget(item); setReviewMode('ignore') }}>忽略</Button>
                </span>}
            </div>
          ))}
        </div>

        <div className="c-section-title">③ 解析日志摘要</div>
        <div className="c-log-grid">
          <span>RapidOCR 字符</span><b>{summaryDiag?.rapidocr_chars ?? '—'}</b>
          <span>PaddleOCR 字符</span><b>{summaryDiag?.paddleocr_chars ?? '—'}</b>
          <span>表格数</span><b>{summaryDiag?.table_count ?? '—'}</b>
          <span>候选/接受指标</span><b>{summaryDiag?.candidate_items ?? '—'} / {summaryDiag?.accepted_items ?? '—'}</b>
          <span>触发 Fallback</span><b>{summaryDiag?.selected_ocr_engine === 'paddleocr' ? '是' : '否'}</b>
          {detail.parse_error && <><span>失败原因</span><b className="c-error-text">{detail.parse_error}</b></>}
        </div>
        {detail.parse_status === 'failed' && <Button type="primary" icon={<ReloadOutlined />} loading={reparseLoading} block style={{ marginTop: 16 }} onClick={() => void handleReparse(detail)}>重新解析</Button>}
      </div> : <div className="c-detail-loading"><Spin /></div>}
    </Drawer>

    <Modal title={reviewMode === 'confirm' ? '确认指标' : reviewMode === 'modify' ? '修改指标' : '忽略指标'} open={Boolean(reviewTarget)} onCancel={() => setReviewTarget(null)} onOk={() => void submitReview()}>
      {reviewTarget && <Form layout="vertical">
        <div className="c-review-original">原始识别：<b>{reviewTarget.value_text ?? reviewTarget.value}</b> {reviewTarget.unit ?? ''}（保留原值，修改不覆盖）</div>
        {reviewMode === 'modify' && <Form.Item label="修正值"><Input value={reviewValue} onChange={(e) => setReviewValue(e.target.value)} placeholder="输入人工核对后的数值" /></Form.Item>}
        <Form.Item label="备注（可选）"><Input value={reviewNote} onChange={(e) => setReviewNote(e.target.value)} placeholder="确认说明 / 修正原因" /></Form.Item>
      </Form>}
    </Modal>
  </section>
}
