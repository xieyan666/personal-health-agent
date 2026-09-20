import { useCallback, useEffect, useState } from 'react'
import {
  Alert, Button, Card, Col, Drawer, Empty, Form, Input, InputNumber, Modal, Progress, Row, Select, Space, Spin, Switch, Tag, Tabs, message,
} from 'antd'
import {
  ApiOutlined, CheckCircleOutlined, CloseCircleOutlined, CloudServerOutlined, DatabaseOutlined, ExperimentOutlined,
  GlobalOutlined, LinkOutlined, PlusOutlined, ReloadOutlined, RocketOutlined, SafetyCertificateOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import { modelApi, type ModelOverview, type ModelOverviewItem, type ProviderItem, type QdrantDimensionInfo, type TestResult, type UsageInfo } from '../../api/models'
import './model-management.css'

const TYPE_COLORS: Record<string, string> = { chat: '#16a34a', embedding: '#0891b2', reranker: '#7c3aed' }
const STATUS_META: Record<string, { label: string; color: string }> = {
  active: { label: '正常', color: 'green' },
  disabled: { label: '已停用', color: 'default' },
  test: { label: '测试模式', color: 'orange' },
}

function TestResultPanel({ result, kind }: { result: TestResult | null; kind: 'chat' | 'embedding' }) {
  if (!result) return <div className="md-test-empty">尚未执行测试</div>
  return <div className={`md-test-panel ${result.success ? 'ok' : 'fail'}`}>
    <div className="md-test-head">
      {result.success ? <CheckCircleOutlined className="md-test-icon ok" /> : <CloseCircleOutlined className="md-test-icon fail" />}
      <b>{result.success ? '测试成功' : '测试失败'}</b>
      {typeof result.duration_ms === 'number' && <span>耗时 {result.duration_ms} ms</span>}
      {result.fake ? <Tag color="orange">TEST 模型</Tag> : null}
    </div>
    {kind === 'chat' && <p><span className="md-test-label">Model ID</span>{result.model_id}</p>}
    {kind === 'embedding' && <>
      <p><span className="md-test-label">模型名称</span>{result.model_name} · 维度 {result.dimension}</p>
      {result.vector_head?.length ? <div className="md-test-vector"><span>Vector 前 {result.vector_head.length} 位</span><code>[{result.vector_head.join(', ')}]</code></div> : null}
    </>}
    {result.response && <p className="md-test-response"><span className="md-test-label">Response</span>{result.response}</p>}
  </div>
}

function ModelsTab({ overview, onReload, onTestChat, onTestEmbedding, onSetDefault, onToggleStatus }: {
  overview: ModelOverview
  onReload: () => void
  onTestChat: (config: ModelOverviewItem) => void
  onTestEmbedding: (config: ModelOverviewItem) => void
  onSetDefault: (config: ModelOverviewItem) => void
  onToggleStatus: (config: ModelOverviewItem) => void
}) {
  const chatModels = overview.models.filter((item) => item.model_type === 'chat')
  const embeddingModels = overview.models.filter((item) => item.model_type === 'embedding')
  const otherModels = overview.models.filter((item) => item.model_type !== 'chat' && item.model_type !== 'embedding')
  const fakeEmbedding = embeddingModels.find((item) => item.provider_type === 'fake' || (item.model_name || '').toLowerCase().includes('fake'))
  const formalEmbedding = embeddingModels.find((item) => !(item.provider_type === 'fake' || (item.model_name || '').toLowerCase().includes('fake')))
  return <div className="md-tab-body">
    {!formalEmbedding && <Alert type="warning" showIcon className="md-alert" message={overview.warnings.embedding_note}
      description="正式 Embedding 模型可通过下方卡片「配置」或 Provider Tab 新增后设置，配置前 RAG 仅能验证测试链路。" />}
    {fakeEmbedding && <Alert type="info" showIcon className="md-alert" message={`${fakeEmbedding.name} 为开发测试用 Embedding（8 维，确定性词法向量）`}
      description="仅用于测试链路验证，不建议用于正式 RAG；正式检索请在配置正式 Embedding 后重新向量化知识库。" />}

    <div className="md-model-section"><h4>Chat Model</h4><span className="md-section-note">用于 Agent / DeepSeek 推理与生成回答</span></div>
    <Row gutter={[16, 16]}>
      {chatModels.map((config) => <ModelCard key={config.id} config={config} onTest={onTestChat} onSetDefault={onSetDefault} onToggle={onToggleStatus} kind="chat" />)}
      {!chatModels.length && <Col span={24}><Empty description="暂无 Chat 模型" /></Col>}
    </Row>

    <div className="md-model-section"><h4>Embedding Model</h4><span className="md-section-note">用于 Chunk → Embedding → Qdrant 及 Query 检索</span></div>
    <Row gutter={[16, 16]}>
      {embeddingModels.map((config) => <ModelCard key={config.id} config={config} onTest={onTestEmbedding} onSetDefault={onSetDefault} onToggle={onToggleStatus} kind="embedding" />)}
      {!embeddingModels.length && <Col span={24}><Empty description="暂无 Embedding 模型" /></Col>}
    </Row>

    {otherModels.length ? <>
      <div className="md-model-section"><h4>Reranker</h4><span className="md-section-note">第一版未配置</span></div>
      <div className="md-reranker-empty"><Tag>未配置</Tag> Reranker 暂不支持，第一版仅提供 Chat / Embedding。</div>
    </> : null}
  </div>
}

function ModelCard({ config, onTest, onSetDefault, onToggle, kind }: {
  config: ModelOverviewItem
  onTest: (config: ModelOverviewItem) => void
  onSetDefault: (config: ModelOverviewItem) => void
  onToggle: (config: ModelOverviewItem) => void
  kind: 'chat' | 'embedding'
}) {
  const status = STATUS_META[config.status] ?? { label: config.status, color: 'default' }
  const fake = config.provider_type === 'fake' || (config.model_name || '').toLowerCase().includes('fake')
  const color = TYPE_COLORS[config.model_type] ?? '#64748b'
  const usageCount = config.used_by_agents.length + config.used_by_knowledge_bases.length
  return <Col xs={24} md={12} xl={8}>
    <Card className={`md-card ${config.is_default ? 'default' : ''} ${fake ? 'fake' : ''}`}>
      <div className="md-card-top">
        <span className="md-card-icon" style={{ background: `${color}1a`, color }}>{kind === 'chat' ? <RocketOutlined /> : <DatabaseOutlined />}</span>
        <Space size={4} wrap>
          <Tag color={color} style={{ margin: 0 }}>{config.model_type_label}</Tag>
          {config.is_default && <Tag color="green" style={{ margin: 0 }}>默认</Tag>}
          <Tag color={status.color} style={{ margin: 0 }}>{status.label}</Tag>
        </Space>
      </div>
      <h3>{config.name}</h3>
      <div className="md-card-meta">
        <span>Provider：{config.provider_name}（{config.provider_type}）</span>
        <span>Model ID：<code>{config.model_name}</code></span>
        {kind === 'embedding' && <span>向量维度：<b>{config.vector_dimension ?? '—'}</b></span>}
        {kind === 'chat' && Object.keys(config.parameters).length ? <span>参数：{JSON.stringify(config.parameters)}</span> : null}
        <span>被使用：{config.used_by_agents.length} 个 Agent{kind === 'embedding' ? ` · ${config.used_by_knowledge_bases.length} 个知识库` : ''}</span>
        {config.updated_at ? <span className="md-muted">更新于 {new Date(config.updated_at).toLocaleString('zh-CN', { hour12: false })}</span> : null}
      </div>
      {fake && <div className="md-fake-tag">用途：TEST · 状态：开发测试 · 不建议用于正式 RAG</div>}
      <div className="md-card-actions">
        <Button size="small" type="primary" ghost onClick={() => onTest(config)}>测试</Button>
        <Button size="small" disabled={config.is_default} onClick={() => onSetDefault(config)}>设为默认</Button>
        <Switch size="small" checked={config.status === 'active'} onChange={() => onToggle(config)} checkedChildren="启用" unCheckedChildren="停用" />
      </div>
    </Card>
  </Col>
}

function ProvidersTab({ providers, onReload, onTest }: { providers: ProviderItem[]; onReload: () => void; onTest: (provider: ProviderItem) => void }) {
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<ProviderItem | null>(null)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()
  const openEditor = (provider: ProviderItem | null) => {
    setEditing(provider)
    form.resetFields()
    if (provider) form.setFieldsValue({ name: provider.name, provider_type: provider.provider_type, endpoint: provider.endpoint, status: provider.status, api_key: '' })
    else form.setFieldsValue({ provider_type: 'deepseek', status: 'active' })
    setOpen(true)
  }
  const save = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      const body = { name: values.name, provider_type: values.provider_type, endpoint: values.endpoint ?? null, api_key: values.api_key || null, status: values.status }
      if (editing) await modelApi.updateProvider(editing.id, body)
      else await modelApi.createProvider(body)
      message.success(editing ? 'Provider 已更新' : 'Provider 已创建')
      setOpen(false)
      onReload()
    } catch (e: any) {
      if (e?.errorFields) return
      message.error(e?.response?.data?.detail || '保存失败')
    } finally { setSaving(false) }
  }
  return <div className="md-tab-body">
    <div className="md-tab-head"><span className="md-tab-note">共 {providers.length} 个 Provider · API Key 仅显示掩码</span>
      <Button type="primary" icon={<PlusOutlined />} onClick={() => openEditor(null)}>新增 Provider</Button></div>
    <Row gutter={[16, 16]}>
      {providers.map((provider) => (
        <Col xs={24} md={12} xl={8} key={provider.id}>
          <Card className="md-provider-card">
            <div className="md-card-top">
              <span className="md-card-icon" style={{ background: '#0EA5B714', color: '#0EA5B7' }}><CloudServerOutlined /></span>
              <Space size={4} wrap>
                <Tag color={provider.provider_type === 'fake' ? 'orange' : 'blue'} style={{ margin: 0 }}>{provider.provider_type}</Tag>
                <Tag color={provider.status === 'active' ? 'green' : 'default'} style={{ margin: 0 }}>{provider.status === 'active' ? '正常' : '已停用'}</Tag>
              </Space>
            </div>
            <h3>{provider.name}</h3>
            <div className="md-card-meta">
              <span>{provider.endpoint ? <><GlobalOutlined /> {provider.endpoint}</> : 'Base URL：未设置'}</span>
              <span>API Key：<code>{provider.api_key_masked ?? '未配置'}</code></span>
              <span>模型数量：{provider.model_count}</span>
            </div>
            <div className="md-card-actions">
              <Button size="small" icon={<ApiOutlined />} onClick={() => onTest(provider)}>测试连接</Button>
              <Button size="small" onClick={() => openEditor(provider)}>编辑</Button>
            </div>
          </Card>
        </Col>
      ))}
    </Row>
    <Drawer title={editing ? '编辑 Provider' : '新增 Provider'} width={440} open={open} onClose={() => setOpen(false)} extra={<Button type="primary" loading={saving} onClick={() => void save()}>保存</Button>} destroyOnClose>
      <Form form={form} layout="vertical">
        <Form.Item name="name" label="Provider 名称" rules={[{ required: true, message: '请输入名称' }]}><Input placeholder="例如：DeepSeek 官方" maxLength={80} /></Form.Item>
        <Form.Item name="provider_type" label="类型" rules={[{ required: true }]}>
          <Select options={[{ value: 'deepseek', label: 'DeepSeek' }, { value: 'fake', label: 'Fake（本地测试）' }]} />
        </Form.Item>
        <Form.Item name="endpoint" label="Base URL"><Input placeholder="留空使用默认 https://api.deepseek.com" /></Form.Item>
        <Form.Item name="api_key" label="API Key" extra="支持 env:VAR 引用（推荐，如 env:DEEPSEEK_API_KEY）或直接填写 Key；保存后仅显示掩码">
          <Input.Password placeholder={editing ? '留空保持不变' : 'env:VAR 或明文 Key'} autoComplete="new-password" />
        </Form.Item>
        <Form.Item name="status" label="启用状态" rules={[{ required: true }]}><Select options={[{ value: 'active', label: '启用' }, { value: 'disabled', label: '停用' }]} /></Form.Item>
      </Form>
    </Drawer>
  </div>
}

