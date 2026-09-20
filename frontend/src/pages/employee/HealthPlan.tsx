import { CheckOutlined, ClockCircleOutlined, ExperimentOutlined, FileTextOutlined, FlagOutlined, FireOutlined, PauseOutlined, PlayCircleOutlined, RobotOutlined, StopOutlined, TrophyOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Checkbox, Col, Empty, Progress, Row, Table, Tabs, Tag, message } from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  completeHealthPlan, completeHealthPlanTask, getCurrentHealthPlan, getHealthPlans, pauseHealthPlan, resumeHealthPlan, uncompleteHealthPlanTask,
  type HealthPlan, type HealthPlanSummary, type HealthPlanTask,
} from '../../api/healthPlans'
import './health-plan.css'

const statusMeta: Record<string, { label: string; color: string }> = {
  active: { label: '执行中', color: 'success' },
  paused: { label: '已暂停', color: 'warning' },
  completed: { label: '已完成', color: 'default' },
  cancelled: { label: '已取消', color: 'error' },
  draft: { label: '草稿', color: 'default' },
}
const typeText: Record<string, string> = { sleep: '睡眠', nutrition: '饮食', exercise: '运动', mental: '心理', general: '通用' }
const sourceText: Record<string, string> = { manual: '手动完成', wearable: '设备同步', health_profile: '档案同步', mental_checkin: '心理打卡' }

const PLAN_TYPE_ICON: Record<string, React.ReactNode> = { sleep: <ClockCircleOutlined />, nutrition: <FileTextOutlined />, exercise: <FlagOutlined />, mental: <TrophyOutlined /> }

function formatDate(value?: string | null) {
  if (!value) return ''
  return value.slice(0, 10)
}

function todayTasks(plan: HealthPlan): HealthPlanTask[] {
  const today = new Date().toISOString().slice(0, 10)
  const byDate = plan.tasks.filter((task) => task.task_date === today)
  if (byDate.length) return byDate
  const current = plan.current_day ?? 1
  return plan.tasks.filter((task) => task.day_index === current)
}

function CurrentPlanCard({ plan, loading, onPause, onResume, onComplete, onViewDetail }: {
  plan: HealthPlan | null
  loading: boolean
  onPause: () => void
  onResume: () => void
  onComplete: () => void
  onViewDetail: () => void
}) {
  const navigate = useNavigate()
  if (loading) return <Card className="plan-card" loading />
  if (!plan || plan.status === 'none') {
    return <Card className="plan-card plan-empty-card">
      <div className="plan-empty">
        <div className="plan-empty-icon"><ExperimentOutlined /></div>
        <h3>暂无进行中的健康计划</h3>
        <p>把健康建议转化为可执行的每日行动，先从生成一个计划开始</p>
        <Button type="primary" icon={<RobotOutlined />} onClick={() => navigate('/employee/assistant')}>生成健康计划</Button>
      </div>
    </Card>
  }
  const meta = statusMeta[plan.status] ?? { label: plan.status, color: 'default' }
  const stats = plan.stats
  const rate = Math.round(stats?.task_completion_rate ?? 0)
  const goals = (plan.goal || '').split(/[；;、]/).filter(Boolean)
  const icon = PLAN_TYPE_ICON[plan.plan_type] ?? <ExperimentOutlined />
  const paused = plan.status === 'paused'
  return <Card className="plan-card plan-current-card">
    <div className="plan-current-head">
      <div className="plan-current-icon">{icon}</div>
      <div className="plan-current-main">
        <div className="plan-current-title"><h2>{plan.plan_name}</h2><Tag color={meta.color}>{meta.label}</Tag></div>
        <p className="plan-current-meta">时间：{formatDate(plan.start_date)} ～ {formatDate(plan.end_date)}　·　当前：Day {plan.current_day ?? 1} / {plan.duration_days}</p>
        <div className="plan-current-progress"><Progress percent={rate} status={paused ? 'normal' : 'active'} strokeColor="#16a34a" /></div>
        {goals.length > 0 && <ul className="plan-goals">{goals.slice(0, 3).map((goal) => <li key={goal}>{goal}</li>)}</ul>}
      </div>
      <div className="plan-current-actions">
        <Button icon={<FileTextOutlined />} onClick={onViewDetail}>查看详情</Button>
        {paused
          ? <Button icon={<PlayCircleOutlined />} onClick={onResume}>恢复计划</Button>
          : <Button icon={<PauseOutlined />} onClick={onPause}>暂停计划</Button>}
        <Button danger icon={<StopOutlined />} onClick={onComplete}>结束计划</Button>
      </div>
    </div>
    <div className="plan-source-line">来源：<b>{plan.source_agent === 'health_plan_agent' ? 'AI Health Plan Agent' : plan.source_agent}</b></div>
  </Card>
}

