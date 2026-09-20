import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, Col, Empty, Progress, Row, Segmented, Space, Tag, message } from 'antd'
import {
  AlertOutlined, ApiOutlined, AppstoreOutlined, CloudServerOutlined, DatabaseOutlined, ExperimentOutlined,
  HeartOutlined, LineChartOutlined, MedicineBoxOutlined, PieChartOutlined, RobotOutlined, SafetyCertificateOutlined,
  TeamOutlined, ThunderboltOutlined, UserOutlined, WarningOutlined, FileTextOutlined, ReadOutlined,
} from '@ant-design/icons'
import { getHealthAnalyticsSummary, type HealthAnalyticsSummary } from '../../api/adminAnalytics'
import { getCheckupSummary, type CheckupSummary } from '../../api/checkups'
import { getAdminActivitySummary, type AdminActivitySummary } from '../../api/activities'
import { knowledgeApi } from '../../api/knowledge'
import { agentAdminApi, type AgentSummary } from '../../api/agents'
import { monitorApi, type SystemOverview } from '../../api/systemMonitor'
import { modelApi, type ModelOverview } from '../../api/models'
import { getRiskCases } from '../../api/riskCases'
import './admin-home.css'

const ENTRY_META: { path: string; icon: React.ReactNode; title: string; desc: string; color: string }[] = [
  { path: '/admin/users', icon: <UserOutlined />, title: '用户管理', desc: '企业员工账号、角色与状态管理', color: '#16a34a' },
  { path: '/admin/checkups', icon: <FileTextOutlined />, title: '体检管理', desc: '体检报告解析、质检与指标入库', color: '#0891b2' },
  { path: '/admin/risk', icon: <SafetyCertificateOutlined />, title: '风险预警与处置', desc: '健康风险队列与处置流程', color: '#dc2626' },
  { path: '/admin/activities', icon: <AppstoreOutlined />, title: '健康活动运营', desc: '活动创建、发布与报名跟踪', color: '#d97706' },
  { path: '/admin/knowledge', icon: <ReadOutlined />, title: '知识库管理', desc: '知识文档解析、向量化与检索', color: '#7c3aed' },
  { path: '/admin/agents', icon: <RobotOutlined />, title: 'Agent 管理', desc: 'AI Agent 能力、绑定与运行监控', color: '#0ea5b7' },
]

function TrendLine({ data }: { data: { label: string; value: number }[] }) {
  const width = 640
  const height = 150
  const max = Math.max(...data.map((item) => item.value), 1) * 1.2
  const points = data.map((item, index) => {
    const x = data.length > 1 ? (index / (data.length - 1)) * (width - 40) + 20 : 20
    const y = height - 18 - (item.value / max) * (height - 40)
    return { x, y, ...item }
  })
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
  return <div className="dash-trend">
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ width: '100%', height: 170 }}>
      <line x1="20" y1={height - 18} x2={width - 20} y2={height - 18} stroke="#e2e8f0" strokeWidth="1" />
      {points.map((p) => <circle key={p.label} cx={p.x} cy={p.y} r="3.5" fill="#fff" stroke="#16a34a" strokeWidth="2" />)}
      <path d={path} fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      {points.length < 12 && points.map((p) => <text key={`t${p.label}`} x={p.x} y={p.y - 10} textAnchor="middle" fontSize="10" fill="#94a3b8">{p.value}</text>)}
    </svg>
    <div className="dash-trend-labels">{data.map((item) => <span key={item.label}>{item.label}</span>)}</div>
  </div>
}

function DonutChart({ items }: { items: { level: string; label: string; count: number; percent: number }[] }) {
  const COLORS: Record<string, string> = { good: '#22c55e', stable: '#84cc16', attention: '#f59e0b', high_risk: '#ef4444' }
  const total = items.reduce((sum, item) => sum + item.count, 0)
  const radius = 54
  const circumference = 2 * Math.PI * radius
  let offset = 0
  return <div className="dash-donut-wrap">
    <svg viewBox="0 0 140 140" className="dash-donut">
      <circle cx="70" cy="70" r={radius} fill="none" stroke="#f1f5f9" strokeWidth="18" />
      {total > 0 && items.filter((item) => item.count > 0).map((item) => {
        const length = (item.count / total) * circumference
        const circle = <circle key={item.level} cx="70" cy="70" r={radius} fill="none" stroke={COLORS[item.level] ?? '#94a3b8'} strokeWidth="18" strokeDasharray={`${length} ${circumference - length}`} strokeDashoffset={-offset} transform="rotate(-90 70 70)" />
        offset += length
        return circle
      })}
      <text x="70" y="66" textAnchor="middle" fontSize="22" fontWeight="700" fill="#1f2937">{total}</text>
      <text x="70" y="84" textAnchor="middle" fontSize="10" fill="#94a3b8">评估员工</text>
    </svg>
    <div className="dash-donut-legend">
      {items.map((item) => (
        <div className="dash-donut-legend-item" key={item.level}>
          <span className="dash-donut-dot" style={{ background: COLORS[item.level] ?? '#94a3b8' }} />
          <span>{item.label}</span>
          <b>{item.count}</b>
          <small>{item.percent}%</small>
        </div>
      ))}
    </div>
  </div>
}

