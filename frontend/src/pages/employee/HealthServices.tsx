import { BookOutlined, CalendarOutlined, CheckCircleOutlined, ClockCircleOutlined, CloseCircleOutlined, ExperimentOutlined, EyeOutlined, FileDoneOutlined, FlagOutlined, GlobalOutlined, HeartOutlined, LeftOutlined, MedicineBoxOutlined, PlusOutlined, RightOutlined, RobotOutlined, SafetyCertificateOutlined, TrophyOutlined, UsergroupAddOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Col, DatePicker, Drawer, Empty, Modal, Progress, Row, Select, Space, Tabs, Tag, message } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useCallback, useEffect, useState } from 'react'
import {
  cancelHealthActivity, cancelHealthServiceBooking, createHealthServiceBooking, getHealthActivities, getHealthActivity, getHealthBenefits, getHealthServiceBookings, getHealthServiceRecommendations, getHealthServices, getMyHealthActivities, joinHealthActivity,
  type EmployeeHealthBenefit, type HealthActivity, type HealthService, type HealthServiceBooking, type MyHealthActivity, type ServiceRecommendationItem,
} from '../../api/healthServices'
import './health-services.css'
import { approveAgentApproval, createAgentApproval, createDataConsent, getDataConsents } from '../../api/dataAuthorizations'

const CATEGORY_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  medical_exam: { label: '体检与检查', icon: <MedicineBoxOutlined />, color: '#0891b2' },
  medical_consult: { label: '医疗健康咨询', icon: <RobotOutlined />, color: '#7c3aed' },
  nutrition: { label: '营养健康', icon: <HeartOutlined />, color: '#d97706' },
  exercise: { label: '运动健康', icon: <FlagOutlined />, color: '#16a34a' },
  course: { label: '健康课程', icon: <SafetyCertificateOutlined />, color: '#dc2626' },
}
const BOOKING_STATUS_META: Record<string, { label: string; color: string }> = {
  pending: { label: '待确认', color: 'default' },
  confirmed: { label: '已预约', color: 'processing' },
  in_progress: { label: '进行中', color: 'success' },
  completed: { label: '已完成', color: 'default' },
  cancelled: { label: '已取消', color: 'error' },
}
const ACTIVITY_TYPE_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  lecture: { label: '健康讲座', icon: <SafetyCertificateOutlined />, color: '#0891b2' },
  exercise: { label: '运动活动', icon: <TrophyOutlined />, color: '#16a34a' },
  nutrition: { label: '营养课程', icon: <HeartOutlined />, color: '#d97706' },
  education: { label: '健康教育', icon: <BookOutlined />, color: '#7c3aed' },
  exam_promo: { label: '体检宣教', icon: <MedicineBoxOutlined />, color: '#dc2626' },
  other: { label: '其他', icon: <CalendarOutlined />, color: '#64748b' },
}
const ACTIVITY_STATUS_META: Record<string, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'default' },
  registration_open: { label: '报名中', color: 'green' },
  registration_closed: { label: '报名截止', color: 'orange' },
  ongoing: { label: '进行中', color: 'processing' },
  finished: { label: '已结束', color: 'default' },
  cancelled: { label: '已取消', color: 'red' },
  active: { label: '进行中', color: 'processing' },
}

