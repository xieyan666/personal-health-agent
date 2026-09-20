import { AppstoreOutlined, CalendarOutlined, CheckCircleOutlined, EditOutlined, EyeOutlined, FileAddOutlined, GlobalOutlined, HeartOutlined, RocketOutlined, StopOutlined, TeamOutlined, UserAddOutlined, UserDeleteOutlined } from '@ant-design/icons'
import { Button, Card, Col, DatePicker, Drawer, Empty, Form, Input, InputNumber, Modal, Row, Select, Space, Table, Tag, TimePicker, message } from 'antd'
import dayjs from 'dayjs'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ACTIVITY_STATUS_LABELS, ACTIVITY_TYPE_LABELS,
  cancelAdminActivity, createAdminActivity, finishAdminActivity, getAdminActivities, getAdminActivity, getAdminActivityDynamics, getAdminActivityParticipants, getAdminActivitySummary, publishAdminActivity, updateAdminActivity,
  type ActivityDynamic, type ActivityParticipant, type ActivityPayload, type AdminActivity, type AdminActivitySummary,
} from '../../api/activities'
import './activity-management.css'

const TYPE_OPTIONS = Object.entries(ACTIVITY_TYPE_LABELS).map(([value, label]) => ({ value, label }))
const SCOPE_OPTIONS = [{ value: 'all', label: '全体员工' }, { value: 'department', label: '指定部门' }]
const DELIVERY_OPTIONS = [{ value: 'offline', label: '线下' }, { value: 'online', label: '线上' }]
const TYPE_ICON_COLORS: Record<string, string> = {
  lecture: '#0891b2', exercise: '#16a34a', nutrition: '#d97706', education: '#7c3aed', exam_promo: '#dc2626', other: '#64748b',
}

function toPayload(values: any): ActivityPayload {
  return {
    name: values.name,
    activity_type: values.activity_type,
    description: values.description ?? null,
    start_date: values.start_date ? values.start_date.format('YYYY-MM-DD') : null,
    end_date: values.end_date ? values.end_date.format('YYYY-MM-DD') : null,
    start_time: values.start_time ? values.start_time.format('HH:mm') : null,
    end_time: values.end_time ? values.end_time.format('HH:mm') : null,
    registration_deadline: values.registration_deadline ? values.registration_deadline.toISOString() : null,
    delivery_mode: values.delivery_mode,
    location: values.location ?? null,
    scope: values.scope,
    target_department: values.scope === 'department' ? (values.target_department ?? null) : null,
    organizer: values.organizer ?? null,
    contact_person: values.contact_person ?? null,
    capacity: values.capacity ?? null,
  }
}

function initialValues(activity: AdminActivity | null) {
  if (!activity) return {
    activity_type: 'lecture', delivery_mode: 'offline', scope: 'all', capacity: undefined,
  }
  return {
    name: activity.name,
    activity_type: activity.activity_type,
    description: activity.description ?? undefined,
    start_date: activity.start_date ? dayjs(activity.start_date) : undefined,
    end_date: activity.end_date ? dayjs(activity.end_date) : undefined,
    start_time: activity.start_time ? dayjs(activity.start_time, 'HH:mm') : undefined,
    end_time: activity.end_time ? dayjs(activity.end_time, 'HH:mm') : undefined,
    registration_deadline: activity.registration_deadline ? dayjs(activity.registration_deadline) : undefined,
    delivery_mode: activity.delivery_mode,
    location: activity.location ?? undefined,
    scope: activity.scope,
    target_department: activity.target_department ?? undefined,
    organizer: activity.organizer ?? undefined,
    contact_person: activity.contact_person ?? undefined,
    capacity: activity.capacity ?? undefined,
  }
}

const PARTICIPANT_STATUS_LABELS: Record<string, { label: string; color: string }> = {
  joined: { label: '已报名', color: 'green' },
  cancelled: { label: '已取消', color: 'default' },
}

function activityDateRange(activity: AdminActivity) {
  if (!activity.start_date) return '待定'
  const start = dayjs(activity.start_date).format('YYYY/MM/DD')
  const end = activity.end_date && activity.end_date !== activity.start_date ? ` - ${dayjs(activity.end_date).format('MM/DD')}` : ''
  return `${start}${end}`
}

