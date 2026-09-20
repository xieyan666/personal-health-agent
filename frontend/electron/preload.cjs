const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('desktop', {
  platform: process.platform,
  isDesktop: true,
  credential: {
    getRecentAccounts: () => ipcRenderer.invoke('credential:getRecentAccounts'),
    saveAccount: (username, remember) => ipcRenderer.invoke('credential:saveAccount', username, remember),
    getPassword: (username) => ipcRenderer.invoke('credential:getPassword', username),
    savePassword: (username, password) => ipcRenderer.invoke('credential:savePassword', username, password),
    deletePassword: (username) => ipcRenderer.invoke('credential:deletePassword', username),
    removeAccount: (username) => ipcRenderer.invoke('credential:removeAccount', username),
  },
})
