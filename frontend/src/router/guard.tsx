import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore, type AuthRole } from '../store/authStore'
export function PrivateRoute({ allowedRoles }: { allowedRoles: AuthRole[] }) { const { isAuthenticated, user, initialized } = useAuthStore(); const location = useLocation(); if (!initialized) return null; if (!isAuthenticated || !user) return <Navigate to="/login" replace state={{ from: location.pathname }} />; return allowedRoles.includes(user.role) ? <Outlet /> : <Navigate to={user.role === 'employee' ? '/employee/dashboard' : '/admin/dashboard'} replace /> }
