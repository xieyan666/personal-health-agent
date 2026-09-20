import { AppstoreOutlined, DashboardOutlined, FileTextOutlined, HeartOutlined, SafetyOutlined, SettingOutlined, SmileOutlined, TeamOutlined, ExperimentOutlined, RobotOutlined, DatabaseOutlined, FundProjectionScreenOutlined, LineChartOutlined, UserOutlined, MonitorOutlined } from '@ant-design/icons'
import { Menu } from 'antd'
import type { MenuProps } from 'antd'
import type { ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore, type AuthRole } from '../../store/authStore'
import { HealthAssistantMascot } from '../common/HealthAssistantMascot'

const employeeItems = [
  ['dashboard', '首页 Dashboard', DashboardOutlined], ['assistant', 'AI 健康助手', RobotOutlined], ['profile', '健康档案', HeartOutlined], ['risk', '健康风险', SafetyOutlined], ['reports', '体检报告', FileTextOutlined], ['plan', '健康计划', ExperimentOutlined], ['services', '健康服务', AppstoreOutlined], ['mental', '心理健康', SmileOutlined], ['authorization', '数据授权', SettingOutlined],
]
const adminItems: MenuProps['items'] = [
  { type: 'group', label: '工作台', children: [
    { key: '/admin/dashboard', label: '企业健康驾驶舱', icon: <FundProjectionScreenOutlined /> },
  ] },
  { type: 'group', label: '人员与健康', children: [
    { key: '/admin/users', label: '用户管理', icon: <UserOutlined /> },
    { key: '/admin/employees', label: '员工健康分析', icon: <LineChartOutlined /> },
    { key: '/admin/risk', label: '风险预警与处置', icon: <SafetyOutlined /> },
    { key: '/admin/checkups', label: '体检管理', icon: <ExperimentOutlined /> },
    { key: '/admin/activities', label: '健康活动运营', icon: <AppstoreOutlined /> },
  ] },
  { type: 'group', label: 'AI能力', children: [
    { key: '/admin/knowledge', label: '知识库管理', icon: <DatabaseOutlined /> },
    { key: '/admin/agents', label: 'Agent 管理', icon: <RobotOutlined /> },
    { key: '/admin/models', label: '模型管理', icon: <SettingOutlined /> },
  ] },
  { type: 'group', label: '系统', children: [
    { key: '/admin/monitoring', label: '系统监控', icon: <MonitorOutlined /> },
  ] },
]

export function Sidebar({ role }: { role: AuthRole }) {
  const navigate = useNavigate(); const location = useLocation(); const isAdmin = role === 'admin' || role === 'company_admin' || role === 'system_admin'
  const items: MenuProps['items'] = isAdmin ? adminItems : employeeItems.map(([key, label, Icon]) => ({ key: `/employee/${key}`, label: label as string, icon: <Icon /> as ReactNode }))
  return <aside className="sidebar">
    <div className="brand"><div className="brand-mark">🌿</div><div><div className="brand-title">Health AI</div><div className="brand-subtitle">生命健康智能平台</div></div></div>
    {!isAdmin && <div className="menu-caption">工作台</div>}
    <Menu mode="inline" selectedKeys={[location.pathname]} items={items} onClick={({ key }) => navigate(key)} />
    <div className="sidebar-bottom">
      {!isAdmin && <HealthAssistantMascot />}
      <div className="sidebar-footer"><div className="status-dot" />系统运行正常</div>
    </div>
  </aside>
}
