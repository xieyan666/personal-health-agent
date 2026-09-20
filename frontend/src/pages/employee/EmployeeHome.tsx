import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  CalendarOutlined,
  CheckCircleFilled,
  ClockCircleOutlined,
  FileTextOutlined,
  HeartOutlined,
  MedicineBoxOutlined,
  RightOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  SmileOutlined,
} from '@ant-design/icons'
import { Button, Card, Empty, Skeleton, Tag } from 'antd'
import { getDashboardSummary, type DashboardSummary } from '../../api/dashboard'
import { useAuthStore } from '../../store/authStore'
import './employee-home.css'

const QUICK_LINKS = [
  { title: 'AI 健康助手', description: '发起健康咨询', path: '/employee/assistant', icon: RobotOutlined },
  { title: '健康档案', description: '查看健康指标', path: '/employee/profile', icon: HeartOutlined },
  { title: '体检报告', description: '管理体检报告', path: '/employee/reports', icon: FileTextOutlined },
  { title: '健康计划', description: '完成今日任务', path: '/employee/plan', icon: CalendarOutlined },
  { title: '心理健康', description: '记录今日状态', path: '/employee/mental', icon: SmileOutlined },
  { title: '健康服务', description: '查看服务与预约', path: '/employee/services', icon: MedicineBoxOutlined },
]

function greetingForNow() {
  const hour = new Date().getHours()
  if (hour < 11) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
}

function formatDateTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '刚刚'
  const day = new Date()
  const sameDay = date.toDateString() === day.toDateString()
  return sameDay
    ? date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    : date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

function riskIcon(status: DashboardSummary['risk_summary']['status']) {
  return status === 'high' ? 'danger' : status === 'attention' ? 'attention' : status === 'normal' ? 'success' : 'empty'
}

export function EmployeeHome() {
  const navigate = useNavigate()
  const user = useAuthStore((state) => state.user)
  const [data, setData] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const loadSummary = useCallback(async () => {
    setLoading(true)
    setError(false)
    try {
      setData(await getDashboardSummary())
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void loadSummary() }, [loadSummary])

  const displayName = user?.displayName || user?.username || '员工'
  const overview = useMemo(() => {
    if (!data) return []
    const risk = data.risk_summary
    const plan = data.active_plan
    const mental = data.mental_today
    return [
      { label: '总体健康状态', value: data.health_overview.label, detail: data.health_overview.score == null ? '暂无已保存的综合评分' : `最近评估：${data.health_overview.score} 分`, path: '/employee/risk', icon: HeartOutlined, tone: 'success' },
      { label: '健康风险', value: risk.status === 'empty' ? '暂无评估' : risk.status === 'high' ? '需要关注' : risk.status === 'attention' ? '需关注' : '正常', detail: risk.primary_factor || (risk.attention_count ? `${risk.attention_count} 项需要关注` : '暂无需要关注的风险项'), path: '/employee/risk', icon: SafetyCertificateOutlined, tone: riskIcon(risk.status) },
      { label: '当前健康计划', value: plan.name || '暂无进行中的计划', detail: plan.name ? `第 ${plan.current_day || 0}/${plan.duration_days || 0} 天 · ${Math.round(plan.completion_rate || 0)}%` : '可从健康助手生成改善计划', path: '/employee/plan', icon: CalendarOutlined, tone: plan.name ? 'plan' : 'empty' },
      { label: '今日心理状态', value: mental.checked_in ? '今日已打卡' : '尚未记录', detail: mental.checked_in ? `情绪：${mental.mood || '已记录'}${mental.stress_level == null ? '' : ` · 压力：${mental.stress_level}/10`}` : '记录今日状态，持续关注自己', path: '/employee/mental', icon: SmileOutlined, tone: mental.checked_in ? 'success' : 'attention' },
    ]
  }, [data])

  if (loading) return <section className="employee-home"><Skeleton active paragraph={{ rows: 11 }} /></section>
  if (error || !data) return <section className="dashboard-error"><Empty description="健康工作台暂时无法加载"><Button type="primary" onClick={() => void loadSummary()}>重新加载</Button></Empty></section>

  return <section className="employee-home">
    <div className="dashboard-welcome">
      <div className="dashboard-welcome-copy"><h2>{greetingForNow()}，<span>{displayName}</span></h2><p>欢迎回来，这是你今天的健康概览。</p></div>
      <div className="dashboard-welcome-badge"><HeartOutlined />健康工作台</div>
    </div>

    <div className="dashboard-overview-grid">
      {overview.map((item) => { const Icon = item.icon; return <button className="dashboard-overview-card" key={item.label} onClick={() => navigate(item.path)}><span className={`dashboard-overview-icon ${item.tone}`}><Icon /></span><span><small>{item.label}</small><strong className="dashboard-clamp">{item.value}</strong><p className="dashboard-clamp">{item.detail}</p></span></button> })}
    </div>

    <div className="dashboard-split dashboard-split-primary">
      <Card className="dashboard-card" title="AI 今日建议" extra={<Tag color="green">规则驱动</Tag>}>
        {data.recommendations.length ? <div className="dashboard-recommendations">{data.recommendations.map((item, index) => <button className={`dashboard-recommendation ${item.tone}`} key={item.id} onClick={() => navigate(item.target_path)}><span className="dashboard-recommendation-number">0{index + 1}</span><span><b>{item.title}</b><p>{item.description}</p><small>来源：{item.source}</small></span><RightOutlined className="dashboard-action" /></button>)}</div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无今日建议" />}
      </Card>
      <Card className="dashboard-card" title="今日健康任务" extra={<Button type="link" onClick={() => navigate('/employee/plan')}>查看计划</Button>}>
        {data.today_tasks.length ? <div className="dashboard-tasks">{data.today_tasks.map((task) => <button className={`dashboard-task ${task.status}`} key={task.id} onClick={() => navigate(task.target_path)}>{task.status === 'completed' ? <CheckCircleFilled /> : <ClockCircleOutlined />}<div><b>{task.title}</b>{task.detail && <p>{task.detail}</p>}</div><Tag color={task.status === 'completed' ? 'green' : 'default'}>{task.status === 'completed' ? '已完成' : '待完成'}</Tag></button>)}</div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="今天暂无待办健康任务" />}
      </Card>
    </div>

    <div className="dashboard-split dashboard-split-secondary">
      <Card className="dashboard-card" title="最近健康动态">
        {data.recent_activities.length ? <div className="dashboard-activities">{data.recent_activities.map((activity) => <button key={activity.id} onClick={() => activity.target_path && navigate(activity.target_path)}><span className="dashboard-activity-dot" /><span><b>{activity.title}</b><small>{formatDateTime(activity.occurred_at)}</small></span><RightOutlined /></button>)}</div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无近期健康动态" />}
      </Card>
      <Card className="dashboard-card" title="快捷入口"><div className="dashboard-quick-links">{QUICK_LINKS.map((link) => { const Icon = link.icon; return <button key={link.path} onClick={() => navigate(link.path)}><span className="dashboard-quick-icon"><Icon /></span><span className="dashboard-quick-copy"><b>{link.title}</b><small>{link.description}</small></span></button> })}</div></Card>
    </div>
  </section>
}
