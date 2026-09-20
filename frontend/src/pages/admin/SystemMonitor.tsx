import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Button, Card, Col, Drawer, Empty, Input, Progress, Row, Segmented, Select, Space, Spin, Table, Tabs, Tag, message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  AlertOutlined, ApiOutlined, CheckCircleOutlined, CloudServerOutlined, DatabaseOutlined, ExperimentOutlined,
  FileSearchOutlined, RobotOutlined, SyncOutlined, ThunderboltOutlined, ToolOutlined, WarningOutlined,
} from '@ant-design/icons'
import { monitorApi, type ServiceHealth, type SystemAlert, type SystemLog, type SystemOverview, type SystemTask } from '../../api/systemMonitor'
import './system-monitor.css'

const SERVICE_STATUS_META: Record<string, { label: string; color: string; dot: string }> = {
  ok: { label: '正常', color: 'green', dot: '#22c55e' },
  error: { label: '异常', color: 'red', dot: '#ef4444' },
  unconfigured: { label: '未配置', color: 'orange', dot: '#f59e0b' },
}
const ALERT_STATUS_META: Record<string, { label: string; color: string }> = {
  open: { label: '未处理', color: 'red' },
  processing: { label: '处理中', color: 'processing' },
  resolved: { label: '已恢复', color: 'green' },
  ignored: { label: '已忽略', color: 'default' },
}
const TASK_STATUS_META: Record<string, { label: string; color: string }> = {
  pending: { label: '等待中', color: 'default' },
  running: { label: '运行中', color: 'processing' },
  success: { label: '成功', color: 'green' },
  failed: { label: '失败', color: 'red' },
}

const SERVICE_JUMP: Record<string, string> = {
  agent_runtime: '/admin/agents',
  model_gateway: '/admin/models',
  embedding: '/admin/models',
  rag: '/admin/knowledge',
}

function TrendChart({ data }: { data: { label: string; count: number }[] }) {
  const max = Math.max(1, ...data.map((item) => item.count))
  return <div className="sm-trend">
    {data.map((item) => (
      <div className="sm-trend-col" key={item.label}>
        <span className="sm-trend-count">{item.count}</span>
        <div className="sm-trend-bar" style={{ height: `${Math.max(4, item.count / max * 100)}%` }} />
        <span className="sm-trend-label">{item.label}</span>
      </div>
    ))}
  </div>
}

function ServiceCard({ service, onJump }: { service: ServiceHealth; onJump: (key: string) => void }) {
  const meta = SERVICE_STATUS_META[service.status] ?? SERVICE_STATUS_META.error
  return <Card className="sm-service-card" onClick={() => onJump(service.key)}>
    <div className="sm-service-head">
      <span className="sm-service-dot" style={{ background: meta.dot }} />
      <b>{service.name}</b>
      <Tag color={meta.color} style={{ margin: 0 }}>{meta.label}</Tag>
    </div>
    <p className="sm-service-detail">{service.detail}</p>
    <div className="sm-service-foot">
      <span>{service.latency_ms} ms</span>
      <small>检查于 {new Date().toLocaleTimeString('zh-CN', { hour12: false })}</small>
    </div>
  </Card>
}

