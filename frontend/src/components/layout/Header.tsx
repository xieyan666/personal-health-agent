import { DownOutlined, SettingOutlined, UserOutlined } from '@ant-design/icons'
import { Avatar, Button, Dropdown, Space } from 'antd'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { getUserAvatar } from '../../api/userProfile'
import { useAuthStore } from '../../store/authStore'
import { NotificationCenter, NotificationSettings } from '../notification/NotificationCenter'

type PageTitle = { kicker: string; title: string; subtitle?: string }

// The Header is the single title source for every routed page. Keeping this
// map here prevents a global workspace title and a page title from being
// rendered twice at the top of the content area.
const PAGE_TITLES: Record<string, PageTitle> = {
  '/employee/dashboard': { kicker: 'EMPLOYEE HEALTH DASHBOARD', title: '健康工作台' },
  '/employee/assistant': { kicker: 'HEALTH ASSISTANT', title: 'AI 健康助手' },
  '/employee/profile': { kicker: 'HEALTH PROFILE', title: '健康档案' },
  '/employee/risk': { kicker: 'HEALTH RISK', title: '健康风险' },
  '/employee/reports': { kicker: 'HEALTH REPORT', title: '体检报告' },
  '/employee/plan': { kicker: 'HEALTH PLAN', title: '健康计划' },
  '/employee/services': { kicker: 'HEALTH SERVICES', title: '健康服务' },
  '/employee/mental': { kicker: 'MENTAL WELLNESS', title: '心理健康' },
  '/employee/personal': { kicker: 'PERSONAL CENTER', title: '个人中心' },
  '/employee/authorization': { kicker: 'DATA AUTHORIZATION', title: '数据授权' },
  '/admin/dashboard': { kicker: 'ENTERPRISE LIFE HEALTH', title: '企业健康管理中心' },
  '/admin/personal': { kicker: 'PERSONAL CENTER', title: '管理员个人中心' },
  '/admin/users': { kicker: 'RBAC USER MANAGEMENT', title: '用户管理' },
  '/admin/employees': { kicker: 'EMPLOYEE HEALTH ANALYTICS', title: '员工健康分析' },
  '/admin/risk': { kicker: 'HEALTH RISK OPERATIONS', title: '风险预警与处置' },
  '/admin/checkups': { kicker: 'HEALTH CHECKUP MANAGEMENT', title: '体检管理' },
  '/admin/activities': { kicker: 'HEALTH ACTIVITY OPERATIONS', title: '健康活动运营' },
  '/admin/knowledge': { kicker: 'KNOWLEDGE BASE MANAGEMENT', title: '知识库管理' },
  '/admin/agents': {
    kicker: 'AGENT MANAGEMENT',
    title: 'Agent 管理',
    subtitle: '统一管理企业 AI Agent，配置能力、资源与运行监控，保障智能服务稳定可靠地运行。',
  },
  '/admin/models': { kicker: 'MODEL MANAGEMENT', title: '模型管理' },
  '/admin/monitoring': { kicker: 'SYSTEM MONITORING', title: '系统监控' },
}

export function Header() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [avatarSource, setAvatarSource] = useState<string | null>(null)
  const role = user?.role ?? 'employee'
  const displayName = user?.displayName || user?.username || '小明'
  const page = PAGE_TITLES[location.pathname] ?? (location.pathname.startsWith('/admin')
    ? PAGE_TITLES['/admin/dashboard']
    : PAGE_TITLES['/employee/dashboard'])

  useEffect(() => {
    let source: string | null = null
    if (!user?.avatarUrl) {
      setAvatarSource(null)
      return
    }
    void getUserAvatar()
      .then((blob) => {
        source = URL.createObjectURL(blob)
        setAvatarSource(source)
      })
      .catch(() => setAvatarSource(null))
    return () => { if (source) URL.revokeObjectURL(source) }
  }, [user?.avatarUrl])

  const menuItems = [
    { key: 'personal', icon: <UserOutlined />, label: '个人中心', onClick: () => navigate(['admin', 'company_admin', 'system_admin'].includes(role) ? '/admin/personal' : '/employee/personal') },
    { type: 'divider' as const },
    { key: 'logout', label: '退出登录', onClick: logout },
  ]

  return (
    <header className="app-header">
      <div className="app-header-title">
        <div className="page-kicker">{page.kicker}</div>
        <h1>{page.title}</h1>
        {page.subtitle ? <p className="app-header-subtitle">{page.subtitle}</p> : null}
      </div>
      <Space size={18}>
        <NotificationCenter />
        <Button type="text" shape="circle" icon={<SettingOutlined />} onClick={() => setSettingsOpen(true)} />
        <Dropdown menu={{ items: menuItems }}>
          <button className="profile-button">
            <Avatar size={34} src={avatarSource ?? user?.avatarUrl ?? undefined} style={{ background: '#DCFCE7', color: '#15803D' }}>
              {displayName.slice(0, 1)}
            </Avatar>
            <span><strong>{displayName}</strong><small>{role === 'employee' ? '员工' : '企业管理员'}</small></span>
            <DownOutlined />
          </button>
        </Dropdown>
      </Space>
      <NotificationSettings open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </header>
  )
}
