import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Button, Card, Col, Empty, Input, Row, Space, Spin, Statistic, Switch, Tabs, Tag, message,
} from 'antd'
import {
  CheckCircleOutlined, DatabaseOutlined, LineChartOutlined, PlayCircleOutlined,
  RobotOutlined, ToolOutlined, AlertOutlined, SearchOutlined, FilterOutlined,
} from '@ant-design/icons'
import { agentAdminApi, type AgentItem, type AgentRunItem, type AgentSummary } from '../../api/agents'
import './agent-management.css'
import './agent-management-fixes.css'

const CAPABILITY_META: [string, string, string][] = [
  ['route', '路由能力', '识别意图并将请求分发到专业 Agent'],
  ['tool', '工具调用能力', '按授权调用健康数据和业务工具'],
  ['knowledge', '知识检索能力', '从绑定知识库获取可信参考内容'],
  ['output', '输出控制能力', '执行安全边界和结构化输出控制'],
]
const RUN_STATUS_META: Record<string, { label: string; color: string }> = {
  succeeded: { label: '成功', color: 'green' },
  pending: { label: '等待中', color: 'default' },
  running: { label: '运行中', color: 'processing' },
  failed: { label: '失败', color: 'red' },
}
const PAGE_SIZE = 6
const FORMAL_AGENT_SLUGS = new Set([
  'health_supervisor', 'health-supervisor-system', 'report_agent', 'health_report_interpretation',
  'sleep_agent', 'risk_agent', 'risk_assessment_agent', 'mental_health_agent', 'health_plan_agent',
  'nutrition_agent', 'fitness_agent',
])

const isTestAgent = (agent: AgentItem) => {
  const value = `${agent.slug} ${agent.name}`.toLowerCase()
  return /(^|[\\-_])(rag|test|demo|fake)([\\-_]|$)/i.test(value) || value.includes('测试')
}

