import { Navigate, createBrowserRouter } from 'react-router-dom'
import { MainLayout } from '../components/layout/MainLayout'
import { Login } from '../pages/Login'
import { EmployeeHome } from '../pages/employee/EmployeeHome'
import { Profile } from '../pages/employee/Profile'
import { HealthAssistant } from '../pages/employee/assistant/HealthAssistant'
import { AdminHome } from '../pages/admin/AdminHome'
import { UserManagement } from '../pages/admin/UserManagement'
import { EmployeeHealthAnalysis } from '../pages/admin/EmployeeHealthAnalysis'
import { RiskOperations } from '../pages/admin/RiskOperations'
import { CheckupManagement } from '../pages/admin/CheckupManagement'
import { ActivityManagement } from '../pages/admin/ActivityManagement'
import { KnowledgeManagement } from '../pages/admin/KnowledgeManagement'
import { ModelManagement } from '../pages/admin/ModelManagement'
import { SystemMonitor } from '../pages/admin/SystemMonitor'
import { AgentManagement } from '../pages/admin/AgentManagement'
import { Risk } from '../pages/employee/Risk'
import { Reports } from '../pages/employee/Reports'
import { HealthPlanPage } from '../pages/employee/HealthPlan'
import { HealthServicesPage } from '../pages/employee/HealthServices'
import { MentalWellness } from '../pages/employee/MentalWellness'
import { DataAuthorization } from '../pages/employee/DataAuthorization'
import { PersonalCenter } from '../pages/employee/PersonalCenter'
import { AdminPersonalCenter } from '../pages/admin/AdminPersonalCenter'
import { PrivateRoute } from './guard'

export const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  { path: '/', element: <Navigate to="/login" replace /> },
  { element: <PrivateRoute allowedRoles={['employee']} />, children: [{ element: <MainLayout />, children: [
    { path: '/employee', element: <Navigate to="/employee/dashboard" replace /> },
    { path: '/employee/dashboard', element: <EmployeeHome /> },
    { path: '/employee/assistant', element: <HealthAssistant /> },
    { path: '/employee/profile', element: <Profile /> },
    { path: '/employee/risk', element: <Risk /> },
    { path: '/employee/reports', element: <Reports /> },
    { path: '/employee/plan', element: <HealthPlanPage /> },
    { path: '/employee/services', element: <HealthServicesPage /> },
    { path: '/employee/mental', element: <MentalWellness /> },
    { path: '/employee/personal', element: <PersonalCenter /> },
    { path: '/employee/authorization', element: <DataAuthorization /> },
    { path: '/employee/*', element: <EmployeeHome /> },
  ] }] },
  { element: <PrivateRoute allowedRoles={['admin', 'company_admin', 'system_admin']} />, children: [{ element: <MainLayout />, children: [
    { path: '/admin', element: <Navigate to="/admin/dashboard" replace /> },
    { path: '/admin/dashboard', element: <AdminHome /> },
    { path: '/admin/personal', element: <AdminPersonalCenter /> },
    { path: '/admin/users', element: <UserManagement /> },
    { path: '/admin/employees', element: <EmployeeHealthAnalysis /> },
    { path: '/admin/risk', element: <RiskOperations /> },
    { path: '/admin/checkups', element: <CheckupManagement /> },
    { path: '/admin/activities', element: <ActivityManagement /> },
    { path: '/admin/knowledge', element: <KnowledgeManagement /> },
    { path: '/admin/agents', element: <AgentManagement /> },
    { path: '/admin/models', element: <ModelManagement /> },
    { path: '/admin/monitoring', element: <SystemMonitor /> },
    { path: '/admin/*', element: <AdminHome /> },
  ] }] },
])