function ActivityCard({ activity, onDetail }: { activity: AdminActivity; onDetail: (activity: AdminActivity) => void }) {
  const statusMeta = ACTIVITY_STATUS_LABELS[activity.display_status] ?? { label: activity.display_status, color: 'default' }
  const color = TYPE_ICON_COLORS[activity.activity_type] ?? '#64748b'
  const progress = activity.capacity ? Math.min(Math.round(activity.participants / activity.capacity * 100), 100) : 0
  return <div className="a-op-card">
    <div className="a-op-card-head">
      <div className="a-op-card-icon" style={{ background: `${color}1a`, color }}><AppstoreOutlined /></div>
      <div className="a-op-card-title">
        <h4>{activity.name}</h4>
        <span>{ACTIVITY_TYPE_LABELS[activity.activity_type] ?? activity.activity_type} · {activity.delivery_mode === 'online' ? '线上' : '线下'}</span>
      </div>
      <Tag color={statusMeta.color}>{statusMeta.label}</Tag>
    </div>
    <div className="a-op-card-meta">
      <span><CalendarOutlined /> {activityDateRange(activity)}</span>
      <span><GlobalOutlined /> {activity.location ?? (activity.delivery_mode === 'online' ? '线上活动' : '线下活动')}</span>
      <span><TeamOutlined /> {activity.scope === 'department' ? `指定部门：${activity.target_department}` : '全体员工'}</span>
    </div>
    <div className="a-op-card-progress">
      <div className="a-op-card-progress-head"><span>报名 {activity.participants} / {activity.capacity ?? '不限'}</span><b>{activity.capacity ? `${progress}%` : '—'}</b></div>
      {activity.capacity ? <div className="a-op-progress-bar"><div className="a-op-progress-fill" style={{ width: `${progress}%`, background: progress >= 100 ? '#ef4444' : '#16a34a' }} /></div> : null}
      {activity.remaining !== null && activity.remaining !== undefined ? <small>{activity.remaining === 0 ? '名额已满' : `剩余 ${activity.remaining} 个名额`}</small> : null}
    </div>
    <div className="a-op-card-foot">
      <Button size="small" type="primary" ghost icon={<EyeOutlined />} onClick={() => onDetail(activity)}>运营详情</Button>
      <span className="a-op-card-time">创建于 {activity.created_at ? dayjs(activity.created_at).format('MM-DD') : '—'}</span>
    </div>
  </div>
}