export function AgentManagement() {
  const [agents, setAgents] = useState<AgentItem[]>([])
  const [summary, setSummary] = useState<AgentSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<AgentItem | null>(null)
  const [runs, setRuns] = useState<AgentRunItem[]>([])
  const [testInput, setTestInput] = useState('')
  const [testResult, setTestResult] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<'all' | 'Supervisor' | 'Specialist' | 'error'>('all')
  const [category, setCategory] = useState<'all' | 'formal' | 'test'>('formal')
  const [agentPage, setAgentPage] = useState(1)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [items, sum] = await Promise.all([agentAdminApi.list(), agentAdminApi.summary()])
      setAgents(items)
      setSummary(sum)
      const preferred = items.find((item) => !isTestAgent(item)) ?? items[0]
      setSelected((prev) => {
        if (prev) {
          const next = items.find((item) => item.id === prev.id) ?? items[0] ?? null
          if (next) void loadDetail(next.id)
          return next
        }
        if (preferred) void loadDetail(preferred.id)
        return preferred ?? null
      })
    } catch { message.error('Agent 数据加载失败') } finally { setLoading(false) }
  }, [])

  const loadDetail = async (id: string) => {
    try {
      const [detail, runList] = await Promise.all([agentAdminApi.detail(id), agentAdminApi.runs(id)])
      setSelected(detail)
      setRuns(runList)
    } catch { /* 详情加载失败不阻塞列表 */ }
  }

  useEffect(() => { void refresh() }, [refresh])

  const toggleStatus = async (agent: AgentItem) => {
    if (!agent) return
    setToggling(true)
    try {
      const updated = await agentAdminApi.updateStatus(agent.id, agent.enabled ? 'disabled' : 'active')
      setAgents((prev) => prev.map((item) => item.id === updated.id ? updated : item))
      setSelected(updated)
      message.success(updated.enabled ? 'Agent 已启用' : 'Agent 已停用')
      void refresh()
    } catch (e: any) { message.error(e?.response?.data?.detail || '操作失败') } finally { setToggling(false) }
  }

  const runTest = async () => {
    if (!selected) return
    if (!testInput.trim()) { message.warning('请输入测试输入'); return }
    setTesting(true); setTestResult(null)
    try {
      const result = await agentAdminApi.test(selected.id, testInput.trim())
      setTestResult(`运行状态：${result.status}${result.assistant_content ? `\n回复：${result.assistant_content.slice(0, 300)}` : ''}`)
    } catch (e: any) { message.error(e?.response?.data?.detail || '测试运行失败') } finally { setTesting(false) }
  }

  const filteredAgents = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    const result = agents.filter((agent) => {
      const matchesQuery = !normalized || [agent.name, agent.slug, agent.domain, agent.model_name ?? agent.model]
        .some((value) => String(value ?? '').toLowerCase().includes(normalized))
      const matchesType = typeFilter === 'all'
        || (typeFilter === 'error' ? agent.exceptions > 0 : agent.type === typeFilter)
      const test = isTestAgent(agent)
      const matchesCategory = category === 'all' || (category === 'test' ? test : !test)
      return matchesQuery && matchesType && matchesCategory
    })
    return result.sort((a, b) => {
      if (category !== 'test') {
        const priority = (agent: AgentItem) => FORMAL_AGENT_SLUGS.has(agent.slug) ? 0 : 1
        return priority(a) - priority(b)
      }
      return 0
    })
  }, [agents, query, typeFilter, category])

  const pageCount = Math.max(1, Math.ceil(filteredAgents.length / PAGE_SIZE))
  const pagedAgents = useMemo(
    () => filteredAgents.slice((agentPage - 1) * PAGE_SIZE, agentPage * PAGE_SIZE),
    [filteredAgents, agentPage],
  )

  useEffect(() => {
    setAgentPage(1)
  }, [query, typeFilter, category])

  useEffect(() => {
    if (agentPage > pageCount) setAgentPage(pageCount)
  }, [agentPage, pageCount])

  useEffect(() => {
    if (filteredAgents.length && !filteredAgents.some((agent) => agent.id === selected?.id)) {
      void loadDetail(filteredAgents[0].id)
    }
  }, [filteredAgents, selected?.id])

  const trend = useMemo(() => {
    const buckets = new Map<string, number>()
    runs.forEach((run) => {
      if (!run.time) return
      const date = new Date(run.time)
      if (Number.isNaN(date.getTime())) return
      const key = date.toISOString().slice(0, 10)
      buckets.set(key, (buckets.get(key) ?? 0) + 1)
    })
    return [...buckets.entries()].sort(([a], [b]) => a.localeCompare(b)).slice(-7)
  }, [runs])

  const kpis = [
    { label: 'Agent 总数', value: summary?.total ?? 0, icon: <RobotOutlined /> },
    { label: '启用中', value: summary?.enabled ?? 0, icon: <CheckCircleOutlined /> },
    { label: '今日运行次数', value: summary?.todayRuns ?? 0, icon: <LineChartOutlined /> },
    { label: '最近异常次数', value: summary?.recentExceptions ?? 0, icon: <AlertOutlined /> },
  ]

  return <section className="agent-page agent-management-page">
    <div className="agent-page-toolbar">
      <span>Agent 能力与运行状态</span>
      <Button size="small" icon={<RobotOutlined />} onClick={() => void refresh()}>刷新</Button>
    </div>

    <Row gutter={[16, 16]} className="agent-kpi-row">
      {kpis.map((kpi) => (
        <Col xs={12} lg={6} key={kpi.label}>
          <Card className="agent-kpi"><div className="agent-kpi-icon">{kpi.icon}</div><Statistic title={kpi.label} value={kpi.value} /></Card>
        </Col>
      ))}
    </Row>

    {loading ? <div className="agent-page-loading"><Spin /> 正在加载 Agent...</div> : agents.length ? (
      <div className="agent-workspace">
        <Card className="agent-selector-panel" title={<span><RobotOutlined /> Agent 选择 <small>{filteredAgents.length} 个能力</small></span>}>
          <div className="agent-list-tools">
            <Input allowClear prefix={<SearchOutlined />} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索 Agent 名称或标识" />
            <Button aria-label="筛选 Agent" icon={<FilterOutlined />} onClick={() => setTypeFilter(typeFilter === 'all' ? 'error' : 'all')} />
          </div>
          <div className="agent-filter-chips">
            {([['all', '全部'], ['formal', '正式 Agent'], ['test', '测试 Agent']] as const).map(([value, label]) => (
              <button type="button" className={category === value ? 'selected' : ''} key={value} onClick={() => setCategory(value)}>{label}</button>
            ))}
            <span className="agent-filter-divider" />
            {([['all', '全部类型'], ['Supervisor', 'Supervisor'], ['Specialist', 'Specialist'], ['error', '异常']] as const).map(([value, label]) => (
              <button type="button" className={typeFilter === value ? 'selected' : ''} key={value} onClick={() => setTypeFilter(value)}>{label}</button>
            ))}
          </div>
          <div className="agent-card-grid">
            {pagedAgents.map((agent) => (
              <button type="button" className={`agent-select-card ${selected?.id === agent.id ? 'active' : ''}`} key={agent.id} onClick={() => void loadDetail(agent.id)}>
                <div className="agent-select-card-header"><span className="agent-list-icon"><RobotOutlined /></span><strong>{agent.name}</strong><Tag color={agent.enabled ? 'green' : 'default'}>{agent.enabled ? '启用' : '停用'}</Tag></div>
                <p className="agent-select-description">{agent.description || agent.domain || '暂无职责说明'}</p>
                <div className="agent-select-meta"><Tag color={agent.type === 'Supervisor' ? 'blue' : 'default'}>{agent.type}</Tag><span>今日 {agent.todayRuns}</span><span>成功率 {agent.successRate === null ? '—' : `${agent.successRate}%`}</span></div>
              </button>
            ))}
            {!filteredAgents.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有匹配的 Agent" /> : null}
          </div>
          {filteredAgents.length > PAGE_SIZE ? <div className="agent-pagination"><span>共 {filteredAgents.length} 个 Agent</span><button type="button" disabled={agentPage <= 1} onClick={() => setAgentPage((p) => p - 1)}>‹</button>{Array.from({ length: pageCount }, (_, index) => index + 1).map((page) => <button type="button" className={page === agentPage ? 'selected' : ''} key={page} onClick={() => setAgentPage(page)}>{page}</button>)}<button type="button" disabled={agentPage >= pageCount} onClick={() => setAgentPage((p) => p + 1)}>›</button></div> : <div className="agent-pagination"><span>共 {filteredAgents.length} 个 Agent</span></div>}
        </Card>
        <Card className="agent-detail-panel agent-detail-workspace" title={selected ? <div className="agent-detail-title">
          <div className="agent-list-icon"><RobotOutlined /></div>
          <div><h2>{selected.name}</h2><p>{selected.slug} · {selected.description || '暂无描述'}</p></div>
          <Space>
            <Switch checked={selected.enabled} loading={toggling} onChange={() => void toggleStatus(selected)} checkedChildren="启用" unCheckedChildren="停用" />
          </Space>
        </div> : 'Agent 详情'}>
          {selected ? <Tabs defaultActiveKey="basic" items={[
            {
              key: 'basic', label: '基本信息',
              children: <div className="agent-basic-layout">
                <Card className="agent-subcard agent-basic-card" title="基本信息">
                  <div className="agent-info-grid">
                    {[['名称', selected.name], ['唯一标识', selected.slug], ['描述', selected.description || '—'], ['Agent 类型', selected.type], ['所属业务域', selected.domain], ['状态', selected.enabled ? '启用中' : '已停用'], ['绑定模型', selected.model_name || selected.model || '未配置'], ['创建时间', selected.createdAt ? new Date(selected.createdAt).toLocaleString('zh-CN', { hour12: false }) : '—'], ['最后更新时间', selected.updatedAt ? new Date(selected.updatedAt).toLocaleString('zh-CN', { hour12: false }) : '—']].map(([key, value]) => (
                      <div key={key as string}><span>{key}</span><b>{value}</b></div>
                    ))}
                    <div className="agent-info-wide"><span>职责说明</span><b>{selected.responsibilities.length ? selected.responsibilities.map((item) => <Tag key={item}>{item}</Tag>) : '未配置'}</b></div>
                  </div>
                </Card>
                <div className="agent-detail-stat-strip">
                  {[['今日运行', selected.todayRuns], ['近7天运行', selected.weekRuns], ['成功率', selected.successRate === null ? '—' : `${selected.successRate}%`], ['平均响应', selected.latency === null ? '—' : `${selected.latency}s`], ['知识库命中率', selected.hitRate === null ? '—' : `${selected.hitRate}%`]].map(([label, value]) => <div key={label as string}><span>{label}</span><b>{value}</b></div>)}
                </div>
              </div>,
            },
            {
              key: 'capability', label: '能力配置',
              children: <div className="agent-capabilities">{CAPABILITY_META.map(([key, title, desc]) => (
                <div className="agent-capability" key={key}><div><b>{title}</b><p>{desc}</p></div><Switch checked={Boolean(selected.capabilities[key as keyof AgentItem['capabilities']])} disabled /></div>
              ))}</div>,
            },
            {
              key: 'resources', label: '绑定资源',
              children: <Row gutter={[12, 12]}>
                {[['绑定模型', selected.model_name ? [selected.model] : [], <RobotOutlined key="m" />], ['绑定知识库', selected.knowledgeBases.map((item) => item.name), <DatabaseOutlined key="d" />], ['绑定工具', selected.tools.map((item) => item.name), <ToolOutlined key="t" />]].map(([title, list, icon]) => (
                  <Col span={24} md={8} key={title as string}>
                    <Card className="agent-resource-card"><h4>{icon} {title as string}</h4>
                      {(list as string[]).length ? (list as string[]).map((item) => <div className="resource-row" key={item}><span>{item}</span><Tag color="green">正常</Tag></div>) : <p className="resource-empty">未绑定</p>}
                      <small>共 {(list as string[]).length} 项资源</small>
                    </Card>
                  </Col>
                ))}
              </Row>,
            },
            {
              key: 'monitoring', label: '运行监控',
              children: <><div className="agent-metrics-grid">
                {[['今日运行次数', selected.todayRuns], ['近7天运行次数', selected.weekRuns], ['成功率', selected.successRate !== null ? `${selected.successRate}%` : '—'], ['平均响应时间', selected.latency !== null ? `${selected.latency}s` : '—'], ['知识库命中率', selected.hitRate !== null ? `${selected.hitRate}%` : '—'], ['近7天异常次数', selected.exceptions]].map(([label, value]) => (
                  <div className="agent-metric" key={label as string}><span>{label}</span><b>{value}</b></div>
                ))}
              </div>
              <Card className="agent-subcard agent-trend" title="近7天调用趋势">
                {trend.length ? <><svg viewBox="0 0 700 160" role="img" aria-label="近7天调用趋势">
                  {(() => { const max = Math.max(...trend.map(([, value]) => value), 1); const points = trend.map(([, value], index) => `${30 + (index * 640) / Math.max(trend.length - 1, 1)},${135 - (value / max) * 100}`).join(' '); return <><polyline points={points} fill="none" stroke="#16a34a" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />{trend.map(([date, value], index) => { const x = 30 + (index * 640) / Math.max(trend.length - 1, 1); const y = 135 - (value / max) * 100; return <g key={date}><circle cx={x} cy={y} r="5" fill="#fff" stroke="#16a34a" strokeWidth="3" /><text x={x} y="154" textAnchor="middle">{date.slice(5)}</text><text x={x} y={y - 10} textAnchor="middle">{value}</text></g> })}</> })()}
                </svg></> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无近7天运行数据" />}
              </Card>
              <Card className="agent-subcard" title="最近运行记录">
                {runs.length ? <div className="agent-run-list">{runs.slice(0, 8).map((run) => {
                  const meta = RUN_STATUS_META[run.status] ?? { label: run.status, color: 'default' }
                  return <div className="agent-run-item" key={run.id}>
                    <Tag color={meta.color}>{meta.label}</Tag>
                    <span className="agent-run-input">{run.input || '—'}</span>
                    <small>{run.latency !== null ? `${(run.latency / 1000).toFixed(2)}s` : ''}</small>
                    <small>{run.time ? new Date(run.time).toLocaleString('zh-CN', { hour12: false }) : ''}</small>
                  </div>
                })}</div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无运行记录" />}
              </Card></>,
            },
            {
              key: 'debug', label: '测试调试',
              children: <Row gutter={[16, 16]}><Col span={24}>
                <Card className="agent-subcard" title="测试输入">
                  <Input.TextArea rows={4} value={testInput} onChange={(e) => setTestInput(e.target.value)} placeholder="输入测试内容，将真实调用 Agent Runtime" />
                  <Button type="primary" icon={<PlayCircleOutlined />} loading={testing} onClick={() => void runTest()} style={{ marginTop: 12 }}>运行测试</Button>
                  {testResult ? <pre className="agent-test-result">{testResult}</pre> : null}
                </Card>
              </Col></Row>,
            },
          ]} /> : null}
        </Card>
      </div>
    ) : <Empty description="暂无 Agent，请先创建企业 AI Agent" />}
  </section>
}