export function AdminHome() {
  const navigate = useNavigate()
  const [analytics, setAnalytics] = useState<HealthAnalyticsSummary | null>(null)
  const [analyticsPeriod, setAnalyticsPeriod] = useState('30d')
  const [checkup, setCheckup] = useState<CheckupSummary | null>(null)
  const [activity, setActivity] = useState<AdminActivitySummary | null>(null)
  const [agentSummary, setAgentSummary] = useState<AgentSummary | null>(null)
  const [monitor, setMonitor] = useState<SystemOverview | null>(null)
  const [models, setModels] = useState<ModelOverview | null>(null)
  const [pendingDocs, setPendingDocs] = useState(0)
  const [pendingRisk, setPendingRisk] = useState(0)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [ana, check, act, agents, mon, mods, kbStatus, risks] = await Promise.all([
        getHealthAnalyticsSummary(analyticsPeriod),
        getCheckupSummary('30d'),
        getAdminActivitySummary(),
        agentAdminApi.summary(),
        monitorApi.overview(),
        modelApi.overview(),
        knowledgeApi.ragStatus(),
        getRiskCases({ status: 'pending', period: '30d' }).catch(() => ({ items: [] })),
      ])
      setAnalytics(ana)
      setCheckup(check)
      setActivity(act)
      setAgentSummary(agents)
      setMonitor(mon)
      setModels(mods)
      setPendingDocs(kbStatus.stats.pending_documents + kbStatus.stats.index_failures)
      setPendingRisk(risks.items.length)
    } catch { message.error('驾驶舱数据加载失败') } finally { setLoading(false) }
  }, [analyticsPeriod])
  useEffect(() => { void load() }, [load])

  const overview = analytics?.overview
  const highRisk = analytics?.health_distribution.find((item) => item.level === 'high_risk')?.count ?? 0
  const attention = overview?.attention_employees ?? 0
  const pendingReviewReports = checkup?.stats.pending_review_reports ?? 0
  const draftActivities = useMemo(() => activity?.open_registration_count ?? 0, [activity])
  const openAlerts = monitor?.alerts.open ?? 0
  const agentExceptions = agentSummary?.recentExceptions ?? 0

  const todos: { label: string; count: number; color: string; path: string }[] = [
    { label: '待人工确认体检报告', count: pendingReviewReports, color: 'blue', path: '/admin/checkups' },
    { label: '待处理风险预警', count: pendingRisk, color: 'red', path: '/admin/risk' },
    { label: '开放报名中的健康活动', count: draftActivities, color: 'orange', path: '/admin/activities' },
    { label: '待处理知识库文档', count: pendingDocs, color: 'purple', path: '/admin/knowledge' },
    { label: '异常 Agent 运行', count: agentExceptions, color: 'cyan', path: '/admin/agents' },
    { label: '系统告警', count: openAlerts, color: 'volcano', path: '/admin/monitoring' },
  ]

  const kpis = [
    { icon: <TeamOutlined />, label: '员工总数', value: overview?.total_employees ?? 0, note: '企业员工账号数', color: '#16a34a' },
    { icon: <HeartOutlined />, label: '健康档案覆盖率', value: `${overview?.coverage_rate ?? 0}%`, note: `${overview?.covered_employees ?? 0} 人已建档`, color: '#0891b2' },
    { icon: <WarningOutlined />, label: '需关注员工', value: attention, note: `占比 ${overview?.attention_rate ?? 0}%`, color: '#f59e0b' },
    { icon: <AlertOutlined />, label: '高风险员工', value: highRisk, note: '建议优先跟进', color: '#dc2626' },
    { icon: <MedicineBoxOutlined />, label: '近30天体检报告', value: checkup?.stats.total_reports ?? 0, note: `${checkup?.stats.abnormal_reports ?? 0} 份存在异常`, color: '#7c3aed' },
    { icon: <AppstoreOutlined />, label: '本月活动参与率', value: `${activity?.avg_participation_rate ?? 0}%`, note: '报名人数 / 名额', color: '#0ea5b7' },
  ]

  const trendData = analytics?.risk_trend.map((point) => ({ label: point.label, value: point.value })) ?? []
  const embeddingFake = models?.models.find((item) => item.model_type === 'embedding' && item.is_default)?.provider_type === 'fake'
  const defaultChat = models?.models.find((item) => item.model_type === 'chat' && item.is_default)

  return <section className="dash-page admin-home-page">
    <div className="dash-page-head">
      <div><p className="dash-subtitle">企业健康管理驾驶舱：全局健康态势、待办处理、业务入口与 AI 平台运行状态。</p></div>
      <Space><span className="dash-checked">更新于 {monitor ? new Date(monitor.checked_at).toLocaleTimeString('zh-CN', { hour12: false }) : '—'}</span>
        <Button size="small" icon={<LineChartOutlined />} loading={loading} onClick={() => void load()}>刷新</Button></Space>
    </div>

    <Row gutter={[16, 16]} className="dash-kpi-row">
      {kpis.map((kpi) => (
        <Col xs={12} xl={4} key={kpi.label}>
          <Card className="dash-kpi" style={{ borderLeft: `3px solid ${kpi.color}` }}>
            <div className="dash-kpi-icon" style={{ color: kpi.color, background: `${kpi.color}14` }}>{kpi.icon}</div>
            <div className="dash-kpi-body"><small>{kpi.label}</small><b>{kpi.value}</b><p>{kpi.note}</p></div>
          </Card>
        </Col>
      ))}
    </Row>

    <Row gutter={[16, 16]} align="stretch">
      <Col xs={24} xl={16}>
        <Card className="dash-card" title="企业健康总览">
          <div className="dash-trend-head">
            <b>需关注员工比例趋势</b>
            <Segmented value={analyticsPeriod} onChange={(value) => setAnalyticsPeriod(String(value))} size="small" options={[{ label: '近7天', value: '7d' }, { label: '近30天', value: '30d' }]} />
          </div>
          {trendData.length ? <TrendLine data={trendData} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无趋势数据" style={{ padding: 20 }} />}
          <div className="dash-section-title"><PieChartOutlined /> 健康状态分布</div>
          {analytics?.health_distribution.length ? <DonutChart items={analytics.health_distribution} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无分布数据" style={{ padding: 20 }} />}
        </Card>
      </Col>
      <Col xs={24} xl={8}>
        <Card className="dash-card dash-todo-card" title="待处理事项" extra={<span className="dash-card-note">共 {todos.reduce((sum, item) => sum + item.count, 0)} 项</span>}>
          {todos.some((item) => item.count > 0) ? todos.map((todo) => (
            <div className="dash-todo" key={todo.label}>
              <span className="dash-todo-dot" style={{ background: todo.color }} />
              <span className="dash-todo-label">{todo.label}</span>
              <Tag color={todo.color} style={{ margin: 0 }}>{todo.count}</Tag>
              <Button size="small" type="link" onClick={() => navigate(todo.path)}>去处理</Button>
            </div>
          )) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无待处理事项" style={{ padding: 20 }} />}
        </Card>
      </Col>
    </Row>

    <div className="dash-section-title">部门健康概览</div>
    <Card className="dash-card">
      {analytics?.department_stats.length ? <div className="dash-dept-table">
        <div className="dash-dept-head dash-dept-row">
          <span>部门名称</span><span>员工数</span><span>档案覆盖率</span><span>需关注人数</span><span>高风险人数</span><span>主要风险标签</span>
        </div>
        {analytics.department_stats.map((dept) => (
          <div className="dash-dept-row" key={dept.department}>
            <span className="dash-dept-name">{dept.department}</span>
            <span>{dept.total}</span>
            <span>{dept.coverage_rate}%</span>
            <span><b className={dept.attention_count > 0 ? 'dash-num-attention' : ''}>{dept.attention_count}</b></span>
            <span><b className="dash-num-high">{dept.attention_count > 0 ? dept.attention_count : 0}</b></span>
            <span>{dept.top_risk ? <Tag color="orange" style={{ margin: 0 }}>{dept.top_risk}</Tag> : <span className="dash-muted">—</span>}</span>
          </div>
        ))}
      </div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无部门健康概览数据" style={{ padding: 20 }} />}
    </Card>

    <div className="dash-section-title">业务快捷入口</div>
    <Row gutter={[16, 16]}>
      {ENTRY_META.map((entry) => (
        <Col xs={12} md={8} key={entry.path}>
          <Card className="dash-entry" onClick={() => navigate(entry.path)}>
            <div className="dash-entry-icon" style={{ color: entry.color, background: `${entry.color}14` }}>{entry.icon}</div>
            <div className="dash-entry-body"><b>{entry.title}</b><p>{entry.desc}</p></div>
            <span className="dash-entry-arrow">→</span>
          </Card>
        </Col>
      ))}
    </Row>

    <Row gutter={[16, 16]} align="stretch">
      <Col xs={24} xl={12}>
        <Card className="dash-card" title={<span><RobotOutlined /> AI 能力状态</span>} extra={<span className="dash-card-note">知识库 {models?.models.find((item) => item.model_type === 'embedding')?.used_by_knowledge_bases.length ?? 0} 个</span>}>
          <div className="dash-ai-rows">
            {[
              { label: '默认 Chat 模型', value: defaultChat ? defaultChat.name : '未配置', ok: Boolean(defaultChat) },
              { label: 'Embedding 配置', value: embeddingFake ? '开发测试模型（Fake 8维）' : models?.defaults.embedding ? '已配置' : '未配置', ok: Boolean(models?.defaults.embedding) && !embeddingFake },
              { label: 'Health Supervisor', value: agentSummary?.enabled ?? 0 > 0 ? '运行中' : '未启用', ok: true },
              { label: 'Agent 运行', value: `${agentSummary?.enabled ?? 0} 启用 · 今日 ${agentSummary?.todayRuns ?? 0} 次`, ok: true },
            ].map((item) => (
              <div className="dash-ai-row" key={item.label}>
                <span className="dash-ai-label">{item.label}</span>
                <b>{item.value}</b>
                <span className={`dash-status-light ${item.ok ? 'ok' : 'warn'}`} />
              </div>
            ))}
          </div>
          <div className="dash-agent-tags">
            {['Health Supervisor', 'Report Agent', 'Risk Agent', 'Sleep Agent', 'Mental Health Agent', 'Health Plan Agent'].map((name) => (
              <Tag key={name} color="green" style={{ margin: '0 6px 6px 0' }}>{name}</Tag>
            ))}
          </div>
        </Card>
      </Col>
      <Col xs={24} xl={12}>
        <Card className="dash-card" title={<span><CloudServerOutlined /> 系统运行状态</span>} extra={<Tag color={monitor?.overall_status === 'normal' ? 'green' : monitor?.overall_status === 'partial' ? 'orange' : 'red'}>{monitor?.overall_status === 'normal' ? '正常' : monitor?.overall_status === 'partial' ? '部分异常' : '严重异常'}</Tag>}>
          <div className="dash-sys-grid">
            {monitor?.services.map((service) => (
              <div className="dash-sys-item" key={service.key}>
                <span className={`dash-status-light ${service.status === 'ok' ? 'ok' : service.status === 'unconfigured' ? 'warn' : 'err'}`} />
                <span className="dash-sys-name">{service.name}</span>
                <Tag color={service.status === 'ok' ? 'green' : service.status === 'unconfigured' ? 'orange' : 'red'} style={{ margin: 0 }}>{service.status === 'ok' ? '正常' : service.status === 'unconfigured' ? '未配置' : '异常'}</Tag>
              </div>
            ))}
          </div>
          <div className="dash-sys-stats">
            <div><b>{monitor?.api.today.total ?? 0}</b><span>今日请求数</span></div>
            <div><b>{monitor?.alerts.open ?? 0}</b><span>未处理告警</span></div>
            <div><b>{monitor?.tasks.completed_today ?? 0}</b><span>今日完成任务</span></div>
            <div><b>{monitor?.services_available ?? '—'}</b><span>服务可用</span></div>
          </div>
          <div style={{ marginTop: 12 }}><Button size="small" type="link" onClick={() => navigate('/admin/monitoring')}>进入系统监控 <span>→</span></Button></div>
        </Card>
      </Col>
    </Row>
  </section>
}