function BookingModal({ service, onClose, onBooked }: { service: HealthService | null; onClose: () => void; onBooked: () => void }) {
  const [date, setDate] = useState<Dayjs | null>(dayjs().add(1, 'day'))
  const [time, setTime] = useState('10:00')
  const [submitting, setSubmitting] = useState(false)
  const [missingScopes, setMissingScopes] = useState<string[]>([])
  const requiredScopes = service?.category === 'nutrition' || service?.category === 'medical_consult'
    ? ['health_profile.read', 'health_plan.read', 'health_service.booking.create']
    : ['health_profile.read', 'health_service.booking.create']
  const submitBooking = async () => {
    if (!service || !date) return
    const bookingPayload = { service_id: service.id, booking_date: date.format('YYYY-MM-DD'), booking_time: time }
    const approval = await createAgentApproval({ action_type: 'health_service.booking.create', action_payload: bookingPayload })
    await approveAgentApproval(approval.id, '员工已确认创建健康服务预约')
    await createHealthServiceBooking({ ...bookingPayload, approval_id: approval.id })
  }
  const submit = async () => {
    if (!service || !date) return
    setSubmitting(true)
    try {
      const consents = await getDataConsents()
      const missing = requiredScopes.filter((scope) => !consents.some((item) => item.scope === scope && item.status === 'active'))
      if (missing.length) { setMissingScopes(missing); return }
      await submitBooking()
      message.success('预约已提交，等待确认')
      onBooked()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '预约失败')
    } finally { setSubmitting(false) }
  }
  const grantAndBook = async () => {
    if (!service) return
    setSubmitting(true)
    try {
      await Promise.all(missingScopes.map((scope) => createDataConsent({ grantee_type: scope.startsWith('health_service') ? 'service' : 'agent', grantee_id: scope.startsWith('health_service') ? 'health_service_agent' : 'health_supervisor_agent', scope, purpose: `用于本次「${service.name}」健康服务预约与服务准备`, expires_at: null })))
      await submitBooking()
      message.success('已完成授权并提交预约')
      setMissingScopes([]); onBooked()
    } catch (error: any) { message.error(error?.response?.data?.detail || '授权并预约失败') } finally { setSubmitting(false) }
  }
  return <Modal open={Boolean(service)} title={service ? `预约：${service.name}` : ''} onCancel={onClose} footer={<><Button onClick={onClose}>取消</Button><Button type="primary" loading={submitting} onClick={() => void submit()}>{missingScopes.length ? '重新检查授权' : '确认预约'}</Button></>} destroyOnClose>
    {service && <div className="svc-modal-info"><p>{service.description}</p>{service.duration_minutes ? <p>时长：{service.duration_minutes} 分钟 · {service.delivery_mode === 'online' ? '线上服务' : '线下服务'}</p> : null}</div>}
    <div className="svc-modal-form">
      <div><label>预约日期</label><DatePicker value={date} onChange={setDate} disabledDate={(current) => current && current < dayjs().startOf('day')} style={{ width: '100%' }} /></div>
      <div><label>预约时间</label><Select value={time} onChange={setTime} options={['09:00', '10:00', '11:00', '14:00', '14:30', '15:00', '16:00'].map((item) => ({ value: item, label: item }))} style={{ width: '100%' }} /></div>
    </div>
    {missingScopes.length ? <Alert type="warning" showIcon message="本次服务需要你先授权以下数据" description={<><p>缺少范围：{missingScopes.join('、')}</p><Button type="primary" loading={submitting} onClick={() => void grantAndBook()}>授权并预约</Button></>} /> : null}
  </Modal>
}

const SOURCE_META: Record<string, { label: string; color: string }> = {
  'Health Report': { label: '体检报告', color: 'blue' },
  'AI Report Analysis': { label: 'AI 解读', color: 'cyan' },
  'Health Plan': { label: '健康计划', color: 'green' },
  'Health Risk': { label: '健康风险', color: 'orange' },
  'Health Trend': { label: '健康趋势', color: 'purple' },
}

function Recommendations({ items, loading, aiStatus, onBook, onBrowseAll }: {
  items: ServiceRecommendationItem[]
  loading: boolean
  aiStatus?: string
  onBook: (serviceId: string) => void
  onBrowseAll: () => void
}) {
  if (loading) return <Card className="svc-card" title="为你推荐"><div className="svc-recommend-loading"><span className="svc-recommend-spinner" />正在分析适合你的健康服务...</div></Card>
  if (!items.length) return <Card className="svc-card" title="为你推荐">
    <div className="svc-recommend-empty">
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂未发现需要特别推荐的健康服务" />
      <Button type="primary" ghost onClick={onBrowseAll}>浏览全部服务</Button>
    </div>
  </Card>
  return <Card className="svc-card" title="为你推荐" extra={<span className="svc-recommend-subtitle">根据你的近期健康状态与计划，为你匹配适合的健康服务{aiStatus === 'fallback' ? ' · 智能解释暂不可用' : ''}</span>}>
    <Row gutter={[16, 16]}>
      {items.map((item) => {
        const categoryMeta = CATEGORY_META[item.category] ?? { label: item.category, icon: <HeartOutlined />, color: '#16a34a' }
        return <Col xs={24} md={8} key={item.service_id}>
          <div className="svc-recommend">
            <div className="svc-recommend-icon" style={{ background: `${categoryMeta.color}1a`, color: categoryMeta.color }}>{categoryMeta.icon}</div>
            <div className="svc-recommend-body">
              <div className="svc-recommend-title"><h4>{item.service_name}</h4><Tag color="default" style={{ margin: 0 }}>{categoryMeta.label}</Tag></div>
              <p className="svc-recommend-reason">{item.reason}</p>
              <div className="svc-recommend-sources">{(item.sources || []).map((source) => { const meta = SOURCE_META[source] ?? { label: source, color: 'default' }; return <Tag key={source} color={meta.color}>{meta.label}</Tag> })}</div>
              <Button size="small" type="primary" ghost icon={<BookOutlined />} onClick={() => onBook(item.service_id)}>预约</Button>
            </div>
          </div>
        </Col>
      })}
    </Row>
  </Card>
}