function PolicyTab({ overview, onSetDefault }: { overview: ModelOverview; onSetDefault: (config: ModelOverviewItem) => void }) {
  const chatDefault = overview.models.find((item) => item.id === overview.defaults.chat)
  const embeddingDefault = overview.models.find((item) => item.id === overview.defaults.embedding)
  const [chatSel, setChatSel] = useState<string | undefined>(overview.defaults.chat ?? undefined)
  const [embSel, setEmbSel] = useState<string | undefined>(overview.defaults.embedding ?? undefined)
  useEffect(() => { setChatSel(overview.defaults.chat ?? undefined); setEmbSel(overview.defaults.embedding ?? undefined) }, [overview.defaults.chat, overview.defaults.embedding])
  const apply = (kind: 'chat' | 'embedding') => {
    const target = overview.models.find((item) => item.id === (kind === 'chat' ? chatSel : embSel))
    if (!target) return
    onSetDefault(target)
  }
  return <div className="md-tab-body">
    <div className="md-policy-grid">
      <Card className="md-policy-card" title="默认 Chat Model">
        <p className="md-policy-note">Agent / DeepSeek 推理与回答使用的默认模型</p>
        <Select style={{ width: '100%' }} value={chatSel} onChange={setChatSel} options={overview.models.filter((item) => item.model_type === 'chat').map((item) => ({ value: item.id, label: `${item.name}（${item.model_name}）` }))} placeholder="选择默认 Chat 模型" />
        {chatDefault && <div className="md-policy-current">当前默认：<b>{chatDefault.name}</b></div>}
        <Button type="primary" disabled={chatSel === overview.defaults.chat} onClick={() => apply('chat')} block style={{ marginTop: 12 }}>应用为默认 Chat</Button>
      </Card>
      <Card className="md-policy-card" title="默认 Embedding Model">
        <p className="md-policy-note">Chunk / Query 向量化使用的默认模型（切换时校验 Qdrant 维度）</p>
        <Select style={{ width: '100%' }} value={embSel} onChange={setEmbSel} options={overview.models.filter((item) => item.model_type === 'embedding').map((item) => ({ value: item.id, label: `${item.name}（${item.vector_dimension ?? '?'} 维）` }))} placeholder="选择默认 Embedding 模型" />
        {embeddingDefault && <div className="md-policy-current">当前默认：<b>{embeddingDefault.name}</b> · {embeddingDefault.vector_dimension ?? '?'} 维</div>}
        <Button type="primary" disabled={embSel === overview.defaults.embedding} onClick={() => apply('embedding')} block style={{ marginTop: 12 }}>应用为默认 Embedding</Button>
      </Card>
      <Card className="md-policy-card" title="默认 Reranker">
        <p className="md-policy-note">第一版未配置</p>
        <div className="md-reranker-empty"><Tag>未配置</Tag></div>
      </Card>
    </div>
    <p className="md-policy-tip">同一模型类型仅保留一个默认模型；切换 Embedding 会检测现有 Qdrant 向量维度，不一致时需要重新构建索引。</p>
  </div>
}