function TodayTasks({ plan, onToggle }: { plan: HealthPlan | null; onToggle: (task: HealthPlanTask) => void }) {
  if (!plan || plan.status === 'none') return <Card className="plan-card"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无进行中的计划" /></Card>
  const tasks = todayTasks(plan)
  const today = new Date().toISOString().slice(0, 10)
  return <Card className="plan-card" title={<div className="plan-block-title">今日健康任务<small>{today}</small></div>}>
    <div className="plan-tasks">
      {tasks.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="今日暂无任务" />}
      {tasks.map((task) => {
        const done = task.completion_status === 'completed'
        return <div className={`plan-task ${done ? 'done' : ''}`} key={task.id}>
          <Checkbox checked={done} onChange={() => onToggle(task)} />
          <div className="plan-task-body">
            <div className="plan-task-title">{task.title}</div>
            <div className="plan-task-sub">
              {task.actual_value ? <span className="plan-task-progress">当前 {task.actual_value}</span> : null}
              {done && task.completed_at ? <span className="plan-task-time">已完成 · {new Date(task.completed_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })}</span> : null}
              <span className="plan-task-source">{sourceText[task.completion_source] ?? task.completion_source}</span>
            </div>
          </div>
        </div>
      })}
    </div>
  </Card>
}

function ProgressStats({ plan }: { plan: HealthPlan | null }) {
  const stats = plan?.stats
  const items = [
    { label: '执行天数', value: stats ? `${stats.executed_days} / ${stats.total_days}` : '--', icon: <ExperimentOutlined />, color: '#16a34a' },
    { label: '任务完成率', value: stats ? `${Math.round(stats.task_completion_rate)}%` : '--', icon: <CheckOutlined />, color: '#0891b2' },
    { label: '连续执行', value: stats ? `${stats.streak_days}天` : '--', icon: <FireOutlined />, color: '#d97706' },
    { label: '已完成任务', value: stats ? `${stats.completed_tasks} / ${stats.total_tasks}` : '--', icon: <TrophyOutlined />, color: '#7c3aed' },
  ]
  return <Card className="plan-card" title="执行进度">
    <div className="plan-stats">
      {items.map((item) => <div className="plan-stat" key={item.label}>
        <div className="plan-stat-icon" style={{ background: `${item.color}1a`, color: item.color }}>{item.icon}</div>
        <div><small>{item.label}</small><b>{item.value}</b></div>
      </div>)}
    </div>
    <div className="plan-stats-note">数据由数据库中的真实任务状态实时计算，健康改善效果将在接入健康趋势数据后展示。</div>
  </Card>
}

function PlanTimeline({ plan }: { plan: HealthPlan | null }) {
  const [activeDay, setActiveDay] = useState<number>(plan?.current_day ?? 1)
  useEffect(() => { setActiveDay(plan?.current_day ?? 1) }, [plan?.id, plan?.current_day])
  if (!plan || plan.status === 'none') return <Card className="plan-card"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无计划" /></Card>
  const days = Array.from({ length: plan.duration_days }, (_, index) => index + 1)
  const dayTasks = plan.tasks.filter((task) => task.day_index === activeDay)
  const completedOf = (day: number) => plan.tasks.filter((task) => task.day_index === day && task.completion_status === 'completed').length
  const totalOf = (day: number) => plan.tasks.filter((task) => task.day_index === day).length
  return <Card className="plan-card plan-timeline-card" id="plan-timeline" title="计划时间线">
    <div className="plan-day-tabs">
      {days.map((day) => {
        const done = completedOf(day)
        const total = totalOf(day)
        const active = day === activeDay
        const isCurrent = day === (plan.current_day ?? 1)
        return <button key={day} className={`plan-day-tab ${active ? 'active' : ''} ${isCurrent ? 'current' : ''}`} onClick={() => setActiveDay(day)}>
          <b>Day {day}</b>
          <small>{done === total && total > 0 ? '✓ 已完成' : `${done}/${total}`}</small>
        </button>
      })}
    </div>
    <div className="plan-day-tasks">
      <h4>Day {activeDay} · {formatDate(dayTasks[0]?.task_date)} {activeDay === plan.current_day ? <Tag color="green">今日</Tag> : null}</h4>
      {dayTasks.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="该天暂无任务" />}
      {dayTasks.map((task) => {
        const done = task.completion_status === 'completed'
        return <div className={`plan-day-task ${done ? 'done' : ''}`} key={task.id}>
          <span className="plan-day-task-mark">{done ? '✓' : '○'}</span>
          <span className="plan-day-task-title">{task.title}</span>
          <Tag color={done ? 'success' : 'default'}>{done ? '已完成' : '待执行'}</Tag>
        </div>
      })}
    </div>
  </Card>
}