function ActivityTimeline({ items, onDetail }: { items: AdminActivity[]; onDetail: (activity: AdminActivity) => void }) {
  const groups = useMemo(() => {
    const map = new Map<string, AdminActivity[]>()
    for (const item of items) {
      const key = item.start_date ? dayjs(item.start_date).format('YYYY年M月') : '时间待定'
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(item)
    }
    return Array.from(map.entries()).sort((a, b) => {
      const na = a[0] === '时间待定' ? '0000' : a[0]
      const nb = b[0] === '时间待定' ? '0000' : b[0]
      return na.localeCompare(nb)
    })
  }, [items])
  if (!items.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无活动" />
  return <div className="a-op-timeline">
    {groups.map(([month, list]) => (
      <div className="a-op-timeline-month" key={month}>
        <div className="a-op-timeline-month-title">{month}<span>{list.length} 场</span></div>
        {list.map((activity) => {
          const statusMeta = ACTIVITY_STATUS_LABELS[activity.display_status] ?? { label: activity.display_status, color: 'default' }
          return <button type="button" className="a-op-timeline-item" key={activity.id} onClick={() => onDetail(activity)}>
            <span className="a-op-timeline-date">{activity.start_date ? dayjs(activity.start_date).format('MM/DD') : '待定'}</span>
            <span className="a-op-timeline-name">{activity.name}</span>
            <Tag color={statusMeta.color} style={{ margin: 0 }}>{statusMeta.label}</Tag>
          </button>
        })}
      </div>
    ))}
  </div>
}

function DynamicsFeed({ dynamics, loading }: { dynamics: ActivityDynamic[]; loading: boolean }) {
  return <Card className="a-card a-side-card" title="报名动态" extra={<span className="a-side-note">最近报名 / 取消</span>}>
    {loading ? <div className="a-dyn-loading">加载中...</div> : dynamics.length ? <div className="a-dyn-list">
      {dynamics.map((item) => (
        <div className="a-dyn-item" key={item.id}>
          <div className={`a-dyn-icon ${item.action === 'joined' ? 'joined' : 'cancelled'}`}>{item.action === 'joined' ? <UserAddOutlined /> : <UserDeleteOutlined />}</div>
          <div className="a-dyn-body">
            <p><b>{item.department ?? '未知部门'}</b> {item.action === 'joined' ? '+1人报名' : '+1人取消'} <span className="a-dyn-activity">{item.activity_name}</span></p>
            <small>{item.occurred_at ? dayjs(item.occurred_at).format('MM-DD HH:mm') : ''} · {item.employee_name ?? ''}</small>
          </div>
        </div>
      ))}
    </div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无报名动态" />}
  </Card>
}

export function ActivityManagement() {
  const [summary, setSummary] = useState<AdminActivitySummary | null>(null)
  const [items, setItems] = useState<AdminActivity[]>([])
  const [dynamics, setDynamics] = useState<ActivityDynamic[]>([])
  const [loading, setLoading] = useState(true)
  const [dynamicsLoading, setDynamicsLoading] = useState(true)
  const [form] = Form.useForm()
  const [editorOpen, setEditorOpen] = useState(false)
  const [editing, setEditing] = useState<AdminActivity | null>(null)
  const [saving, setSaving] = useState(false)
  const [detail, setDetail] = useState<AdminActivity | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [participants, setParticipants] = useState<ActivityParticipant[]>([])
  const [participantsLoading, setParticipantsLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [actionTarget, setActionTarget] = useState<AdminActivity | null>(null)
  const [actionKind, setActionKind] = useState<'publish' | 'cancel' | 'finish'>('publish')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [summaryResult, itemsResult] = await Promise.all([getAdminActivitySummary(), getAdminActivities()])
      setSummary(summaryResult)
      setItems(itemsResult)
    } catch { message.error('健康活动数据加载失败') } finally { setLoading(false) }
  }, [])
  const loadDynamics = useCallback(async () => {
    setDynamicsLoading(true)
    try { setDynamics(await getAdminActivityDynamics(12)) } catch { /* 动态加载失败不阻塞 */ } finally { setDynamicsLoading(false) }
  }, [])
  useEffect(() => { void load(); void loadDynamics() }, [load, loadDynamics])

  const openDetail = async (activity: AdminActivity) => {
    setDetail(activity)
    setDetailOpen(true)
    setParticipantsLoading(true)
    try { setParticipants(await getAdminActivityParticipants(activity.id)) }
    catch { setParticipants([]); message.error('报名人员加载失败') }
    finally { setParticipantsLoading(false) }
  }

  const openEditor = (activity: AdminActivity | null) => {
    setEditing(activity)
    form.resetFields()
    if (activity) form.setFieldsValue(initialValues(activity))
    setEditorOpen(true)
  }

  const saveActivity = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      const payload = toPayload(values)
      if (editing) {
        await updateAdminActivity(editing.id, payload)
        message.success('活动已更新')
      } else {
        await createAdminActivity(payload)
        message.success('活动已创建为草稿，发布后员工端可见')
      }
      setEditorOpen(false)
      await load()
    } catch (error: any) {
      if (error?.errorFields) return
      message.error(error?.response?.data?.detail || '保存失败')
    } finally { setSaving(false) }
  }

  const confirmAction = async () => {
    if (!actionTarget) return
    setActionLoading(true)
    try {
      if (actionKind === 'publish') {
        await publishAdminActivity(actionTarget.id)
        message.success('活动已发布，员工端可见并收到通知')
      } else if (actionKind === 'cancel') {
        await cancelAdminActivity(actionTarget.id)
        message.success('活动已取消')
      } else {
        await finishAdminActivity(actionTarget.id)
        message.success('活动已结束')
      }
      setActionTarget(null)
      await Promise.all([load(), loadDynamics()])
      if (detail?.id === actionTarget.id) {
        try {
          const updated = await getAdminActivity(actionTarget.id)
          setDetail(updated)
          setParticipants(await getAdminActivityParticipants(actionTarget.id))
        } catch { /* 详情刷新失败不影响主流程 */ }
      }
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '操作失败')
    } finally { setActionLoading(false) }
  }

  const kpis = [
    { icon: <CalendarOutlined />, label: '本月活动数', value: summary?.month_activity_count ?? 0, note: '本月创建的活动', color: '#16A34A' },
    { icon: <RocketOutlined />, label: '开放报名', value: summary?.open_registration_count ?? 0, note: '当前可报名的活动', color: '#0EA5B7' },
    { icon: <TeamOutlined />, label: '累计报名', value: summary?.total_participants ?? 0, note: '全部活动累计人次', color: '#F59E0B' },
    { icon: <HeartOutlined />, label: '平均参与率', value: `${summary?.avg_participation_rate ?? 0}%`, note: '报名人数 / 名额', color: '#8B5CF6' },
  ]

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const item of items) counts[item.display_status] = (counts[item.display_status] ?? 0) + 1
    return counts
  }, [items])

  const actionTitle = actionKind === 'publish' ? '发布活动' : actionKind === 'cancel' ? '取消活动' : '结束活动'
  const actionText = actionKind === 'publish'
    ? `确认发布「${actionTarget?.name}」？发布后员工端可见，符合范围的员工将收到通知。`
    : actionKind === 'cancel'
      ? `确认取消「${actionTarget?.name}」？取消后员工将无法报名。`
      : `确认结束「${actionTarget?.name}」？结束后将停止报名。`

  return <section className="a-page activity-management-page">
    <div className="a-page-head">
      <div>
        <p className="a-subtitle">活动运营中心：创建、发布、跟踪报名与参与情况。</p>
      </div>
      <Button type="primary" icon={<FileAddOutlined />} onClick={() => openEditor(null)}>新建健康活动</Button>
    </div>

    <Row gutter={[16, 16]} className="a-kpi-row">
      {kpis.map((item) => (
        <Col xs={12} xl={6} key={item.label}>
          <Card className="a-kpi" style={{ borderLeft: `3px solid ${item.color}` }}>
            <div className="a-kpi-icon" style={{ color: item.color, background: `${item.color}14` }}>{item.icon}</div>
            <div className="a-kpi-body"><small>{item.label}</small><b>{item.value}</b><p>{item.note}</p></div>
          </Card>
        </Col>
      ))}
    </Row>

    <Row gutter={[16, 16]} align="stretch">
      <Col xs={24} xl={16}>
        <Card className="a-card" title="活动日历 / 时间轴" extra={<span className="a-side-note">按月份分组 · 点击查看运营详情</span>}>
          {loading ? <div className="a-dyn-loading">加载中...</div> : <ActivityTimeline items={items} onDetail={(a) => void openDetail(a)} />}
        </Card>
        <Card className="a-card a-op-cards-card" title={`活动卡片（${items.length}）`} extra={<span className="a-side-note">报名进度一目了然</span>}>
          {loading ? <div className="a-dyn-loading">加载中...</div> : items.length
            ? <Row gutter={[16, 16]}>
              {items.map((activity) => (
                <Col xs={24} md={12} xl={8} key={activity.id}>
                  <ActivityCard activity={activity} onDetail={(a) => void openDetail(a)} />
                </Col>
              ))}
            </Row>
            : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无活动，点击右上角「新建健康活动」开始" />}
        </Card>
      </Col>
      <Col xs={24} xl={8}>
        <DynamicsFeed dynamics={dynamics} loading={dynamicsLoading} />
        <Card className="a-card a-side-card" title="状态概览">
          <div className="a-status-overview">
            {(['draft', 'registration_open', 'registration_closed', 'ongoing', 'finished', 'cancelled'] as const).map((status) => {
              const meta = ACTIVITY_STATUS_LABELS[status] ?? { label: status, color: 'default' }
              return <div className="a-status-row" key={status}>
                <Tag color={meta.color}>{meta.label}</Tag>
                <b>{statusCounts[status] ?? 0}</b>
                <span>场</span>
              </div>
            })}
          </div>
        </Card>
      </Col>
    </Row>

    <Drawer title={editing ? '编辑健康活动' : '新建健康活动'} width={520} open={editorOpen} onClose={() => setEditorOpen(false)} extra={<Button type="primary" loading={saving} onClick={() => void saveActivity()}>保存</Button>} destroyOnClose>
      <Form form={form} layout="vertical" initialValues={initialValues(null)}>
        <Form.Item name="name" label="活动名称" rules={[{ required: true, message: '请输入活动名称' }]}><Input placeholder="例如：秋季健康讲座" maxLength={120} /></Form.Item>
        <Form.Item name="activity_type" label="活动类型" rules={[{ required: true }]}><Select options={TYPE_OPTIONS} /></Form.Item>
        <Form.Item name="description" label="活动简介"><Input.TextArea rows={3} placeholder="活动内容、亮点等" maxLength={2000} /></Form.Item>
        <Row gutter={12}>
          <Col span={12}><Form.Item name="start_date" label="活动日期"><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={12}><Form.Item name="end_date" label="结束日期"><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
        </Row>
        <Row gutter={12}>
          <Col span={12}><Form.Item name="start_time" label="开始时间"><TimePicker format="HH:mm" style={{ width: '100%' }} /></Form.Item></Col>
          <Col span={12}><Form.Item name="end_time" label="结束时间"><TimePicker format="HH:mm" style={{ width: '100%' }} /></Form.Item></Col>
        </Row>
        <Form.Item name="registration_deadline" label="报名截止时间" extra="不填时默认为活动开始时间">
          <DatePicker showTime format="YYYY-MM-DD HH:mm" style={{ width: '100%' }} />
        </Form.Item>
        <Row gutter={12}>
          <Col span={12}>
            <Form.Item name="delivery_mode" label="活动形式" rules={[{ required: true }]}><Select options={DELIVERY_OPTIONS} /></Form.Item>
          </Col>
          <Col span={12}><Form.Item name="capacity" label="人数上限"><InputNumber min={1} max={100000} style={{ width: '100%' }} placeholder="不填则不限" /></Form.Item></Col>
        </Row>
        <Form.Item name="location" label="活动地点/线上说明">
          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.delivery_mode !== cur.delivery_mode}>
            {({ getFieldValue }) => (
              <Input placeholder={getFieldValue('delivery_mode') === 'online' ? '例如：腾讯会议，会议号 123-456-789' : '例如：3号楼多功能厅'} maxLength={200} />
            )}
          </Form.Item>
        </Form.Item>
        <Form.Item name="scope" label="参与范围" rules={[{ required: true }]}><Select options={SCOPE_OPTIONS} /></Form.Item>
        <Form.Item noStyle shouldUpdate={(prev, cur) => prev.scope !== cur.scope}>
          {({ getFieldValue }) => getFieldValue('scope') === 'department'
            ? <Form.Item name="target_department" label="指定部门" rules={[{ required: true, message: '请选择部门' }]}><Input placeholder="例如：研发部" maxLength={120} /></Form.Item>
            : null}
        </Form.Item>
        <Row gutter={12}>
          <Col span={12}><Form.Item name="organizer" label="主办方"><Input placeholder="例如：行政部" maxLength={80} /></Form.Item></Col>
          <Col span={12}><Form.Item name="contact_person" label="联系人"><Input placeholder="姓名 / 电话" maxLength={80} /></Form.Item></Col>
        </Row>
      </Form>
    </Drawer>

    <Drawer title="活动运营详情" width={560} open={detailOpen} onClose={() => setDetailOpen(false)}>
      {detail ? <div className="a-detail">
        <div className="a-detail-head">
          <div className="a-detail-icon"><AppstoreOutlined /></div>
          <div>
            <h3>{detail.name}</h3>
            <Space size={4} wrap>
              <Tag color="green">{ACTIVITY_TYPE_LABELS[detail.activity_type] ?? detail.activity_type}</Tag>
              <Tag color={ACTIVITY_STATUS_LABELS[detail.display_status]?.color}>{ACTIVITY_STATUS_LABELS[detail.display_status]?.label}</Tag>
            </Space>
          </div>
        </div>
        <div className="a-detail-actions">
          {(detail.status === 'draft' || detail.status === 'registration_closed') && <Button size="small" icon={<EditOutlined />} onClick={() => { openEditor(detail); setDetailOpen(false) }}>编辑</Button>}
          {detail.status === 'draft' && <Button size="small" type="primary" icon={<RocketOutlined />} onClick={() => { setActionTarget(detail); setActionKind('publish') }}>发布</Button>}
          {detail.status === 'registration_open' && <Button size="small" icon={<CheckCircleOutlined />} onClick={() => { setActionTarget(detail); setActionKind('finish') }}>结束活动</Button>}
          {!['cancelled', 'finished'].includes(detail.status) && <Button size="small" danger icon={<StopOutlined />} onClick={() => { setActionTarget(detail); setActionKind('cancel') }}>取消活动</Button>}
        </div>
        <div className="a-detail-grid">
          <span>活动时间</span><b>{detail.start_date ? `${detail.start_date}${detail.end_date !== detail.start_date ? ` ~ ${detail.end_date}` : ''} ${detail.start_time ?? ''}${detail.end_time ? `-${detail.end_time}` : ''}` : '—'}</b>
          <span>活动形式</span><b>{detail.delivery_mode === 'online' ? '线上' : '线下'}{detail.location ? ` · ${detail.location}` : ''}</b>
          <span>报名截止</span><b>{detail.registration_deadline ? dayjs(detail.registration_deadline).format('YYYY-MM-DD HH:mm') : '—'}</b>
          <span>参与范围</span><b>{detail.scope === 'department' ? `指定部门：${detail.target_department}` : '全体员工'}</b>
          <span>主办方</span><b>{detail.organizer ?? '—'}{detail.contact_person ? ` · ${detail.contact_person}` : ''}</b>
          <span>报名情况</span><b className="a-detail-strong">{detail.participants} / {detail.capacity ?? '不限'} 人{detail.remaining !== null && detail.remaining !== undefined ? `（剩余 ${detail.remaining} 名额）` : ''}</b>
        </div>
        {detail.description ? <p className="a-detail-desc">{detail.description}</p> : null}

        <div className="a-section-title">报名员工列表（{participants.length}）</div>
        <Table
          rowKey="id" size="small" pagination={{ pageSize: 8, showTotal: (total) => `共 ${total} 人` }} loading={participantsLoading}
          dataSource={participants}
          columns={[
            { title: '员工编号', dataIndex: 'employee_no', key: 'employee_no', width: 120, render: (value) => value ?? '—' },
            { title: '姓名', dataIndex: 'employee_name', key: 'employee_name', width: 100, render: (value) => <b>{value ?? '—'}</b> },
            { title: '部门', dataIndex: 'department', key: 'department', render: (value) => value ?? '—' },
            { title: '报名时间', dataIndex: 'joined_at', key: 'joined_at', width: 140, render: (value) => <span className="a-muted">{value ? dayjs(value).format('MM-DD HH:mm') : '—'}</span> },
            { title: '状态', dataIndex: 'status', key: 'status', width: 84, render: (value) => { const meta = PARTICIPANT_STATUS_LABELS[value] ?? { label: value, color: 'default' }; return <Tag color={meta.color} style={{ margin: 0 }}>{meta.label}</Tag> } },
          ]}
        />
        {!participantsLoading && !participants.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无报名记录" /> : null}
      </div> : <div className="a-detail-loading">加载中...</div>}
    </Drawer>

    <Modal title={actionTitle} open={Boolean(actionTarget)} onCancel={() => setActionTarget(null)} onOk={() => void confirmAction()} confirmLoading={actionLoading} okText="确认" cancelText="再想想">
      <p style={{ margin: 0 }}>{actionText}</p>
    </Modal>
  </section>
}
