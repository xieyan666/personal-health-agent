import { AlertOutlined, CheckCircleOutlined, ClockCircleOutlined, FireOutlined, SafetyOutlined } from '@ant-design/icons'
import { Button, Card, Col, Drawer, Empty, Form, Input, Modal, Row, Select, Skeleton, Table, Tag, Timeline, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useCallback, useEffect, useState } from 'react'
import {
  getRiskCase, getRiskCaseOptions, getRiskCases, linkRiskCasePlan, linkRiskCaseService,
  updateRiskCaseStatus,
  type PlanOption, type RiskCaseDetail, type RiskCaseItem, type RiskCaseListResponse, type ServiceOption,
} from '../../api/riskCases'
import './risk-operations.css'

const RISK_TYPE_LABELS: Record<string, string> = { sleep: '睡眠不足', exercise: '运动不足', abnormal: '体检指标异常', stress: '心理压力偏高', heart_rate: '心率异常趋势' }
const SOURCE_LABELS: Record<string, string> = { Wearable: '健康趋势', HealthCheck: '体检报告', MentalCheckin: '心理打卡', RiskTrend: '风险趋势' }
const STATUS_LABELS: Record<string, string> = { pending: '待处理', confirmed: '已确认', processing: '处理中', observing: '持续观察', resolved: '已解决', ignored: '已忽略' }
const ACTION_LABELS: Record<string, string> = { confirm: '确认风险', link_plan: '关联健康计划', link_service: '关联健康服务', observe: '设置持续观察', resolve: '标记已解决', ignore: '忽略风险' }
const STATUS_COLORS: Record<string, string> = { pending: 'orange', confirmed: 'blue', processing: 'cyan', observing: 'geekblue', resolved: 'green', ignored: 'default' }
const LEVEL_COLORS: Record<string, string> = { high: 'red', medium: 'orange', low: 'green' }
const LEVEL_LABELS: Record<string, string> = { high: '高风险', medium: '中风险', low: '低风险' }

