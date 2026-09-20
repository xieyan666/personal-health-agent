import { AppstoreOutlined, BellOutlined, CheckOutlined, ExperimentOutlined, FileTextOutlined, HeartOutlined, LockOutlined, SafetyOutlined, SmileOutlined } from '@ant-design/icons'
import { Badge, Button, Drawer, Empty, Popover, Spin, Switch, message } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getNotificationPreferences, getNotificationUnreadCount, getNotifications, markAllNotificationsRead, markNotificationRead, updateNotificationPreferences,
  type NotificationPreferences, type NotificationType, type UserNotification,
} from '../../api/notifications'
import './notification-center.css'

const TYPE_ICON: Record<NotificationType, React.ReactNode> = {
  system: <BellOutlined />,
  health_report: <FileTextOutlined />,
  health_risk: <SafetyOutlined />,
  health_plan: <ExperimentOutlined />,
  mental_health: <SmileOutlined />,
  health_service: <AppstoreOutlined />,
  authorization: <LockOutlined />,
  agent_error: <BellOutlined />,
}
const TYPE_COLOR: Record<NotificationType, string> = {
  system: '#64748b',
  health_report: '#0891b2',
  health_risk: '#d97706',
  health_plan: '#16a34a',
  mental_health: '#7c3aed',
  health_service: '#dc2626',
  authorization: '#475569',
  agent_error: '#ea580c',
}

function formatTime(value: string): string {
  const date = new Date(value)
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const time = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  if (date.getTime() >= startOfToday) return `今天 ${time}`
  if (date.getTime() >= startOfToday - 86400000) return `昨天 ${time}`
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }).replace('/', '-') + ` ${time}`
}

function NotificationList({ onOpened, unread, onUnreadChange }: { onOpened: () => void; unread: number; onUnreadChange: (count: number | ((prev: number) => number)) => void }) {
  const navigate = useNavigate()
  const [items, setItems] = useState<UserNotification[] | null>(null)

  const refresh = useCallback(async () => {
    const [rows, { unread_count }] = await Promise.all([getNotifications(6), getNotificationUnreadCount()])
    setItems(rows)
    onUnreadChange(unread_count)
  }, [onUnreadChange])
  useEffect(() => { void refresh() }, [refresh])

  const openItem = async (item: UserNotification) => {
    if (!item.is_read) {
      // Optimistic update: hide the dot immediately, then sync with the server.
      setItems((prev) => prev?.map((row) => (row.id === item.id ? { ...row, is_read: true } : row)) ?? prev)
      onUnreadChange((prev) => Math.max(0, prev - 1))
      try { await markNotificationRead(item.id) } catch { void refresh() }
    }
    onOpened()
    if (item.target_path) navigate(item.target_path)
  }
  const readAll = async () => {
    setItems((prev) => prev?.map((row) => ({ ...row, is_read: true })) ?? prev)
    onUnreadChange(0)
    try {
      await markAllNotificationsRead()
      message.success('已全部标为已读')
    } catch {
      message.error('操作失败，请重试')
      void refresh()
    }
  }

  return <div className="notif-panel">
    <div className="notif-panel-head"><b>消息通知</b><Button type="link" size="small" icon={<CheckOutlined />} onClick={() => void readAll()}>全部标为已读</Button></div>
    {items === null ? <div className="notif-loading"><Spin size="small" />加载中...</div>
      : items.length === 0
        ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={<><div>暂无新消息</div><div className="notif-empty-sub">你的健康报告、计划、预约和系统提醒会显示在这里。</div></>} />
        : <div className="notif-list">
          {items.map((item) => (
            <button type="button" className={`notif-item ${item.is_read ? 'read' : 'unread'}`} key={item.id} onClick={() => void openItem(item)}>
              <span className="notif-item-icon" style={{ background: `${TYPE_COLOR[item.type] ?? '#64748b'}1a`, color: TYPE_COLOR[item.type] ?? '#64748b' }}>{TYPE_ICON[item.type] ?? <BellOutlined />}</span>
              <span className="notif-item-body">
                <span className="notif-item-title">{item.title}{!item.is_read && <em className="notif-dot" aria-label="未读" />}</span>
                <span className="notif-item-content">{item.content}</span>
                <span className="notif-item-time">{formatTime(item.created_at)}</span>
              </span>
            </button>
          ))}
        </div>}
  </div>
}

export function NotificationCenter() {
  const [open, setOpen] = useState(false)
  const [unread, setUnread] = useState(0)
  const handleUnreadChange = useCallback((updater: number | ((prev: number) => number)) => {
    setUnread((prev) => (typeof updater === 'function' ? (updater as (value: number) => number)(prev) : updater))
  }, [])
  const refreshUnread = useCallback(() => { void getNotificationUnreadCount().then(({ unread_count }) => setUnread(unread_count)).catch(() => undefined) }, [])
  useEffect(() => { refreshUnread(); const timer = window.setInterval(refreshUnread, 60000); return () => window.clearInterval(timer) }, [refreshUnread])

  return <Popover
    trigger="click"
    placement="bottomRight"
    open={open}
    onOpenChange={(next) => { setOpen(next); if (next) refreshUnread() }}
    overlayClassName="notif-popover"
    content={<NotificationList onOpened={() => setOpen(false)} unread={unread} onUnreadChange={handleUnreadChange} />}
  >
    <Badge count={unread} size="small" color="#ef4444" offset={[-2, 2]}><Button type="text" shape="circle" icon={<BellOutlined />} /></Badge>
  </Popover>
}

const PREFERENCE_ITEMS: { key: keyof NotificationPreferences; label: string }[] = [
  { key: 'system', label: '系统通知' },
  { key: 'health_report', label: '体检报告通知' },
  { key: 'health_risk', label: '健康风险通知' },
  { key: 'health_plan', label: '健康计划通知' },
  { key: 'mental_health', label: '心理健康通知' },
  { key: 'health_service', label: '健康服务通知' },
  { key: 'authorization', label: '数据授权安全提醒' },
  { key: 'agent_error', label: 'Agent异常通知' },
]

export function NotificationSettings({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [preferences, setPreferences] = useState<NotificationPreferences | null>(null)
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    if (open) void getNotificationPreferences().then(setPreferences).catch(() => undefined)
  }, [open])
  const toggle = async (key: keyof NotificationPreferences, value: boolean) => {
    const next = preferences ? { ...preferences, [key]: value } : null
    setPreferences(next)
    setSaving(true)
    try {
      const saved = await updateNotificationPreferences({ [key]: value })
      setPreferences(saved)
    } catch { message.error('设置保存失败'); if (preferences) setPreferences({ ...preferences, [key]: !value }) } finally { setSaving(false) }
  }
  return <Drawer title="通知设置" width={400} open={open} onClose={onClose}>
    <p className="notif-settings-desc">选择你希望接收的消息类型。关闭某类通知只会停止该类消息提醒，不影响对应功能的使用。</p>
    <div className="notif-settings">
      {PREFERENCE_ITEMS.map((item) => (
        <div className="notif-setting-row" key={item.key}>
          <span>{item.label}</span>
          <Switch size="small" checked={preferences?.[item.key] ?? true} disabled={saving} onChange={(checked) => void toggle(item.key, checked)} />
        </div>
      ))}
    </div>
  </Drawer>
}