function UsageTab({ usage }: { usage: UsageInfo | null }) {
  if (!usage) return <div className="md-tab-body"><Spin /> 加载中...</div>
  const maxTrend = Math.max(1, ...usage.chat.trend.map((item) => item.count))
  return <div className="md-tab-body">
    <Row gutter={[16, 16]}>
      <Col xs={12} xl={6}><Card className="md-kpi"><b>{usage.chat.today_runs}</b><span>今日调用次数</span></Card></Col>
      <Col xs={12} xl={6}><Card className="md-kpi"><b>{usage.chat.success_rate}%</b><span>成功率</span></Card></Col>
      <Col xs={12} xl={6}><Card className="md-kpi"><b>{usage.chat.prompt_tokens + usage.chat.completion_tokens}</b><span>累计 Tokens</span></Card></Col>
      <Col xs={12} xl={6}><Card className="md-kpi"><b>{usage.chat.total_runs}</b><span>累计调用</span></Card></Col>
    </Row>
    <Card className="md-usage-card" title="近 7 天调用趋势">
      {usage.chat.trend.length ? <div className="md-trend">
        {usage.chat.trend.map((item) => (
          <div className="md-trend-col" key={item.date}><span className="md-trend-count">{item.count}</span><div className="md-trend-bar" style={{ height: `${Math.max(4, item.count / maxTrend * 100)}%` }} /><span className="md-trend-date">{item.date}</span></div>
        ))}
      </div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="近 7 天暂无调用记录" />}
    </Card>
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={14}>
        <Card className="md-usage-card" title="最近异常">
          {usage.chat.recent_errors.length ? usage.chat.recent_errors.map((error) => (
            <div className="md-error-item" key={error.id}><Tag color="red">{error.error_code || error.status}</Tag><span>{error.error_message || '未知错误'}</span><small>{error.created_at ? new Date(error.created_at).toLocaleString('zh-CN', { hour12: false }) : ''}</small></div>
          )) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无异常记录" />}
        </Card>
      </Col>
      <Col xs={24} xl={10}>
        <Card className="md-usage-card" title="Embedding 使用情况">
          <div className="md-usage-row"><span>已索引文档</span><b>{usage.embedding.indexed_documents}</b></div>
          {usage.embedding.knowledge_bases.map((item) => (
            <div className="md-usage-row" key={item.knowledge_base}><span>{item.knowledge_base}</span>{item.embedding_model_id ? <Tag color="green">已绑定 Embedding</Tag> : <Tag>未绑定</Tag>}</div>
          ))}
          {!usage.embedding.knowledge_bases.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无知识库使用 Embedding" />}
        </Card>
      </Col>
    </Row>
  </div>
}

export function ModelManagement() {
  const [overview, setOverview] = useState<ModelOverview | null>(null)
  const [usage, setUsage] = useState<UsageInfo | null>(null)
  const [qdrant, setQdrant] = useState<QdrantDimensionInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('models')
  const [testTarget, setTestTarget] = useState<ModelOverviewItem | null>(null)
  const [testKind, setTestKind] = useState<'chat' | 'embedding'>('chat')
  const [embeddingText, setEmbeddingText] = useState('甲状腺功能检查')
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [testing, setTesting] = useState(false)
  const [providerTest, setProviderTest] = useState<{ provider: ProviderItem; result: { success: boolean; duration_ms: number; detail: string } | null } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [ov, qd, us] = await Promise.all([modelApi.overview(), modelApi.qdrantDimension(), modelApi.usage()])
      setOverview(ov); setQdrant(qd); setUsage(us)
    } catch { message.error('模型数据加载失败') } finally { setLoading(false) }
  }, [])
  useEffect(() => { void load() }, [load])

  const runTest = async () => {
    if (!testTarget) return
    setTesting(true); setTestResult(null)
    try {
      const result = testKind === 'chat'
        ? await modelApi.testChat(testTarget.id)
        : await modelApi.testEmbedding(testTarget.id, embeddingText)
      setTestResult(result)
    } catch (e: any) {
      setTestResult({ success: false, duration_ms: 0, response: e?.response?.data?.detail || '测试失败' })
    } finally { setTesting(false) }
  }

  const openTest = (config: ModelOverviewItem, kind: 'chat' | 'embedding') => {
    setTestTarget(config); setTestKind(kind); setTestResult(null)
  }

  const setDefault = async (config: ModelOverviewItem) => {
    try {
      const result = await modelApi.setDefault(config.id)
      message.success(`已设为默认${config.model_type_label}模型`)
      if (result.qdrant_mismatch?.length) {
        Modal.warning({ title: 'Qdrant 向量维度不一致', content: `当前 Embedding 向量维度（${result.vector_dimension}）与现有 Qdrant 索引维度不一致（${result.qdrant_dimensions.join('、')}）。切换后需要重新构建索引并重新向量化知识库。` })
      }
      await load()
    } catch (e: any) { message.error(e?.response?.data?.detail || '设置失败') }
  }

  const toggleStatus = async (config: ModelOverviewItem) => {
    try {
      await modelApi.updateConfig(config.id, { status: config.status === 'active' ? 'disabled' : 'active' })
      message.success(config.status === 'active' ? '模型已停用' : '模型已启用')
      await load()
    } catch (e: any) { message.error(e?.response?.data?.detail || '操作失败') }
  }

  const testProvider = async (provider: ProviderItem) => {
    setProviderTest({ provider, result: null })
    try { const result = await modelApi.testProvider(provider.id); setProviderTest({ provider, result }) }
    catch (e: any) { setProviderTest({ provider, result: { success: false, duration_ms: 0, detail: e?.response?.data?.detail || '测试失败' } }) }
  }

  return <section className="md-page model-management-page">
    <p className="md-subtitle">AI Model Control Center：统一管理 Chat / Embedding 模型与 Provider、默认策略与运行情况。</p>
    <Card className="md-card-panel" styles={{ body: { padding: 0 } }}>
      <Tabs activeKey={tab} onChange={setTab} items={[
        { key: 'models', label: '模型', children: overview ? <ModelsTab overview={overview} onReload={() => void load()} onTestChat={(c) => openTest(c, 'chat')} onTestEmbedding={(c) => openTest(c, 'embedding')} onSetDefault={(c) => void setDefault(c)} onToggleStatus={(c) => void toggleStatus(c)} /> : <div className="md-tab-loading"><Spin /></div> },
        { key: 'providers', label: 'Provider', children: overview ? <ProvidersTab providers={overview.providers} onReload={() => void load()} onTest={(p) => void testProvider(p)} /> : <div className="md-tab-loading"><Spin /></div> },
        { key: 'policy', label: '调用策略', children: overview ? <PolicyTab overview={overview} onSetDefault={(c) => void setDefault(c)} /> : <div className="md-tab-loading"><Spin /></div> },
        { key: 'usage', label: '使用情况', children: <UsageTab usage={usage} /> },
      ]} />
    </Card>

    <Modal open={Boolean(testTarget)} title={`模型测试 · ${testTarget?.name ?? ''}`} footer={null} onCancel={() => setTestTarget(null)} width={520} destroyOnClose>
      {testTarget && <>
        {testKind === 'embedding' ? <div className="md-test-form">
          <label>输入测试文本</label>
          <Input value={embeddingText} onChange={(e) => setEmbeddingText(e.target.value)} placeholder="例如：甲状腺功能检查" />
        </div> : null}
        <Button type="primary" icon={<ExperimentOutlined />} loading={testing} onClick={() => void runTest()} block style={{ marginBottom: 12 }}>{testKind === 'chat' ? '执行连通测试' : '执行向量测试'}</Button>
        <TestResultPanel result={testResult} kind={testKind} />
      </>}
    </Modal>

    <Modal open={Boolean(providerTest)} title={`连接测试 · ${providerTest?.provider.name ?? ''}`} footer={null} onCancel={() => setProviderTest(null)} width={480} destroyOnClose>
      {providerTest?.result ? <div className={`md-test-panel ${providerTest.result.success ? 'ok' : 'fail'}`}>
        <div className="md-test-head">{providerTest.result.success ? <CheckCircleOutlined className="md-test-icon ok" /> : <CloseCircleOutlined className="md-test-icon fail" />}<b>{providerTest.result.success ? '连接成功' : '连接失败'}</b>{providerTest.result.duration_ms ? <span>耗时 {providerTest.result.duration_ms} ms</span> : null}</div>
        <p>{providerTest.result.detail}</p>
      </div> : <div className="md-test-empty"><Spin /> 正在连接 Provider...</div>}
    </Modal>
  </section>
}
