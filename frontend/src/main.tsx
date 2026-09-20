import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import { App } from './App'
import './styles/index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><ConfigProvider theme={{ token: { colorPrimary: '#16A34A', borderRadius: 10, colorBgLayout: '#F8FAFC', fontFamily: 'Inter, "PingFang SC", "Microsoft YaHei", sans-serif' } }}><App /></ConfigProvider></React.StrictMode>)
