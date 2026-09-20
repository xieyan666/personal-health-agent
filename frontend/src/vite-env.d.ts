/// <reference types="vite/client" />

interface DesktopCredentialApi {
  getRecentAccounts: () => Promise<Array<{ username: string; last_login_at: string; remember_password: boolean }>>
  saveAccount: (username: string, remember: boolean) => Promise<Array<{ username: string; last_login_at: string; remember_password: boolean }>>
  getPassword: (username: string) => Promise<string | null>
  savePassword: (username: string, password: string) => Promise<boolean>
  deletePassword: (username: string) => Promise<boolean>
  removeAccount: (username: string) => Promise<{ accounts: unknown[]; passwordRemoved: boolean }>
}

interface DesktopApi {
  platform: string
  isDesktop: boolean
  credential: DesktopCredentialApi
}

interface Window {
  desktop?: DesktopApi
}
