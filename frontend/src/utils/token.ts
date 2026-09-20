const ACCESS_KEY = 'health_access_token'
const REFRESH_KEY = 'health_refresh_token'
export const saveAccessToken = (value: string) => localStorage.setItem(ACCESS_KEY, value)
export const getAccessToken = () => localStorage.getItem(ACCESS_KEY)
export const removeAccessToken = () => localStorage.removeItem(ACCESS_KEY)
export const saveRefreshToken = (value: string) => localStorage.setItem(REFRESH_KEY, value)
export const getRefreshToken = () => localStorage.getItem(REFRESH_KEY)
export const removeRefreshToken = () => localStorage.removeItem(REFRESH_KEY)
export const clearToken = () => { removeAccessToken(); removeRefreshToken() }