function ServiceCatalog({ services, onBook }: { services: HealthService[]; onBook: (service: HealthService) => void }) {
  const groups = Object.entries(CATEGORY_META).map(([category, meta]) => ({
    category, ...meta, items: services.filter((service) => service.category === category),
  }))
  return <Card className="svc-card" title="健康服务">
    <Tabs
      items={groups.map((group) => ({
        key: group.category,
        label: <span><span className="svc-tab-icon" style={{ color: group.color }}>{group.icon}</span>{group.label}</span>,
        children: <div className="svc-grid">{group.items.map((service) => (
          <div className="svc-service" key={service.id}>
            <div className="svc-service-head"><h4>{service.name}</h4>{service.is_annual_check ? <Tag color="green">年度体检</Tag> : null}</div>
            <p className="svc-service-desc">{service.description}</p>
            <div className="svc-service-meta">
              <span><ClockCircleOutlined /> {service.duration_minutes ? `${service.duration_minutes}分钟` : '--'}</span>
              <span><GlobalOutlined /> {service.delivery_mode === 'online' ? '线上' : '线下'}</span>
            </div>
            <p className="svc-service-suit">{service.suitability}</p>
            <Button size="small" type="primary" icon={<BookOutlined />} onClick={() => onBook(service)}>预约</Button>
          </div>
        ))}</div>,
      }))}
    />
  </Card>
}

function MyBookings({ bookings, onCancel }: { bookings: HealthServiceBooking[]; onCancel: (booking: HealthServiceBooking) => void }) {
  const cancellable = (status: string) => ['pending', 'confirmed'].includes(status)
  return <Card className="svc-card" title="我的预约">
    {bookings.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无预约" /> : <div className="svc-booking-list">
      {bookings.map((booking) => {
        const meta = BOOKING_STATUS_META[booking.status] ?? { label: booking.status, color: 'default' }
        return <div className="svc-booking" key={booking.id}>
          <div className="svc-booking-date"><b>{dayjs(booking.booking_date).format('MM月DD日')}</b><span>{booking.booking_time}</span></div>
          <div className="svc-booking-body">
            <h4>{booking.service_name}</h4>
            <p>{CATEGORY_META[booking.category]?.label ?? ''} · {booking.provider || '服务待分配'}</p>
          </div>
          <div className="svc-booking-status"><Tag color={meta.color}>{meta.label}</Tag>{cancellable(booking.status) ? <Button size="small" danger type="text" icon={<CloseCircleOutlined />} onClick={() => onCancel(booking)}>取消预约</Button> : null}</div>
        </div>
      })}
    </div>}
  </Card>
}

function MyBenefits({ benefits }: { benefits: EmployeeHealthBenefit[] }) {
  return <Card className="svc-card" title="我的健康权益">
    {benefits.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无权益数据" /> : <div className="svc-benefits">
      {benefits.map((benefit) => {
        const percent = benefit.annual_quota ? Math.round(benefit.used_quota / benefit.annual_quota * 100) : 0
        return <div className="svc-benefit" key={benefit.id}>
          <div className="svc-benefit-head"><b>{benefit.benefit_name}</b><span>{benefit.used_quota} / {benefit.annual_quota} 次 / 年</span></div>
          <Progress percent={percent} strokeColor="#16a34a" size="small" showInfo={false} />
          <div className="svc-benefit-remain">剩余 <b>{benefit.remaining_quota}</b> 次</div>
        </div>
      })}
    </div>}
  </Card>
}

