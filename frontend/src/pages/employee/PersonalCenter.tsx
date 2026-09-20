import { CameraOutlined, EditOutlined, IdcardOutlined, LockOutlined, SaveOutlined } from '@ant-design/icons'
import { Avatar, Button, Card, Col, Form, Input, Modal, Row, Spin, Switch, Tag, Upload, message } from 'antd'
import type { UploadProps } from 'antd'
import { useEffect, useState } from 'react'
import { changeMyPassword, getUserAvatar, getUserProfile, updateUserProfile, uploadUserAvatar, type UserProfile } from '../../api/userProfile'
import { getNotificationPreferences, updateNotificationPreferences, type NotificationPreferences } from '../../api/notifications'
import { useAuthStore } from '../../store/authStore'
import './personal-center.css'

function display(value?: string | null): string {
  return value?.trim() ? value : '未填写'
}

type PersonalCenterProps = { adminMode?: boolean }

export function PersonalCenter({ adminMode = false }: PersonalCenterProps) {
  const setUser = useAuthStore((state) => state.setUser)
  const currentUser = useAuthStore((state) => state.user)
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [avatarSource, setAvatarSource] = useState<string | null>(null)
  const [avatarUploading, setAvatarUploading] = useState(false)
  const [passwordModalOpen, setPasswordModalOpen] = useState(false)
  const [passwordSaving, setPasswordSaving] = useState(false)
  const [activeTab, setActiveTab] = useState<'profile' | 'password' | 'notifications'>('profile')
  const [preferences, setPreferences] = useState<NotificationPreferences | null>(null)
  const [preferencesLoading, setPreferencesLoading] = useState(false)
  const [passwordForm] = Form.useForm<{ currentPassword: string; newPassword: string; confirmPassword: string }>()
  const [form, setForm] = useState({
    display_name: '', email: '', phone: '', department: '', job_title: '', office_location: '', bio: '',
  })

  useEffect(() => {
    void (async () => {
      try {
        const data = await getUserProfile()
        setProfile(data)
        if (data.avatar_url) {
          try { setAvatarSource(URL.createObjectURL(await getUserAvatar())) } catch { /* keep initial avatar fallback */ }
        }
        setForm({
          display_name: data.display_name ?? '', email: data.email ?? '', phone: data.phone ?? '',
          department: data.department ?? '', job_title: data.job_title ?? '', office_location: data.office_location ?? '', bio: data.bio ?? '',
        })
      } catch { message.error('个人资料加载失败') } finally { setLoading(false) }
    })()
  }, [])

  useEffect(() => {
    if (!adminMode) return
    void getNotificationPreferences().then(setPreferences).catch(() => message.error('通知设置加载失败'))
  }, [adminMode])

  const uploadAvatar: UploadProps['beforeUpload'] = async (file) => {
    const allowed = ['image/jpeg', 'image/png', 'image/webp'].includes(file.type)
    if (!allowed) { message.error('仅支持 JPG、PNG 或 WebP 图片'); return Upload.LIST_IGNORE }
    if (file.size > 5 * 1024 * 1024) { message.error('头像文件不能超过 5MB'); return Upload.LIST_IGNORE }
    setAvatarUploading(true)
    try {
      const updated = await uploadUserAvatar(file as File)
      const nextSource = URL.createObjectURL(file as File)
      setAvatarSource((current) => { if (current) URL.revokeObjectURL(current); return nextSource })
      setProfile(updated)
      if (currentUser) {
        setUser({ ...currentUser, avatarUrl: nextSource, displayName: updated.display_name || currentUser.displayName })
      }
      message.success('头像已更新')
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '头像上传失败，请重试')
    } finally { setAvatarUploading(false) }
    return false
  }

  const save = async () => {
    setSaving(true)
    try {
      const updated = await updateUserProfile({
        display_name: form.display_name.trim() || undefined,
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
        department: form.department.trim() || null,
        job_title: form.job_title.trim() || null,
        office_location: form.office_location.trim() || null,
        bio: form.bio.trim() || null,
      })
      setProfile(updated)
      setEditing(false)
      // Keep the Header avatar/name in sync without a page reload.
      if (currentUser) setUser({ ...currentUser, avatarUrl: updated.avatar_url ?? currentUser.avatarUrl, displayName: updated.display_name || updated.username })
      message.success('个人资料已保存')
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      const firstMessage = Array.isArray(detail) ? detail[0]?.msg?.replace('Value error, ', '') : detail
      message.error(firstMessage || '保存失败，请重试')
    } finally { setSaving(false) }
  }

  const submitPasswordChange = async () => {
    try {
      const values = await passwordForm.validateFields()
      setPasswordSaving(true)
      await changeMyPassword(values.currentPassword, values.newPassword)
      passwordForm.resetFields()
      setPasswordModalOpen(false)
      message.success('密码修改成功，请使用新密码重新登录。')
      useAuthStore.getState().logout()
      window.setTimeout(() => window.location.assign('/login'), 650)
    } catch (error: any) {
      if (error?.errorFields) return
      const detail = error?.response?.data?.detail
      message.error(typeof detail === 'string' ? detail : '密码修改失败，请稍后重试')
    } finally {
      setPasswordSaving(false)
    }
  }

  const updatePreference = async (key: keyof NotificationPreferences, checked: boolean) => {
    setPreferences((current) => current ? { ...current, [key]: checked } : current)
    setPreferencesLoading(true)
    try {
      const updated = await updateNotificationPreferences({ [key]: checked })
      setPreferences(updated)
    } catch (error: any) {
      setPreferences((current) => current ? { ...current, [key]: !checked } : current)
      message.error(error?.response?.data?.detail || '通知设置保存失败')
    } finally { setPreferencesLoading(false) }
  }

  if (loading) return <div className="pc-loading"><Spin />正在加载...</div>
  const avatarText = (profile?.display_name || profile?.username || 'e').slice(0, 1)

  if (adminMode) {
    const roleLabel = profile?.role === 'system_admin' ? '系统管理员' : '企业管理员'
    const tabs = [
      { key: 'profile' as const, label: '基本资料' },
      { key: 'password' as const, label: '修改密码' },
      { key: 'notifications' as const, label: '通知设置' },
    ]
    return <section className="pc-page admin-pc-page">
      <div className="pc-heading"><div className="page-kicker">PERSONAL CENTER</div><h2>管理员个人中心</h2><p>管理您的管理员资料、密码与通知设置。</p></div>
      <div className="admin-pc-tabs" role="tablist">{tabs.map((tab) => <button key={tab.key} className={activeTab === tab.key ? 'active' : ''} onClick={() => setActiveTab(tab.key)} role="tab" aria-selected={activeTab === tab.key}>{tab.label}</button>)}</div>
      {activeTab === 'profile' && <Row gutter={[16, 16]} align="stretch" style={{ display: 'flex', alignItems: 'stretch' }}>
        <Col xs={24} md={8} style={{ display: 'flex' }}><Card className="pc-card admin-profile-card" style={{ flex: 1, width: '100%' }}>
          <div className="pc-avatar-block"><div className="pc-avatar-upload"><Avatar size={96} src={avatarSource ?? undefined} style={{ background: '#DCFCE7', color: '#15803D', fontSize: 32 }}>{avatarText}</Avatar><Upload accept="image/jpeg,image/png,image/webp" showUploadList={false} beforeUpload={uploadAvatar} disabled={avatarUploading}><Button className="pc-avatar-action" shape="circle" size="small" icon={<CameraOutlined />} loading={avatarUploading} /></Upload></div><Upload accept="image/jpeg,image/png,image/webp" showUploadList={false} beforeUpload={uploadAvatar} disabled={avatarUploading}><Button type="link" size="small" loading={avatarUploading}>上传头像</Button></Upload><h3>{display(profile?.display_name || profile?.username)}</h3><p>@{profile?.username}</p><Tag color="green">{roleLabel}</Tag></div>
          <div className="pc-readonly-list"><div className="pc-readonly"><span>用户名</span><b>{display(profile?.username)}</b></div><div className="pc-readonly"><span>角色</span><b>{roleLabel}</b></div><div className="pc-readonly"><span>所属企业</span><b>{display(currentUser?.company_id)}</b></div></div>
        </Card></Col>
        <Col xs={24} md={16} style={{ display: 'flex' }}><Card className="pc-card" title={<span><IdcardOutlined /> 基本资料</span>} extra={!editing ? <Button type="primary" icon={<EditOutlined />} onClick={() => setEditing(true)}>编辑资料</Button> : null} style={{ flex: 1, width: '100%' }}>
          {!editing ? <div className="pc-profile-view"><div className="pc-field"><span>姓名</span><b>{display(profile?.display_name)}</b></div><div className="pc-field"><span>用户名</span><b className="pc-readonly-text">{display(profile?.username)}</b></div><div className="pc-field"><span>邮箱</span><b>{display(profile?.email)}</b></div><div className="pc-field"><span>手机号</span><b>{display(profile?.phone)}</b></div><div className="pc-field"><span>角色</span><b>{roleLabel}</b></div><div className="pc-field"><span>所属企业</span><b>{display(currentUser?.company_id)}</b></div></div> : <div className="pc-form"><div className="pc-form-row"><label>姓名</label><Input value={form.display_name} maxLength={120} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></div><div className="pc-form-row"><label>邮箱</label><Input value={form.email} maxLength={320} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div><div className="pc-form-row"><label>手机号</label><Input value={form.phone} maxLength={32} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div><div className="pc-form-actions"><Button onClick={() => setEditing(false)}>取消</Button><Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={() => void save()}>保存修改</Button></div></div>}
        </Card></Col>
      </Row>}
      {activeTab === 'password' && <Card className="pc-card admin-tab-card" title={<span><LockOutlined /> 修改密码</span>}><div className="admin-password-intro">定期更新密码可以帮助保护管理员账号安全。</div><Form form={passwordForm} layout="vertical" requiredMark={false} autoComplete="off" className="admin-password-form"><Form.Item name="currentPassword" label="当前密码" rules={[{ required: true, message: '请输入当前密码' }]}><Input.Password autoComplete="current-password" /></Form.Item><Form.Item name="newPassword" label="新密码" rules={[{ required: true, message: '请输入新密码' }, { min: 8, message: '新密码长度至少为 8 位' }, { pattern: /(?=.*[A-Za-z])(?=.*\d)/, message: '新密码需至少包含字母和数字' }, ({ getFieldValue }) => ({ validator(_, value) { return value && value === getFieldValue('currentPassword') ? Promise.reject(new Error('新密码不能与当前密码相同')) : Promise.resolve() } })]}><Input.Password autoComplete="new-password" /></Form.Item><Form.Item name="confirmPassword" label="确认新密码" dependencies={['newPassword']} rules={[{ required: true, message: '请确认新密码' }, ({ getFieldValue }) => ({ validator(_, value) { return value === getFieldValue('newPassword') ? Promise.resolve() : Promise.reject(new Error('新密码和确认密码不一致')) } })]}><Input.Password autoComplete="new-password" /></Form.Item><div className="pc-form-actions"><Button type="primary" loading={passwordSaving} onClick={() => void submitPasswordChange()}>确认修改</Button></div></Form></Card>}
      {activeTab === 'notifications' && <Card className="pc-card admin-tab-card" title="通知设置"><p className="admin-notice-copy">选择需要接收的管理员工作提醒，修改会立即保存。</p><div className="admin-preferences">{[
        ['health_risk', '风险预警通知', '健康风险状态发生变化时提醒'], ['health_report', '体检待确认通知', '有新的体检报告需要处理时提醒'], ['agent_error', 'Agent异常通知', 'Agent运行异常时提醒'], ['system', '系统异常通知', '系统安全与授权异常时提醒'],
      ].map(([key, label, desc]) => <div className="admin-preference-row" key={key}><div><b>{label}</b><span>{desc}</span></div><Switch checked={Boolean(preferences?.[key as keyof NotificationPreferences])} loading={preferencesLoading} onChange={(checked) => void updatePreference(key as keyof NotificationPreferences, checked)} /></div>)}</div></Card>}
    </section>
  }

  const readonlyInfo = [
    { label: '用户名', value: profile?.username ?? '' },
    { label: '员工编号', value: profile?.username ?? '' },
    { label: '角色', value: profile?.role === 'employee' ? '员工' : profile?.role ?? '' },
    { label: '账号状态', value: profile?.status === 'active' ? '正常' : profile?.status ?? '' },
  ]
  return <section className="pc-page">
    <div className="pc-heading"><p>查看并完善你的个人账号信息</p></div>
    <Row gutter={[16, 16]} align="stretch" style={{ display: 'flex', alignItems: 'stretch' }}>
      <Col xs={24} md={8} style={{ display: 'flex' }}>
        <Card className="pc-card" style={{ flex: 1, width: '100%' }}>
          <div className="pc-avatar-block">
            <div className="pc-avatar-upload">
              <Avatar size={88} src={avatarSource ?? undefined} style={{ background: '#DCFCE7', color: '#15803D', fontSize: 30 }}>{avatarText}</Avatar>
              <Upload accept="image/jpeg,image/png,image/webp" showUploadList={false} beforeUpload={uploadAvatar} disabled={avatarUploading}>
                <Button className="pc-avatar-action" shape="circle" size="small" icon={<CameraOutlined />} loading={avatarUploading} aria-label="上传头像" />
              </Upload>
            </div>
            <Upload accept="image/jpeg,image/png,image/webp" showUploadList={false} beforeUpload={uploadAvatar} disabled={avatarUploading}>
              <Button type="link" size="small" loading={avatarUploading}>上传头像</Button>
            </Upload>
            <h3>{profile?.display_name || profile?.username}</h3>
            <p>@{profile?.username}</p>
            <Tag color="green">{profile?.role === 'employee' ? '员工' : profile?.role}</Tag>
          </div>
          <div className="pc-readonly-list">
            {readonlyInfo.map((item) => <div className="pc-readonly" key={item.label}>
              <span>{item.label}</span><b>{item.value || '未填写'}</b>
            </div>)}
          </div>
        </Card>
      </Col>
      <Col xs={24} md={16} style={{ display: 'flex' }}>
        <Card className="pc-card" title={<span><IdcardOutlined /> 个人资料</span>} extra={!editing ? <Button type="primary" icon={<EditOutlined />} onClick={() => setEditing(true)}>编辑资料</Button> : null} style={{ flex: 1, width: '100%' }}>
          {!editing ? (
            <div className="pc-profile-view">
              <div className="pc-field"><span>姓名</span><b>{display(profile?.display_name)}</b></div>
              <div className="pc-field"><span>用户名</span><b className="pc-readonly-text">{profile?.username}</b></div>
              <div className="pc-field"><span>员工编号</span><b className="pc-readonly-text">{profile?.username}</b></div>
              <div className="pc-field"><span>邮箱</span><b>{display(profile?.email)}</b></div>
              <div className="pc-field"><span>手机号</span><b>{display(profile?.phone)}</b></div>
              <div className="pc-field"><span>部门</span><b>{display(profile?.department)}</b></div>
              <div className="pc-field"><span>职位</span><b>{display(profile?.job_title)}</b></div>
              <div className="pc-field"><span>办公地点</span><b>{display(profile?.office_location)}</b></div>
              <div className="pc-field pc-field-bio"><span>个人简介</span><b>{display(profile?.bio)}</b></div>
            </div>
          ) : (
            <div className="pc-form">
              <div className="pc-form-row"><label>姓名</label><Input value={form.display_name} maxLength={120} onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="请输入姓名" /></div>
              <div className="pc-form-row"><label>邮箱</label><Input value={form.email} maxLength={320} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="name@example.com" /></div>
              <div className="pc-form-row"><label>手机号</label><Input value={form.phone} maxLength={32} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="请输入手机号" /></div>
              <div className="pc-form-row"><label>部门</label><Input value={form.department} maxLength={120} onChange={(e) => setForm({ ...form, department: e.target.value })} placeholder="请输入部门" /></div>
              <div className="pc-form-row"><label>职位</label><Input value={form.job_title} maxLength={120} onChange={(e) => setForm({ ...form, job_title: e.target.value })} placeholder="请输入职位" /></div>
              <div className="pc-form-row"><label>办公地点</label><Input value={form.office_location} maxLength={120} onChange={(e) => setForm({ ...form, office_location: e.target.value })} placeholder="请输入办公地点" /></div>
              <div className="pc-form-row pc-form-bio"><label>个人简介</label><Input.TextArea rows={4} maxLength={1000} value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} placeholder="介绍一下自己（可选）" /></div>
              <div className="pc-form-actions">
                <Button onClick={() => { setEditing(false); if (profile) setForm({ display_name: profile.display_name ?? '', email: profile.email ?? '', phone: profile.phone ?? '', department: profile.department ?? '', job_title: profile.job_title ?? '', office_location: profile.office_location ?? '', bio: profile.bio ?? '' }) }}>取消</Button>
                <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={() => void save()}>保存修改</Button>
              </div>
            </div>
          )}
        </Card>
      </Col>
    </Row>
    <Card className="pc-card pc-security-card" title={<span><LockOutlined /> 账号安全</span>}>
      <div className="pc-security-content">
        <div className="pc-security-copy"><b>登录密码</b><span>用于保护你的账号安全，建议定期更新密码。</span></div>
        <Button type="primary" icon={<LockOutlined />} onClick={() => setPasswordModalOpen(true)}>修改密码</Button>
      </div>
    </Card>
    <Modal
      title="修改密码"
      open={passwordModalOpen}
      confirmLoading={passwordSaving}
      okText="确认修改"
      cancelText="取消"
      onCancel={() => { if (!passwordSaving) { setPasswordModalOpen(false); passwordForm.resetFields() } }}
      onOk={() => void submitPasswordChange()}
      destroyOnClose
    >
      <Form form={passwordForm} layout="vertical" requiredMark={false} autoComplete="off">
        <Form.Item name="currentPassword" label="当前密码" rules={[{ required: true, message: '请输入当前密码' }]}>
          <Input.Password placeholder="请输入当前密码" autoComplete="current-password" />
        </Form.Item>
        <Form.Item name="newPassword" label="新密码" rules={[
          { required: true, message: '请输入新密码' },
          { min: 8, message: '新密码长度至少为 8 位' },
          { pattern: /(?=.*[A-Za-z])(?=.*\d)/, message: '新密码需至少包含字母和数字' },
          ({ getFieldValue }) => ({ validator(_, value) { return value && value === getFieldValue('currentPassword') ? Promise.reject(new Error('新密码不能与当前密码相同')) : Promise.resolve() } }),
        ]}>
          <Input.Password placeholder="至少 8 位，包含字母和数字" autoComplete="new-password" />
        </Form.Item>
        <Form.Item name="confirmPassword" label="确认新密码" dependencies={['newPassword']} rules={[
          { required: true, message: '请确认新密码' },
          ({ getFieldValue }) => ({ validator(_, value) { return value === getFieldValue('newPassword') ? Promise.resolve() : Promise.reject(new Error('新密码和确认密码不一致')) } }),
        ]}>
          <Input.Password placeholder="请再次输入新密码" autoComplete="new-password" />
        </Form.Item>
      </Form>
    </Modal>
  </section>
}
