import { RouterProvider } from 'react-router-dom'
import { router } from './router'
import { useEffect } from 'react'
import { useAuthStore } from './store/authStore'
export function App() { const hydrate = useAuthStore((s) => s.hydrate); useEffect(() => { void hydrate() }, [hydrate]); return <RouterProvider router={router} /> }