function activityTimeText(activity: HealthActivity) {
  if (!activity.start_date) return '待定'
  const date = `${dayjs(activity.start_date).format('YYYY年MM月DD日')}${activity.end_date && activity.end_date !== activity.start_date ? ` ~ ${dayjs(activity.end_date).format('MM月DD日')}` : ''}`
  const time = activity.start_time ? `${activity.start_time}${activity.end_time ? `-${activity.end_time}` : ''}` : ''
  return time ? `${date} ${time}` : date
}

function ActivityDetailDrawer({ activity, onClose, onJoin, onCancel }: {
  activity: HealthActivity | null
  onClose: () => void
  onJoin: () => void
  onCancel: () => void
}) {
  const meta = activity ? ACTIVITY_TYPE_META[activity.activity_type] ?? ACTIVITY_TYPE_META.other : ACTIVITY_TYPE_META.other
  const statusMeta = activity ? ACTIVITY_STATUS_META[activity.display_status] ?? { label: activity.display_status, color: 'default' } : { label: '', color: 'default' }
  const registrable = activity?.display_status === 'registration_open'
  return <Drawer title="活动详情" width={480} open={Boolean(activity)} onClose={onClose}>
    {activity ? <div className="svc-activity-detail">
      <div className="svc-activity-detail-head">
        <div className="svc-activity-detail-icon" style={{ background: `${meta.color}1a`, color: meta.color }}>{meta.icon}</div>
        <div>
          <h3>{activity.name}</h3>
          <Space size={4} wrap>
            <Tag color="green" style={{ margin: 0 }}>{meta.label}</Tag>
            <Tag color={statusMeta.color} style={{ margin: 0 }}>{statusMeta.label}</Tag>
          </Space>
        </div>
      </div>
      <div className="svc-activity-detail-grid">
        <span>活动时间</span><b>{activityTimeText(activity)}</b>
        <span>活动形式</span><b>{activity.delivery_mode === 'online' ? '线上' : '线下'}{activity.location ? ` · ${activity.location}` : ''}</b>
        <span>主办方</span><b>{activity.organizer ?? '—'}{activity.contact_person ? ` · ${activity.contact_person}` : ''}</b>
        <span>参与范围</span><b>{activity.scope === 'department' ? `指定部门：${activity.target_department}` : '全体员工'}</b>
        <span>报名截止</span><b>{activity.registration_deadline ? dayjs(activity.registration_deadline).format('YYYY-MM-DD HH:mm') : '—'}</b>
        <span>报名情况</span><b className="svc-activity-detail-strong">{activity.participants} / {activity.capacity ?? '不限'} 人{activity.remaining !== null && activity.remaining !== undefined ? `（剩余 ${activity.remaining} 名额）` : ''}</b>
      </div>
      {activity.description ? <p className="svc-activity-detail-desc">{activity.description}</p> : null}
      <div className="svc-activity-detail-actions">
        {activity.joined
          ? <Button danger icon={<CloseCircleOutlined />} onClick={onCancel}>取消报名</Button>
          : <Button type="primary" icon={<PlusOutlined />} disabled={!registrable || activity.remaining === 0} onClick={onJoin}>{!registrable ? (activity.display_status === 'registration_closed' ? '报名已截止' : '当前不可报名') : activity.remaining === 0 ? '名额已满' : '立即报名'}</Button>}
      </div>
    </div> : null}
  </Drawer>
}