function HistoryPlans({ plans, loading }: { plans: HealthPlanSummary[]; loading: boolean }) {
  const columns = [
    { title: '计划名称', dataIndex: 'plan_name', key: 'plan_name' },
    { title: '类型', dataIndex: 'plan_type', key: 'plan_type', width: 90, render: (value: string) => <Tag>{typeText[value] ?? value}</Tag> },
    { title: '开始日期', dataIndex: 'start_date', key: 'start_date', width: 120 },
    { title: '结束日期', dataIndex: 'end_date', key: 'end_date', width: 120 },
    { title: '完成率', key: 'rate', width: 110, render: (_: unknown, row: HealthPlanSummary) => <span>{row.stats ? `${Math.round(row.stats.task_completion_rate)}%` : '--'}</span> },
    { title: '状态', dataIndex: 'status', key: 'status', width: 90, render: (value: string) => { const meta = statusMeta[value] ?? { label: value, color: 'default' }; return <Tag color={meta.color}>{meta.label}</Tag> } },
  ]
  return <Card className="plan-card" title="历史健康计划">
    <Table rowKey="id" size="middle" loading={loading} columns={columns} dataSource={plans} pagination={false} locale={{ emptyText: '暂无历史计划' }} />
  </Card>
}

export function HealthPlanPage() {
  const [current, setCurrent] = useState<HealthPlan | null>(null)
  const [history, setHistory] = useState<HealthPlanSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const refresh = useCallback(async () => {
    const [plan, plans] = await Promise.all([getCurrentHealthPlan(), getHealthPlans()])
    setCurrent(plan)
    setHistory(plans)
  }, [])
  useEffect(() => {
    void (async () => { try { await refresh() } catch { message.error('健康计划加载失败') } finally { setLoading(false) } })()
  }, [refresh])
  const run = async (action: () => Promise<unknown>, successText: string) => {
    setActing(true)
    try {
      await action()
      await refresh()
      message.success(successText)
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '操作失败')
    } finally { setActing(false) }
  }
  const toggleTask = (task: HealthPlanTask) => {
    void run(
      () => task.completion_status === 'completed' ? uncompleteHealthPlanTask(task.id) : completeHealthPlanTask(task.id),
      task.completion_status === 'completed' ? '已取消完成' : '任务已完成',
    )
  }
  const scrollToTimeline = () => document.getElementById('plan-timeline')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  const active = current && current.status !== 'none' ? current : null
  return <section className="health-plan-page">
    <div className="plan-heading">
      <p>把健康建议转化为可执行的每日行动</p>
    </div>
    <CurrentPlanCard
      plan={active}
      loading={loading}
      onPause={() => active && void run(() => pauseHealthPlan(active.id), '计划已暂停')}
      onResume={() => active && void run(() => resumeHealthPlan(active.id), '计划已恢复')}
      onComplete={() => active && void run(() => completeHealthPlan(active.id), '计划已结束')}
      onViewDetail={scrollToTimeline}
    />
    <Row gutter={[16, 16]} align="stretch" style={{ display: 'flex', alignItems: 'stretch' }}>
      <Col xs={24} xl={14} style={{ display: 'flex' }}><div style={{ flex: 1, width: '100%' }}><TodayTasks plan={active} onToggle={toggleTask} /></div></Col>
      <Col xs={24} xl={10} style={{ display: 'flex' }}><div style={{ flex: 1, width: '100%' }}><ProgressStats plan={active} /></div></Col>
    </Row>
    <PlanTimeline plan={active} />
    <HistoryPlans plans={history} loading={loading} />
    {acting && <Alert className="plan-acting" type="info" showIcon message="正在更新…" />}
  </section>
}