function OverviewTab({ overview, onRefresh }: { overview: SystemOverview; onRefresh: () => void }) {
  const [trendRange, setTrendRange] = useState('hour')
  const navigate = (key: string) => {
    const target = SERVICE_JUMP[key]
    if (target) window.location.hash = `#${target}`
  }
  const trendData = trendRange === 'hour' ? overview.api.trend.hour : trendRange === 'day' ? overview.api.trend.day : overview.api.trend.week
  const overallMeta = overview.overall_status === 'normal'
    ? { label: '正常', color: 'green' }
    : overview.overall_status === 'partial' ? { label: '部分异常', color: 'orange' } : { label: '严重异常', color: 'red' }
  const kpis = [
    { icon: <ThunderboltOutlined />, color: overallMeta.color, label: '系统状态', value: overallMeta.label, note: `${overview.services_available} 核心服务可用` },
    { icon: <CloudServerOutlined />, color: '#16a34a', label: '在线核心服务', value: overview.services.filter((s) => s.status === 'ok').length, note: `共 ${overview.services.length} 项检测` },
    { icon: <ApiOutlined />, color: '#0EA5B7', label: '今日请求', value: overview.api.today.total, note: overview.api.today.success_rate !== null ? `成功率 ${overview.api.today.success_rate}%` : '暂无请求' },
    { icon: <AlertOutlined />, color: '#F59E0B', label: '异常告警', value: overview.alerts.open, note: `今日共 ${overview.alerts.today_total} 条` },
  ]
  return <div className="sm-tab-body">
    <Row gutter={[16, 16]}>
      {kpis.map((kpi) => (
        <Col xs={12} xl={6} key={kpi.label}>
          <Card className="sm-kpi" style={{ borderLeft: `3px solid ${kpi.color}` }}>
            <div className="sm-kpi-icon" style={{ color: kpi.color, background: `${kpi.color}14` }}>{kpi.icon}</div>
            <div className="sm-kpi-body"><small>{kpi.label}</small><b>{kpi.value}</b><p>{kpi.note}</p></div>
          </Card>
        </Col>
      ))}
    </Row>

    <div className="sm-section-title">核心服务状态</div>
    <Row gutter={[12, 12]}>
      {overview.services.map((service) => (
        <Col xs={12} md={8} xl={8} key={service.key}><ServiceCard service={service} onJump={navigate} /></Col>
      ))}
    </Row>

    <div className="sm-section-title">系统资源</div>
    <Card className="sm-sub-card">
      {overview.resources.available ? <Row gutter={[20, 16]}>
        <Col xs={12} md={6}><div className="sm-resource"><span>CPU</span><b>{overview.resources.cpu_percent}%</b><Progress percent={overview.resources.cpu_percent ?? 0} size="small" strokeColor="#16a34a" showInfo={false} /></div></Col>
        <Col xs={12} md={6}><div className="sm-resource"><span>内存</span><b>{overview.resources.memory_percent}%</b><Progress percent={overview.resources.memory_percent ?? 0} size="small" strokeColor="#16a34a" showInfo={false} /><small>{overview.resources.memory_used_gb} / {overview.resources.memory_total_gb} GB</small></div></Col>
        <Col xs={12} md={6}><div className="sm-resource"><span>磁盘</span><b>{overview.resources.disk_percent}%</b><Progress percent={overview.resources.disk_percent ?? 0} size="small" strokeColor="#16a34a" showInfo={false} /></div></Col>
        <Col xs={12} md={6}><div className="sm-resource"><span>系统运行时长</span><b>{overview.resources.uptime_hours}h</b><small>自上次启动</small></div></Col>
      </Row> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前环境无法可靠读取系统资源，暂无监控数据" />}
    </Card>

    <div className="sm-section-title">API 请求趋势 <Segmented value={trendRange} onChange={(value) => setTrendRange(String(value))} size="small" options={[{ label: '近1小时', value: 'hour' }, { label: '近24小时', value: 'day' }, { label: '近7天', value: 'week' }]} /></div>
    <Card className="sm-sub-card">
      {overview.api.today.total ? <TrendChart data={trendData} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无请求监控数据" />}
    </Card>

    <Row gutter={[16, 16]}>
      <Col xs={24} xl={14}>
        <div className="sm-section-title">最慢接口（近 7 天）</div>
        <Card className="sm-sub-card">
          {overview.api.slow_endpoints.length ? <Table
            rowKey={(row) => row.path} size="small" pagination={false}
            columns={[
              { title: 'API', dataIndex: 'path', render: (value) => <code className="sm-code">{value}</code> },
              { title: '平均耗时', dataIndex: 'avg_ms', width: 100, align: 'center', render: (value) => <b className="sm-ms">{value}ms</b> },
              { title: '调用次数', dataIndex: 'calls', width: 90, align: 'center' },
              { title: '错误率', dataIndex: 'error_rate', width: 90, align: 'center', render: (value) => <Tag color={value > 5 ? 'red' : 'default'}>{value}%</Tag> },
            ]} dataSource={overview.api.slow_endpoints}
          /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无接口统计数据" />}
        </Card>
      </Col>
      <Col xs={24} xl={10}>
        <div className="sm-section-title">Agent Runtime</div>
        <Card className="sm-sub-card">
          <div className="sm-agent-stats">
            <div><b>{overview.agents.today_runs}</b><span>今日 Runs</span></div>
            <div><b>{overview.agents.today_success_rate !== null ? `${overview.agents.today_success_rate}%` : '—'}</b><span>成功率</span></div>
            <div><b>{overview.agents.avg_latency_ms !== null ? `${overview.agents.avg_latency_ms}ms` : '—'}</b><span>平均耗时</span></div>
            <div><b>{overview.agents.exceptions}</b><span>异常 Runs</span></div>
          </div>
          {overview.agents.recent_errors.length ? overview.agents.recent_errors.map((error) => (
            <div className="sm-agent-error" key={error.id}>
              <Tag color="red">{error.agent}</Tag>
              <span>{error.error_message || error.error_code || '未知错误'}</span>
              <small>{error.created_at ? new Date(error.created_at).toLocaleTimeString('zh-CN', { hour12: false }) : ''}</small>
            </div>
          )) : <p className="sm-empty-line">近期无异常 Agent Run</p>}
        </Card>
      </Col>
    </Row>
    <div style={{ textAlign: 'right', marginTop: 8 }}><Button size="small" icon={<SyncOutlined />} onClick={onRefresh}>刷新</Button></div>
  </div>
}

function TasksTab({ tasks }: { tasks: SystemOverview['tasks'] | null }) {
  const columns: ColumnsType<SystemTask> = [
    { title: '任务', dataIndex: 'name', render: (value) => <b className="sm-task-name">{value}</b> },
    { title: '任务类型', dataIndex: 'task_type', width: 140, render: (value) => <Tag color="blue">{value}</Tag> },
    { title: '创建时间', dataIndex: 'created_at', width: 150, render: (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—' },
    { title: '状态', dataIndex: 'status', width: 100, render: (value) => { const meta = TASK_STATUS_META[value] ?? { label: value, color: 'default' }; return <Tag color={meta.color}>{meta.label}</Tag> } },
    { title: '关联资源', dataIndex: 'related', width: 100, render: (value) => <Tag style={{ margin: 0 }}>{value}</Tag> },
    { title: '失败原因', dataIndex: 'error', width: 220, render: (value) => value ? <span className="sm-error-text">{value}</span> : '—' },
  ]
  if (!tasks) return <div className="sm-tab-body"><Spin /></div>
  return <div className="sm-tab-body">
    <Row gutter={[16, 16]} className="sm-task-stats-row">
      {[['运行中', tasks.running, 'processing'], ['等待中', tasks.waiting, 'default'], ['今日完成', tasks.completed_today, 'green'], ['失败', tasks.failed, 'red']].map(([label, value, color]) => (
        <Col xs={12} xl={6} key={label as string}><Card className="sm-kpi sm-kpi-sm"><div className="sm-kpi-body"><small>{label}</small><b>{value}</b></div></Card></Col>
      ))}
    </Row>
    <div className="sm-section-title">后台任务列表</div>
    <Card className="sm-sub-card">
      {tasks.tasks.length ? <Table rowKey="id" size="small" columns={columns} dataSource={tasks.tasks} pagination={{ pageSize: 10 }} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无运行中的后台任务" />}
    </Card>
  </div>
}

function AlertsTab() {
  const [alerts, setAlerts] = useState<SystemAlert[]>([])
  const [loading, setLoading] = useState(true)
  const [viewing, setViewing] = useState<SystemAlert | null>(null)
  const [showDetail, setShowDetail] = useState(false)
  const load = useCallback(async () => {
    setLoading(true)
    try { setAlerts(await monitorApi.alerts()) } catch { message.error('告警加载失败') } finally { setLoading(false) }
  }, [])
  useEffect(() => { void load() }, [load])
  const changeStatus = async (alert: SystemAlert, status: string) => {
    try {
      await monitorApi.updateAlertStatus(alert.id, status)
      message.success('状态已更新')
      setViewing((prev) => prev && prev.id === alert.id ? { ...prev, status } : prev)
      await load()
    } catch { message.error('更新失败') }
  }
  const columns: ColumnsType<SystemAlert> = [
    { title: '时间', dataIndex: 'created_at', width: 150, render: (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—' },
    { title: '服务', dataIndex: 'source', width: 110, render: (value) => <Tag color="blue">{value}</Tag> },
    { title: '级别', dataIndex: 'level', width: 100, render: (value) => <Tag color={value === 'CRITICAL' ? 'red' : value === 'ERROR' ? 'volcano' : value === 'WARNING' ? 'orange' : 'default'}>{value}</Tag> },
    { title: '错误代码', dataIndex: 'error_code', width: 130, render: (value) => value ? <code className="sm-code">{value}</code> : '—' },
    { title: '异常摘要', dataIndex: 'message', render: (value) => <span className="sm-alert-msg">{value}</span> },
    { title: '状态', dataIndex: 'status', width: 100, render: (value) => { const meta = ALERT_STATUS_META[value] ?? { label: value, color: 'default' }; return <Tag color={meta.color}>{meta.label}</Tag> } },
    { title: '操作', key: 'op', width: 180, render: (_, record) => (
      <Space size={0} wrap>
        <Button type="link" size="small" onClick={() => { setViewing(record); setShowDetail(false) }}>详情</Button>
        {record.status === 'open' && <Button type="link" size="small" onClick={() => void changeStatus(record, 'processing')}>标记处理中</Button>}
        {['open', 'processing'].includes(record.status) && <Button type="link" size="small" onClick={() => void changeStatus(record, 'resolved')}>已恢复</Button>}
        {record.status !== 'ignored' && <Button type="link" size="small" danger onClick={() => void changeStatus(record, 'ignored')}>忽略</Button>}
      </Space>
    ) },
  ]
  return <div className="sm-tab-body">
    <div className="sm-tab-head"><span className="sm-tab-note">共 {alerts.length} 条系统告警 · 操作实时持久化</span><Button size="small" icon={<SyncOutlined />} onClick={() => void load()}>刷新</Button></div>
    <Card className="sm-sub-card">
      {alerts.length ? <Table rowKey="id" size="small" columns={columns} dataSource={alerts} pagination={{ pageSize: 10 }} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前暂无系统异常" />}
    </Card>
    <Drawer title="异常详情" width={480} open={Boolean(viewing)} onClose={() => setViewing(null)}>
      {viewing ? <div className="sm-alert-detail">
        <div className="sm-alert-detail-grid">
          <span>服务</span><b>{viewing.source}</b>
          <span>时间</span><b>{viewing.created_at ? new Date(viewing.created_at).toLocaleString('zh-CN', { hour12: false }) : '—'}</b>
          <span>级别</span><b><Tag color={viewing.level === 'CRITICAL' ? 'red' : viewing.level === 'ERROR' ? 'volcano' : 'orange'}>{viewing.level}</Tag></b>
          <span>错误代码</span><b><code className="sm-code">{viewing.error_code ?? '—'}</code></b>
          <span>Trace ID</span><b><code className="sm-code">{viewing.trace_id ?? '—'}</code></b>
          <span>当前状态</span><b><Tag color={ALERT_STATUS_META[viewing.status]?.color}>{ALERT_STATUS_META[viewing.status]?.label}</Tag></b>
        </div>
        <div className="sm-section-title">异常摘要</div>
        <p className="sm-alert-message">{viewing.message}</p>
        {!showDetail ? <Button size="small" type="link" onClick={() => setShowDetail(true)}>查看技术详情</Button>
          : <div className="sm-section-title">技术详情</div>}
        {showDetail && <pre className="sm-alert-details">{viewing.details || '无更多技术信息'}</pre>}
        <div className="sm-alert-actions">
          {viewing.status === 'open' && <Button type="primary" onClick={() => void changeStatus(viewing, 'processing')}>标记处理中</Button>}
          {['open', 'processing'].includes(viewing.status) && <Button onClick={() => void changeStatus(viewing, 'resolved')}>标记已恢复</Button>}
          {viewing.status !== 'ignored' && <Button danger onClick={() => void changeStatus(viewing, 'ignored')}>忽略</Button>}
        </div>
      </div> : null}
    </Drawer>
  </div>
}

function LogsTab() {
  const [logs, setLogs] = useState<SystemLog[]>([])
  const [loading, setLoading] = useState(true)
  const [level, setLevel] = useState<string>()
  const [traceId, setTraceId] = useState('')
  const load = useCallback(async () => {
    setLoading(true)
    try {
      setLogs(await monitorApi.logs({ level, trace_id: traceId || undefined, limit: 100 }))
    } catch { message.error('日志加载失败') } finally { setLoading(false) }
  }, [level, traceId])
  useEffect(() => { void load() }, [load])
  const columns: ColumnsType<SystemLog> = [
    { title: '时间', dataIndex: 'time', width: 150, render: (value) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—' },
    { title: '服务', dataIndex: 'service', width: 90, render: (value) => <Tag color="blue">{value}</Tag> },
    { title: 'Level', dataIndex: 'level', width: 90, render: (value) => <Tag color={value === 'WARNING' ? 'orange' : 'default'}>{value}</Tag> },
    { title: 'Message', dataIndex: 'message', render: (value) => <span className="sm-log-msg">{value}</span> },
    { title: 'Trace ID', dataIndex: 'trace_id', width: 160, render: (value) => value ? <code className="sm-code">{value.slice(0, 18)}...</code> : '—' },
  ]
  return <div className="sm-tab-body">
    <div className="sm-log-filters">
      <span>级别</span>
      <Select size="small" allowClear placeholder="全部" style={{ width: 130 }} value={level} onChange={setLevel} options={['INFO', 'WARNING', 'ERROR', 'CRITICAL'].map((value) => ({ value, label: value }))} />
      <span>Trace ID</span>
      <Input size="small" placeholder="按 Trace ID 过滤" style={{ width: 220 }} value={traceId} onChange={(e) => setTraceId(e.target.value)} allowClear />
      <Button size="small" type="primary" icon={<FileSearchOutlined />} onClick={() => void load()}>查询</Button>
      <span className="sm-tab-note" style={{ marginLeft: 'auto' }}>仅展示审计元数据，不包含敏感请求内容</span>
    </div>
    <Card className="sm-sub-card">
      {logs.length ? <Table rowKey="id" size="small" columns={columns} dataSource={logs} pagination={{ pageSize: 15 }} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无日志记录" />}
    </Card>
  </div>
}

export function SystemMonitor() {
  const [overview, setOverview] = useState<SystemOverview | null>(null)
  const [tab, setTab] = useState('overview')
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async () => {
    try { setOverview(await monitorApi.overview()) } catch { /* 静默，保留旧数据 */ } finally { setLoading(false) }
  }, [])
  useEffect(() => { void load() }, [load])

  useEffect(() => {
    if (!autoRefresh) return
    timerRef.current = setInterval(() => {
      if (document.hidden) return
      void load()
    }, 30000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [autoRefresh, load])

  return <section className="sm-page system-monitor-page">
    <div className="sm-page-head">
      <p className="sm-subtitle">平台技术运行监控中心：服务健康、API 指标、Agent Runtime、后台任务与系统告警。</p>
      <Space>
        <Button size="small" icon={<SyncOutlined />} loading={loading} onClick={() => void load()}>刷新</Button>
        <Button size="small" type={autoRefresh ? 'primary' : 'default'} onClick={() => setAutoRefresh((value) => !value)}>{autoRefresh ? '自动刷新 30s' : '自动刷新已关'}</Button>
      </Space>
    </div>
    <Card className="sm-card-panel" styles={{ body: { padding: 0 } }}>
      {overview ? <Tabs activeKey={tab} onChange={setTab} items={[
        { key: 'overview', label: '运行概览', children: <OverviewTab overview={overview} onRefresh={() => void load()} /> },
        { key: 'tasks', label: '任务监控', children: <TasksTab tasks={overview.tasks} /> },
        { key: 'alerts', label: '异常告警', children: <AlertsTab /> },
        { key: 'logs', label: '系统日志', children: <LogsTab /> },
      ]} /> : <div className="sm-tab-loading"><Spin /> 正在检查平台服务...</div>}
    </Card>
  </section>
}