function ActivityCard({ activity, onDetail, onJoin, onCancel }: {
  activity: HealthActivity
  onDetail: () => void
  onJoin: () => void
  onCancel: () => void
}) {
  const meta = ACTIVITY_TYPE_META[activity.activity_type] ?? ACTIVITY_TYPE_META.other
  const statusMeta = ACTIVITY_STATUS_META[activity.display_status] ?? { label: activity.display_status, color: 'default' }
  const registrable = activity.display_status === 'registration_open'
  const progress = activity.capacity ? Math.min(Math.round(activity.participants / activity.capacity * 100), 100) : 0
  return <div className="svc-activity-card">
    <div className="svc-activity-card-top">
      <div className="svc-activity-card-icon" style={{ background: `${meta.color}1a`, color: meta.color }}>{meta.icon}</div>
      <Tag color={statusMeta.color}>{statusMeta.label}</Tag>
    </div>
    <h4>{activity.name}</h4>
    <p className="svc-activity-card-desc">{activity.description || '暂无活动简介'}</p>
    <div className="svc-activity-card-meta">
      <span><CalendarOutlined /> {activityTimeText(activity)}</span>
      <span><GlobalOutlined /> {activity.delivery_mode === 'online' ? '线上' : '线下'}{activity.location ? ` · ${activity.location}` : ''}</span>
      <span><UsergroupAddOutlined /> 已报名 {activity.participants}{activity.capacity ? ` / ${activity.capacity}` : ''}</span>
      {activity.remaining !== null && activity.remaining !== undefined ? <span className={activity.remaining === 0 ? 'svc-activity-card-full' : ''}>剩余名额 {activity.remaining}</span> : null}
      {activity.registration_deadline ? <span><ClockCircleOutlined /> 报名截止 {dayjs(activity.registration_deadline).format('MM-DD HH:mm')}</span> : null}
    </div>
    {activity.capacity ? <Progress percent={progress} strokeColor={progress >= 100 ? '#ef4444' : '#16a34a'} size="small" showInfo={false} /> : null}
    <div className="svc-activity-card-actions">
      <Button size="small" icon={<EyeOutlined />} onClick={onDetail}>查看详情</Button>
      {activity.joined
        ? <><Button size="small" disabled icon={<CheckCircleOutlined />}>已报名</Button><Button size="small" danger type="text" onClick={onCancel}>取消报名</Button></>
        : <Button size="small" type="primary" icon={<PlusOutlined />} disabled={!registrable || activity.remaining === 0} onClick={onJoin}>{!registrable ? (activity.display_status === 'registration_closed' ? '报名已截止' : '不可报名') : activity.remaining === 0 ? '名额已满' : '立即报名'}</Button>}
    </div>
  </div>
}

function EnterpriseActivities({ activities, loading, onDetail, onJoin, onCancel }: {
  activities: HealthActivity[]
  loading: boolean
  onDetail: (activity: HealthActivity) => void
  onJoin: (activity: HealthActivity) => void
  onCancel: (activity: HealthActivity) => void
}) {
  return <Card className="svc-card" title="企业健康活动" extra={<span className="svc-recommend-subtitle">由企业发布的健康讲座、运动与教育类活动</span>}>
    {loading ? <div className="svc-recommend-loading"><span className="svc-recommend-spinner" />正在加载活动...</div> : activities.length
      ? <Row gutter={[16, 16]}>
        {activities.map((activity) => (
          <Col xs={24} md={12} xl={8} key={activity.id}>
            <ActivityCard activity={activity} onDetail={() => onDetail(activity)} onJoin={() => onJoin(activity)} onCancel={() => onCancel(activity)} />
          </Col>
        ))}
      </Row>
      : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可报名的企业健康活动" />}
  </Card>
}

const MY_GROUP_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  upcoming: { label: '待参加', color: 'green', icon: <CalendarOutlined /> },
  finished: { label: '已完成', color: 'default', icon: <CheckCircleOutlined /> },
  cancelled: { label: '已取消', color: 'default', icon: <CloseCircleOutlined /> },
}

