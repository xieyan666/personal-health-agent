import { DeleteOutlined, DownOutlined, LockOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Checkbox, Form, Input, Typography, message } from 'antd'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../api/auth'
import axios from 'axios'
import { useAuthStore } from '../store/authStore'

interface RecentAccount { username: string; last_login_at: string; remember_password: boolean }

function formatLoginTime(value: string): string {
  const date = new Date(value)
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const time = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  if (date.getTime() >= startOfToday) return `今天 ${time}`
  if (date.getTime() >= startOfToday - 86400000) return '昨天'
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }).replace('/', '-')
}

export function Login() {
  const navigate = useNavigate()
  const setSession = useAuthStore((s) => s.setSession)
  const [form] = Form.useForm()
  const [accounts, setAccounts] = useState<RecentAccount[]>([])
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [remember, setRemember] = useState(false)
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState('')
  const [loginError, setLoginError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const credential = window.desktop?.credential

  useEffect(() => {
    if (!credential) return
    void credential.getRecentAccounts().then(async (rows) => {
      setAccounts(rows)
      if (!rows.length) return
      const latest = rows[0]
      form.setFieldsValue({ username: latest.username })
      if (latest.remember_password) {
        const password = await credential.getPassword(latest.username)
        if (password) { form.setFieldsValue({ password }); setRemember(true) }
      }
    }).catch(() => undefined)
  }, [credential, form])

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setDropdownOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const visibleAccounts = accounts.filter((item) => item.username.toLowerCase().includes(filter.toLowerCase()))

  const selectAccount = async (account: RecentAccount) => {
    form.setFieldsValue({ username: account.username })
    if (account.remember_password && credential) {
      const password = await credential.getPassword(account.username)
      if (password) { form.setFieldsValue({ password }); setRemember(true) }
      else { form.setFieldsValue({ password: '' }); setRemember(false) }
    } else {
      form.setFieldsValue({ password: '' }); setRemember(false)
    }
    setDropdownOpen(false)
  }

  const removeAccount = async (event: React.MouseEvent, account: RecentAccount) => {
    event.stopPropagation()
    if (!credential) return
    await credential.removeAccount(account.username)
    const rows = await credential.getRecentAccounts()
    setAccounts(rows)
    message.success('已删除本机登录记录')
  }

  const submit = (values: { username: string; password: string }) => {
    setLoading(true)
    setLoginError(null)
    login(values.username, values.password)
      .then(async (result) => {
        setSession(result.user, result.access_token, result.refresh_token)
        if (credential) {
          // Only record the account after the backend accepted the credentials.
          await credential.saveAccount(values.username, remember)
          if (remember) await credential.savePassword(values.username, values.password)
          else await credential.deletePassword(values.username)
        }
        navigate(result.user.role === 'employee' ? '/employee/dashboard' : '/admin/dashboard')
      })
      .catch((error: unknown) => {
        const status = axios.isAxiosError(error) ? error.response?.status : undefined
        if (status === 401 || status === 404) setLoginError('账号不存在或密码错误')
        else if (status === 403) setLoginError('该账号无权登录或已被停用')
        else if (status) setLoginError('认证服务异常，请稍后重试')
        else setLoginError('无法连接认证服务，请确认后端已启动')
      })
      .finally(() => setLoading(false))
  }

  return <div className="login-page"><div className="login-decoration"><div className="decoration-orb orb-one" /><div className="decoration-orb orb-two" /><div className="login-quote">守护每一位员工的<br /><strong>身心健康</strong></div></div><div className="login-panel"><div className="login-brand"><span>🌿</span><div><b>Health AI</b><small>企业生命健康智能平台</small></div></div><Typography.Title level={2}>欢迎回来</Typography.Title><Typography.Paragraph type="secondary">登录您的健康工作台</Typography.Paragraph><Form form={form} layout="vertical" size="large" onFinish={submit}>
      {loginError && <Alert type="error" showIcon message={loginError} className="login-error-alert" />}
      <Form.Item label="账号" required>
        <div className="login-account-wrap" ref={containerRef}>
          <Form.Item name="username" rules={[{ required: true, message: '请输入账号' }]} style={{ marginBottom: 0 }}>
          <Input prefix={<UserOutlined />} placeholder="请输入账号" autoComplete="username"
            onFocus={() => setDropdownOpen(true)}
            onChange={(event) => {
              setFilter(event.target.value)
              setDropdownOpen(true)
              // A manually edited username must never keep another account's password.
              form.setFieldValue('password', '')
              setRemember(false)
            }}
            suffix={<DownOutlined className="login-account-caret" />} />
          </Form.Item>
          {dropdownOpen && visibleAccounts.length > 0 && <div className="recent-accounts">
            <div className="recent-accounts-title">最近登录账号</div>
            {visibleAccounts.map((item) => (
              <div className="recent-account" key={item.username} onClick={() => void selectAccount(item)}>
                <span className="recent-account-icon"><UserOutlined /></span>
                <span className="recent-account-body"><b>{item.username}</b><small>最近登录：{formatLoginTime(item.last_login_at)}</small></span>
                <button type="button" className="recent-account-remove" aria-label="删除记录" onClick={(event) => void removeAccount(event, item)}><DeleteOutlined /></button>
              </div>
            ))}
          </div>}
        </div>
      </Form.Item>
      <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
        <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" />
      </Form.Item>
      <div className="login-remember-row"><Checkbox checked={remember} onChange={(event) => setRemember(event.target.checked)}>记住密码</Checkbox></div>
      <Button type="primary" htmlType="submit" block loading={loading}>登录</Button>
    </Form><div className="login-footnote">忘记密码请联系企业管理员</div></div></div>
}
