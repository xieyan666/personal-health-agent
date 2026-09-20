const { app, BrowserWindow, shell, ipcMain, safeStorage } = require('electron')
const path = require('node:path')
const fs = require('node:fs')

const isDevelopment = Boolean(process.env.VITE_DEV_SERVER_URL)
const MAX_RECENT_ACCOUNTS = 5

// ---------------------------------------------------------------
// Local credential storage (main process only).
// - recent-accounts.json        : last N successful usernames (no passwords).
// - encrypted-credentials.json  : username -> base64(safeStorage.encryptString).
// The two are kept in separate files so plaintext passwords never sit next to
// account metadata, and are only ever encrypted at rest.
// ---------------------------------------------------------------
function accountsPath() { return path.join(app.getPath('userData'), 'recent-accounts.json') }
function credentialsPath() { return path.join(app.getPath('userData'), 'encrypted-credentials.json') }

function readJson(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, 'utf-8')) } catch { return fallback }
}
function writeJson(file, data) {
  try { fs.writeFileSync(file, JSON.stringify(data, null, 2)) } catch (error) {
    console.error('[Electron] credential store write failed:', error.message)
  }
}

function registerCredentialIpc() {
  ipcMain.handle('credential:getRecentAccounts', () => readJson(accountsPath(), []))

  // Called only AFTER a successful backend login.
  ipcMain.handle('credential:saveAccount', (_event, username, remember) => {
    if (typeof username !== 'string' || !username.trim()) return readJson(accountsPath(), [])
    const accounts = readJson(accountsPath(), [])
    const entry = { username: username.trim(), last_login_at: new Date().toISOString(), remember_password: Boolean(remember) }
    const next = [entry, ...accounts.filter((item) => item.username !== entry.username)].slice(0, MAX_RECENT_ACCOUNTS)
    writeJson(accountsPath(), next)
    return next
  })

  ipcMain.handle('credential:getPassword', (_event, username) => {
    const base64 = readJson(credentialsPath(), {})[username]
    if (!base64) return null
    try {
      if (!safeStorage.isEncryptionAvailable()) return null
      return safeStorage.decryptString(Buffer.from(base64, 'base64'))
    } catch { return null }
  })

  ipcMain.handle('credential:savePassword', (_event, username, password) => {
    if (!safeStorage.isEncryptionAvailable()) return false
    const credentials = readJson(credentialsPath(), {})
    credentials[username] = safeStorage.encryptString(String(password)).toString('base64')
    writeJson(credentialsPath(), credentials)
    return true
  })

  ipcMain.handle('credential:deletePassword', (_event, username) => {
    const credentials = readJson(credentialsPath(), {})
    if (Object.prototype.hasOwnProperty.call(credentials, username)) {
      delete credentials[username]
      writeJson(credentialsPath(), credentials)
    }
    return true
  })

  ipcMain.handle('credential:removeAccount', (_event, username) => {
    const accounts = readJson(accountsPath(), []).filter((item) => item.username !== username)
    writeJson(accountsPath(), accounts)
    const credentials = readJson(credentialsPath(), {})
    if (Object.prototype.hasOwnProperty.call(credentials, username)) {
      delete credentials[username]
      writeJson(credentialsPath(), credentials)
    }
    return { accounts, passwordRemoved: true }
  })
}

function createWindow() {
  console.log('[Electron] BrowserWindow creation started')
  const window = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    title: '生命健康智能体',
    backgroundColor: '#F8FAFC',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  window.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
  console.log('[Electron] BrowserWindow created')

  if (isDevelopment) {
    const devServerUrl = process.env.VITE_DEV_SERVER_URL
    console.log('[Electron] VITE_DEV_SERVER_URL:', devServerUrl || '(not set)')
    console.log('[Electron] loadURL started:', devServerUrl)
    window.loadURL(devServerUrl)
      .then(() => console.log('[Electron] loadURL completed'))
      .catch((error) => console.error('[Electron] loadURL failed:', error.message))
    window.webContents.once('did-finish-load', () => console.log('[Electron] did-finish-load'))
    window.webContents.openDevTools({ mode: 'detach' })
  } else {
    console.log('[Electron] loading production dist/index.html')
    window.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }
}

app.whenReady().then(() => {
  console.log('[Electron] Electron started')
  registerCredentialIpc()
  createWindow()
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow() })
})

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