function MyActivities({ items, loading, onDetail }: {
  items: MyHealthActivity[]
  loading: boolean
  onDetail: (activity: HealthActivity) => void
}) {
  const groups = (['upcoming', 'finished', 'cancelled'] as const).map((group) => {
    const meta = MY_GROUP_META[group]
    const list = items.filter((item) => item.group === group)
    return {
      key: group,
      label: <span><span className="svc-tab-icon" style={{ color: group === 'upcoming' ? '#16a34a' : '#94a3b8' }}>{meta.icon}</span>{meta.label}（{list.length}）</span>,
      children: loading ? <div className="svc-recommend-loading"><span className="svc-recommend-spinner" />正在加载...</div> : list.length ? <div className="svc-my-list">
        {list.map((item) => {
          const activity = item.activity
          const typeMeta = ACTIVITY_TYPE_META[activity.activity_type] ?? ACTIVITY_TYPE_META.other
          const statusMeta = ACTIVITY_STATUS_META[activity.display_status] ?? { label: activity.display_status, color: 'default' }
          return <div className="svc-my-item" key={item.id}>
            <div className="svc-my-icon" style={{ background: `${typeMeta.color}1a`, color: typeMeta.color }}>{typeMeta.icon}</div>
            <div className="svc-my-body">
              <h4>{activity.name}</h4>
              <p><CalendarOutlined /> {activityTimeText(activity)}</p>
              <p><GlobalOutlined /> {activity.delivery_mode === 'online' ? '线上' : '线下'}{activity.location ? ` · ${activity.location}` : ''}</p>
              {item.group === 'cancelled' ? <p className="svc-my-cancel-note">报名于 {item.joined_at ? dayjs(item.joined_at).format('YYYY-MM-DD HH:mm') : ''} 取消，仍保留参与记录</p> : null}
            </div>
            <div className="svc-my-status">
              <Tag color={statusMeta.color}>{statusMeta.label}</Tag>
              <Button size="small" icon={<EyeOutlined />} onClick={() => onDetail(activity)}>详情</Button>
            </div>
          </div>
        })}
      </div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无相关内容" />,
    }
  })
  return <Card className="svc-card" title="我的活动">
    <Tabs items={groups} />
  </Card>
}