export function RiskOperations() {
  const [data, setData] = useState<RiskCaseListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ period: '30d', department: undefined as string | undefined, level: undefined as string | undefined, source: undefined as string | undefined, status: undefined as string | undefined })
  const [detail, setDetail] = useState<RiskCaseDetail | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [options, setOptions] = useState<{ services: ServiceOption[]; plans: PlanOption[] }>({ services: [], plans: [] })
  const [planModal, setPlanModal] = useState(false)
  const [serviceModal, setServiceModal] = useState(false)
  const [observeModal, setObserveModal] = useState(false)
  const [resolveModal, setResolveModal] = useState(false)
  const [ignoreModal, setIgnoreModal] = useState(false)
  const [pendingPlan, setPendingPlan] = useState<string>()
  const [pendingService, setPendingService] = useState<string>()
  const [observeDays, setObserveDays] = useState(14)
  const [resolveNote, setResolveNote] = useState('')
  const [ignoreReason, setIgnoreReason] = useState('数据异常')

  const load = useCallback(async (next = filters) => {
    setLoading(true)
    try {
      const result = await getRiskCases(next)
      setData(result)
    } catch { message.error('风险数据加载失败') } finally { setLoading(false) }
  }, [filters])
  useEffect(() => { void load() }, [load])

  const openDetail = async (item: RiskCaseItem) => {
    try {
      const result = await getRiskCase(item.id)
      setDetail(result)
      setDrawerOpen(true)
      const opts = await getRiskCaseOptions(item.id)
      setOptions(opts)
    } catch { message.error('风险详情加载失败') }
  }

  const refreshDetail = async (caseId: string) => {
    const updated = await getRiskCase(caseId)
    setDetail(updated)
    await load()
  }

  const act = async (action: () => Promise<unknown>, successMessage: string, caseId?: string) => {
    try {
      await action()
      message.success(successMessage)
      if (caseId) await refreshDetail(caseId)
      else await load()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '操作失败，请重试')
    }
  }

  const kpis = [
    { icon: <AlertOutlined />, label: '待处理风险', value: data?.stats.pending ?? 0, color: '#F59E0B' },
    { icon: <FireOutlined />, label: '高优先级风险', value: data?.stats.high_priority ?? 0, color: '#EF4444' },
    { icon: <ClockCircleOutlined />, label: '处理中', value: data?.stats.processing ?? 0, color: '#0EA5B7' },
    { icon: <CheckCircleOutlined />, label: '本月已关闭', value: data?.stats.closed_this_month ?? 0, color: '#16A34A' },
  ]

  const columns: ColumnsType<RiskCaseItem> = [
    { title: '风险类型', dataIndex: 'risk_type', key: 'risk_type', render: (v: string) => <b className="r-risk-name">{RISK_TYPE_LABELS[v] ?? v}</b> },
    { title: '风险等级', dataIndex: 'risk_level', key: 'risk_level', width: 92, render: (v: string) => <Tag color={LEVEL_COLORS[v] ?? 'default'}>{LEVEL_LABELS[v] ?? v}</Tag> },
    { title: '所属部门', dataIndex: 'department', key: 'department', width: 110, render: (v: string | null) => v ?? '—' },
    { title: '数据来源', dataIndex: 'source', key: 'source', width: 110, render: (v: string | null) => <span className="r-source">{v ? SOURCE_LABELS[v] ?? v : '—'}</span> },
    { title: '发现时间', dataIndex: 'created_at', key: 'created_at', width: 150, render: (v: string) => <span className="r-time">{new Date(v).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })}</span> },
    { title: '当前状态', dataIndex: 'status', key: 'status', width: 100, render: (v: string) => <Tag color={STATUS_COLORS[v] ?? 'default'}>{STATUS_LABELS[v] ?? v}</Tag> },
    { title: '操作', key: 'action', width: 80, render: (_, record) => <Button type="link" size="small" onClick={() => void openDetail(record)}>查看</Button> },
  ]

  return <section className="r-page risk-operations-page">
    <p className="r-subtitle">集中处理企业员工健康风险预警、干预与跟踪任务。</p>
    <Row gutter={[16, 16]} className="r-kpi-row">
      {kpis.map((item) => (
        <Col xs={12} xl={6} key={item.label}>
          <Card className="r-kpi" style={{ borderLeft: `3px solid ${item.color}` }}>
            <div className="r-kpi-icon" style={{ color: item.color, background: `${item.color}14` }}>{item.icon}</div>
            <div className="r-kpi-body"><small>{item.label}</small><b>{item.value}</b></div>
          </Card>
        </Col>
      ))}
    </Row>

    <Card className="r-card">
      <div className="r-filters">
        <Select value={filters.department ?? 'all'} style={{ width: 140 }} listHeight={300} filterOption={false} placeholder="全部部门" options={[{ value: 'all', label: '全部部门' }, ...(data?.departments ?? []).map(item => ({ value: item, label: item }))]} onChange={(value) => setFilters({ ...filters, department: value === 'all' ? undefined : value })} />
        <Select value={filters.level ?? 'all'} style={{ width: 120 }} options={[{ value: 'all', label: '全部风险等级' }, { value: 'high', label: '高风险' }, { value: 'medium', label: '中风险' }, { value: 'low', label: '低风险' }]} onChange={(value) => setFilters({ ...filters, level: value === 'all' ? undefined : value })} />
        <Select value={filters.source ?? 'all'} style={{ width: 120 }} options={[{ value: 'all', label: '全部来源' }, ...Object.entries(SOURCE_LABELS).map(([value, label]) => ({ value, label }))]} onChange={(value) => setFilters({ ...filters, source: value === 'all' ? undefined : value })} />
        <Select value={filters.status ?? 'all'} style={{ width: 120 }} options={[{ value: 'all', label: '全部状态' }, ...Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label }))]} onChange={(value) => setFilters({ ...filters, status: value === 'all' ? undefined : value })} />
        <Select value={filters.period} style={{ width: 96 }} options={[{ value: '7d', label: '近7天' }, { value: '30d', label: '近30天' }, { value: '90d', label: '近90天' }]} onChange={(value) => setFilters({ ...filters, period: value })} />
      </div>
      {loading ? <Skeleton active paragraph={{ rows: 6 }} /> : data?.items.length
        ? <Table rowKey="id" columns={columns} dataSource={data.items} pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条` }} size="middle" />
        : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无风险事件" />}
    </Card>

    <Drawer title="风险详情" width={520} open={drawerOpen} onClose={() => setDrawerOpen(false)}>
      {detail && <div className="r-detail">
        <div className="r-detail-header">
          <h3>{RISK_TYPE_LABELS[detail.risk_type] ?? detail.risk_type}</h3>
          <Tag color={LEVEL_COLORS[detail.risk_level]}>{LEVEL_LABELS[detail.risk_level] ?? detail.risk_level}</Tag>
          <Tag color={STATUS_COLORS[detail.status]}>{STATUS_LABELS[detail.status] ?? detail.status}</Tag>
        </div>
        <div className="r-detail-grid">
          <span>所属部门</span><b>{detail.department ?? '—'}</b>
          <span>发现时间</span><b>{new Date(detail.created_at).toLocaleString('zh-CN')}</b>
          <span>数据来源</span><b>{detail.source ? SOURCE_LABELS[detail.source] ?? detail.source : '—'}</b>
          {detail.assigned_plan_id && <><span>关联计划</span><b className="r-linked">已关联</b></>}
          {detail.assigned_service_id && <><span>关联服务</span><b className="r-linked">已关联</b></>}
          {detail.next_review_at && <><span>下次复查</span><b>{new Date(detail.next_review_at).toLocaleDateString('zh-CN')}</b></>}
        </div>
        <div className="r-summary"><SafetyOutlined /> {detail.risk_summary ?? '暂无风险说明'}</div>

        <div className="r-actions">
          {detail.status === 'pending' && <Button type="primary" onClick={() => void act(() => updateRiskCaseStatus(detail.id, { action: 'confirm', note: '确认风险' }), '已确认风险', detail.id)}>确认风险</Button>}
          {['confirmed', 'processing'].includes(detail.status) && <>
            <Button onClick={() => setPlanModal(true)}>关联健康计划</Button>
            <Button onClick={() => setServiceModal(true)}>关联健康服务</Button>
            <Button onClick={() => setObserveModal(true)}>持续观察</Button>
          </>}
          {!['resolved', 'ignored'].includes(detail.status) && <>
            <Button onClick={() => setResolveModal(true)}>标记已解决</Button>
            <Button danger onClick={() => setIgnoreModal(true)}>忽略</Button>
          </>}
        </div>

        <div className="r-timeline-title">处理记录</div>
        {detail.actions.length
          ? <Timeline items={detail.actions.slice().reverse().map((action) => ({
              children: <div className="r-timeline-item">
                <b>{ACTION_LABELS[action.action] ?? action.action}</b>
                <span>{action.note && ` · ${action.note}`}</span>
                <small>{action.actor_name ?? '系统'} · {new Date(action.created_at).toLocaleString('zh-CN')}</small>
              </div>,
            }))} />
          : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无处理记录" />}
      </div>}
    </Drawer>

    <Modal title="关联健康计划" open={planModal} onCancel={() => setPlanModal(false)} onOk={() => {
      if (!pendingPlan || !detail) return
      void act(() => linkRiskCasePlan(detail.id, pendingPlan), '已关联健康计划', detail.id).then(() => { setPlanModal(false); setPendingPlan(undefined) })
    }} okButtonProps={{ disabled: !pendingPlan }}>
      {options.plans.length
        ? <Select style={{ width: '100%' }} placeholder="选择该员工的健康计划" value={pendingPlan} onChange={setPendingPlan} options={options.plans.map(plan => ({ value: plan.id, label: `${plan.plan_name}（${STATUS_LABELS[plan.status] ?? plan.status}）` }))} />
        : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="该员工暂无健康计划，可先在健康计划页面生成" />}
    </Modal>

    <Modal title="关联健康服务" open={serviceModal} onCancel={() => setServiceModal(false)} onOk={() => {
      if (!pendingService || !detail) return
      void act(() => linkRiskCaseService(detail.id, pendingService), '已关联健康服务', detail.id).then(() => { setServiceModal(false); setPendingService(undefined) })
    }} okButtonProps={{ disabled: !pendingService }}>
      <Select style={{ width: '100%' }} placeholder="选择数据库中的健康服务" value={pendingService} onChange={setPendingService} options={options.services.map((service: ServiceOption) => ({ value: service.id, label: `${service.name}（${service.category}）` }))} />
    </Modal>

    <Modal title="持续观察" open={observeModal} onCancel={() => setObserveModal(false)} onOk={() => {
      if (!detail) return
      void act(() => updateRiskCaseStatus(detail.id, { action: 'observe', next_review_days: observeDays }), `已设置持续观察（${observeDays} 天后复查）`, detail.id).then(() => setObserveModal(false))
    }}>
      <Select style={{ width: '100%' }} value={observeDays} onChange={setObserveDays} options={[{ value: 7, label: '7 天' }, { value: 14, label: '14 天' }, { value: 30, label: '30 天' }]} />
    </Modal>

    <Modal title="标记已解决" open={resolveModal} onCancel={() => setResolveModal(false)} onOk={() => {
      if (!detail) return
      void act(() => updateRiskCaseStatus(detail.id, { action: 'resolve', note: resolveNote || '风险已解决' }), '已标记解决', detail.id).then(() => { setResolveModal(false); setResolveNote('') })
    }}>
      <Form layout="vertical"><Form.Item label="处理备注（可选）"><Input.TextArea rows={3} value={resolveNote} onChange={(e) => setResolveNote(e.target.value)} placeholder="记录解决说明（可选）" /></Form.Item></Form>
    </Modal>

    <Modal title="忽略风险" open={ignoreModal} onCancel={() => setIgnoreModal(false)} onOk={() => {
      if (!detail) return
      void act(() => updateRiskCaseStatus(detail.id, { action: 'ignore', ignore_reason: ignoreReason }), '已忽略该风险', detail.id).then(() => setIgnoreModal(false))
    }}>
      <Form layout="vertical"><Form.Item label="忽略原因（必填）">
        <Select value={ignoreReason} onChange={setIgnoreReason} options={[{ value: '数据异常', label: '数据异常' }, { value: '重复预警', label: '重复预警' }, { value: '已由其他方式处理', label: '已由其他方式处理' }, { value: '其他', label: '其他' }]} />
      </Form.Item></Form>
    </Modal>
  </section>
}