export function HealthServicesPage() {
  const [tab, setTab] = useState('services')
  const [services, setServices] = useState<HealthService[]>([])
  const [recommendations, setRecommendations] = useState<ServiceRecommendationItem[]>([])
  const [recommendAiStatus, setRecommendAiStatus] = useState<string>('ok')
  const [activities, setActivities] = useState<HealthActivity[]>([])
  const [myActivities, setMyActivities] = useState<MyHealthActivity[]>([])
  const [bookings, setBookings] = useState<HealthServiceBooking[]>([])
  const [benefits, setBenefits] = useState<EmployeeHealthBenefit[]>([])
  const [loading, setLoading] = useState(true)
  const [bookingService, setBookingService] = useState<HealthService | null>(null)
  const [detailActivity, setDetailActivity] = useState<HealthActivity | null>(null)
  const [joinTarget, setJoinTarget] = useState<HealthActivity | null>(null)
  const [cancelTarget, setCancelTarget] = useState<HealthActivity | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const refresh = useCallback(async () => {
    const [svc, rec, act, my, bok, ben] = await Promise.all([
      getHealthServices(), getHealthServiceRecommendations(), getHealthActivities(), getMyHealthActivities(), getHealthServiceBookings(), getHealthBenefits(),
    ])
    setServices(svc); setRecommendations(rec.recommendations); setRecommendAiStatus(rec.ai_status); setActivities(act); setMyActivities(my); setBookings(bok); setBenefits(ben)
  }, [])
  useEffect(() => {
    void (async () => { try { await refresh() } catch { message.error('健康服务加载失败') } finally { setLoading(false) } })()
  }, [refresh])

  const run = async (action: () => Promise<unknown>, successText: string) => {
    try { await action(); await refresh(); message.success(successText) } catch (error: any) { message.error(error?.response?.data?.detail || '操作失败') }
  }
  const bookRecommended = (serviceId: string) => {
    const service = services.find((item) => item.id === serviceId)
    if (service) setBookingService(service)
  }
  const scrollToCatalog = () => document.getElementById('service-catalog')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  const openActivityDetail = async (activity: HealthActivity) => {
    try {
      setDetailActivity(await getHealthActivity(activity.id))
    } catch (error: any) { message.error(error?.response?.data?.detail || '活动详情加载失败') }
  }
  const confirmJoin = async () => {
    if (!joinTarget) return
    setSubmitting(true)
    try {
      await joinHealthActivity(joinTarget.id)
      await refresh()
      setDetailActivity(null)
      message.success('报名成功，欢迎参加活动')
    } catch (error: any) { message.error(error?.response?.data?.detail || '报名失败') } finally { setSubmitting(false); setJoinTarget(null) }
  }
  const confirmCancel = async () => {
    if (!cancelTarget) return
    setSubmitting(true)
    try {
      await cancelHealthActivity(cancelTarget.id)
      await refresh()
      setDetailActivity(null)
      message.success('已取消报名')
    } catch (error: any) { message.error(error?.response?.data?.detail || '取消失败') } finally { setSubmitting(false); setCancelTarget(null) }
  }

  return <section className="health-services-page">
    <div className="svc-heading">
      <p>企业健康资源与专业服务中心</p>
    </div>
    {loading ? <Card loading /> : <Tabs
      activeKey={tab}
      onChange={setTab}
      items={[
        {
          key: 'services',
          label: <span><span className="svc-tab-icon" style={{ color: '#16a34a' }}><HeartOutlined /></span>健康服务</span>,
          children: <div className="svc-tab-panel">
            <Recommendations items={recommendations} loading={loading} aiStatus={recommendAiStatus} onBook={bookRecommended} onBrowseAll={scrollToCatalog} />
            <div id="service-catalog"><ServiceCatalog services={services} onBook={setBookingService} /></div>
            <Row gutter={[16, 16]} align="stretch" style={{ display: 'flex', alignItems: 'stretch' }}>
              <Col xs={24} xl={12} style={{ display: 'flex' }}><div style={{ flex: 1, width: '100%' }}><MyBookings bookings={bookings} onCancel={(booking) => void run(() => cancelHealthServiceBooking(booking.id), '预约已取消')} /></div></Col>
              <Col xs={24} xl={12} style={{ display: 'flex' }}><div style={{ flex: 1, width: '100%' }}><MyBenefits benefits={benefits} /></div></Col>
            </Row>
          </div>,
        },
        {
          key: 'activities',
          label: <span><span className="svc-tab-icon" style={{ color: '#0891b2' }}><CalendarOutlined /></span>企业健康活动</span>,
          children: <EnterpriseActivities activities={activities} loading={loading} onDetail={(a) => void openActivityDetail(a)} onJoin={setJoinTarget} onCancel={setCancelTarget} />,
        },
        {
          key: 'my',
          label: <span><span className="svc-tab-icon" style={{ color: '#7c3aed' }}><UsergroupAddOutlined /></span>我的活动</span>,
          children: <MyActivities items={myActivities} loading={loading} onDetail={(a) => void openActivityDetail(a)} />,
        },
      ]}
    />}
    <BookingModal service={bookingService} onClose={() => setBookingService(null)} onBooked={() => { setBookingService(null); void refresh() }} />
    <ActivityDetailDrawer
      activity={detailActivity}
      onClose={() => setDetailActivity(null)}
      onJoin={() => detailActivity && setJoinTarget(detailActivity)}
      onCancel={() => detailActivity && setCancelTarget(detailActivity)}
    />
    <Modal
      open={Boolean(joinTarget)}
      title={joinTarget ? `确认报名：${joinTarget.name}` : ''}
      onCancel={() => !submitting && setJoinTarget(null)}
      onOk={() => void confirmJoin()}
      confirmLoading={submitting}
      okText="确认报名" cancelText="再想想" destroyOnClose
    >
      {joinTarget && <div className="svc-modal-info">
        <p>{activityTimeText(joinTarget)}</p>
        <p>{joinTarget.delivery_mode === 'online' ? '线上' : '线下'}{joinTarget.location ? ` · ${joinTarget.location}` : ''}</p>
        <p>当前报名：<b>{joinTarget.participants}</b> 人{joinTarget.remaining !== null && joinTarget.remaining !== undefined ? <>，剩余名额 <b>{joinTarget.remaining}</b></> : null}</p>
        <p style={{ color: '#dc2626', marginTop: 12 }}>报名成功后将记入你的活动参与记录，可在「我的活动」中取消报名。</p>
      </div>}
    </Modal>
    <Modal
      open={Boolean(cancelTarget)}
      title={cancelTarget ? `取消报名：${cancelTarget.name}` : ''}
      onCancel={() => !submitting && setCancelTarget(null)}
      onOk={() => void confirmCancel()}
      confirmLoading={submitting}
      okText="确认取消" cancelText="保留报名" destroyOnClose
    >
      <p style={{ margin: 0 }}>取消报名后仍会保留你的参与记录，需要时可重新报名（名额允许的情况下）。</p>
    </Modal>
  </section>
}
