import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert, Button, Card, Checkbox, Col, Drawer, Empty, Form, Input, Modal, Progress, Row, Select, Space, Spin, Tag, Upload, message,
} from 'antd'
import {
  ArrowLeftOutlined, CheckCircleOutlined, CloudUploadOutlined, CloseCircleOutlined, DatabaseOutlined, DeleteOutlined,
  FileTextOutlined, LoadingOutlined, PlusOutlined, ReloadOutlined, SearchOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import { knowledgeApi, type KnowledgeBase, type KnowledgeChunk, type KnowledgeDocument, type RagStatus, type RetrieveItem } from '../../api/knowledge'
import './knowledge-management.css'

const KB_STATUS_META: Record<string, { label: string; color: string }> = {
  active: { label: '可检索', color: 'green' },
  disabled: { label: '未启用', color: 'default' },
}
const DOC_STATUS_META: Record<string, { label: string; color: string }> = {
  stored: { label: '已上传', color: 'default' },
  processing: { label: '处理中', color: 'processing' },
  indexed: { label: '可检索', color: 'green' },
  failed: { label: '处理失败', color: 'red' },
}
const DOMAINS = ['体检检验', '睡眠健康', '营养健康', '心理健康', '企业健康管理', '其他']
const PIPELINE_STEPS = [
  { key: 'upload', label: '文件上传' },
  { key: 'parse', label: '文档解析' },
  { key: 'clean', label: '文本清洗' },
  { key: 'chunk', label: 'Chunk 切分' },
  { key: 'embed', label: 'Embedding' },
  { key: 'index', label: 'Qdrant 索引' },
]

function docPipelineState(doc: KnowledgeDocument): Record<string, 'done' | 'failed' | 'waiting'> {
  const meta = (doc.metadata ?? {}) as Record<string, unknown>
  const failed = doc.status === 'failed'
  const chunkCount = Number(meta.chunk_count ?? 0)
  const indexedCount = Number(meta.indexed_count ?? 0)
  return {
    upload: 'done',
    parse: failed ? 'failed' : meta.parser ? 'done' : 'waiting',
    clean: failed ? 'failed' : meta.parser ? 'done' : 'waiting',
    chunk: failed ? 'failed' : chunkCount > 0 ? 'done' : 'waiting',
    embed: failed ? 'failed' : indexedCount > 0 ? 'done' : 'waiting',
    index: failed ? 'failed' : doc.status === 'indexed' ? 'done' : 'waiting',
  }
}

function RagStatusPanel({ status }: { status: RagStatus | null }) {
  return <Card className="kb-card-panel" title="RAG 运行状态" extra={<span className="kb-panel-note">基础服务健康检查</span>}>
    {status ? <>
      <div className="kb-rag-components">
        {Object.values(status.components).map((component) => (
          <div className="kb-rag-component" key={component.name}>
            <span>{component.name}</span>
            {component.status === 'ok'
              ? <Tag color="green" style={{ margin: 0 }}><CheckCircleOutlined /> 正常</Tag>
              : <Tag color="red" style={{ margin: 0 }}><CloseCircleOutlined /> 异常</Tag>}
          </div>
        ))}
      </div>
      <div className="kb-rag-stats">
        <div><b>{status.stats.pending_documents}</b><span>待处理文档</span></div>
        <div><b>{status.stats.index_failures}</b><span>索引异常</span></div>
        <div><b>{status.stats.total_chunks}</b><span>Chunk 总数</span></div>
      </div>
      <p className="kb-rag-last">最后索引时间：{status.stats.last_indexed_at ? new Date(status.stats.last_indexed_at).toLocaleString('zh-CN', { hour12: false }) : '暂无'}</p>
    </> : <div className="kb-panel-loading"><Spin size="small" /> 正在检查基础服务...</div>}
  </Card>
}

function RecentFeed({ status }: { status: RagStatus | null }) {
  const recent = status?.recent ?? []
  return <Card className="kb-card-panel" title="最近处理">
    {recent.length ? <div className="kb-recent-list">
      {recent.map((item) => {
        const meta = DOC_STATUS_META[item.status] ?? { label: item.status, color: 'default' }
        return <div className="kb-recent-item" key={item.id}>
          <FileTextOutlined className="kb-recent-icon" />
          <div className="kb-recent-body">
            <b>{item.document_name}</b>
            <p>{item.status === 'indexed' ? `已完成向量化 · 生成 ${item.chunk_count} 个 Chunks` : item.status === 'failed' ? (item.error_message ?? '处理失败') : '处理中'}</p>
          </div>
          <div className="kb-recent-right">
            <Tag color={meta.color}>{meta.label}</Tag>
            <small>{new Date(item.updated_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })}</small>
          </div>
        </div>
      })}
    </div> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无处理记录" />}
  </Card>
}

function KbCard({ kb, onEnter, onRetrieve }: { kb: KnowledgeBase; onEnter: () => void; onRetrieve: () => void }) {
  const meta = KB_STATUS_META[kb.status] ?? { label: kb.status, color: 'default' }
  return <Card className="kb-card" styles={{ body: { padding: 18, display: 'flex', flexDirection: 'column', gap: 10, height: '100%' } }}>
    <div className="kb-card-top">
      <span className="kb-icon"><DatabaseOutlined /></span>
      <Tag color={meta.color}>{meta.label}</Tag>
    </div>
    <h3>{kb.name}</h3>
    <p className="kb-card-desc">{kb.description || '暂无描述'}</p>
    <div className="kb-meta">
      <Tag color="blue" style={{ margin: 0 }}>{kb.domain}</Tag>
      <span>{kb.document_count} 份文档 · {kb.chunk_count} Chunks</span>
    </div>
    <div className="kb-progress"><span>向量化进度</span><b>{kb.vector_progress}%</b></div>
    <Progress percent={kb.vector_progress} size="small" strokeColor="#16a34a" showInfo={false} />
    <div className="kb-agent-tags">
      {kb.agents.length ? kb.agents.slice(0, 2).map((agent) => <Tag key={agent.id} color="green" style={{ margin: 0 }}>{agent.name}</Tag>) : <span className="kb-no-agent">未绑定 Agent</span>}
      {kb.agents.length > 2 ? <Tag style={{ margin: 0 }}>+{kb.agents.length - 2}</Tag> : null}
    </div>
    <div className="kb-card-actions">
      <Button size="small" type="primary" onClick={onEnter}>进入知识库</Button>
      <Button size="small" ghost type="primary" icon={<SearchOutlined />} onClick={onRetrieve}>检索测试</Button>
    </div>
  </Card>
}

function PipelineDrawer({ doc, open, onClose, onRetry }: { doc: KnowledgeDocument | null; open: boolean; onClose: () => void; onRetry: (doc: KnowledgeDocument) => void }) {
  const state = doc ? docPipelineState(doc) : null
  return <Drawer title={`处理流水线 · ${doc?.name ?? ''}`} width={460} open={open} onClose={onClose}>
    {doc && state ? <div className="kb-pipeline">
      {PIPELINE_STEPS.map((step) => {
        const stepState = state[step.key]
        return <div className={`kb-pipeline-step ${stepState}`} key={step.key}>
          <span className="kb-pipeline-dot">
            {stepState === 'done' ? <CheckCircleOutlined /> : stepState === 'failed' ? <CloseCircleOutlined /> : <span className="kb-pipeline-wait" />}
          </span>
          <span className="kb-pipeline-label">{step.label}</span>
          <span className="kb-pipeline-state">
            {stepState === 'done' ? '完成' : stepState === 'failed' ? '失败' : '等待'}
          </span>
        </div>
      })}
      <div className="kb-pipeline-result">
        {doc.status === 'indexed' ? <>
          <div className="kb-pipeline-ok"><CheckCircleOutlined /> 已生成 {String((doc.metadata ?? {}).chunk_count ?? 0)} Chunks</div>
          <div className="kb-pipeline-ok">状态：可检索</div>
        </> : doc.status === 'failed' ? <>
          <div className="kb-pipeline-fail"><CloseCircleOutlined /> {doc.error_message || '处理失败'}</div>
          <Button type="primary" icon={<ReloadOutlined />} onClick={() => onRetry(doc)}>重新处理</Button>
        </> : <div className="kb-pipeline-loading"><LoadingOutlined /> 处理中...</div>}
      </div>
    </div> : null}
  </Drawer>
}

function DocTab({ docs, onUpload, onRetry, onDelete, onViewChunks }: {
  docs: KnowledgeDocument[]
  onUpload: (file: File) => boolean
  onRetry: (doc: KnowledgeDocument) => void
  onDelete: (doc: KnowledgeDocument) => void
  onViewChunks: (doc: KnowledgeDocument) => void
}) {
  return <div className="kb-tab-body">
    <div className="kb-upload-bar">
      <Upload accept=".pdf,.docx,.txt,.md" beforeUpload={(file) => { onUpload(file); return false }} showUploadList={false}>
        <Button type="primary" icon={<CloudUploadOutlined />}>上传文档</Button>
      </Upload>
      <span className="kb-upload-note">支持 PDF / DOCX / TXT / MD · 自动解析 → 切分 → 向量化 → Qdrant</span>
    </div>
    <div className="kb-doc-table">
      <div className="kb-doc-row kb-doc-head">
        <span className="kb-doc-name">文档名称</span>
        <span className="kb-doc-cell">类型</span>
        <span className="kb-doc-cell">解析状态</span>
        <span className="kb-doc-cell">Chunks</span>
        <span className="kb-doc-cell">向量化</span>
        <span className="kb-doc-cell">更新时间</span>
        <span className="kb-doc-op">操作</span>
      </div>
      {docs.map((doc) => {
        const meta = DOC_STATUS_META[doc.status] ?? { label: doc.status, color: 'default' }
        const chunkCount = Number((doc.metadata ?? {}).chunk_count ?? 0)
        const indexed = doc.status === 'indexed'
        const ext = doc.name.split('.').pop()?.toUpperCase() ?? ''
        return <div className="kb-doc-row" key={doc.id}>
          <span className="kb-doc-name"><FileTextOutlined /> {doc.name}</span>
          <span className="kb-doc-cell"><Tag style={{ margin: 0 }}>{ext}</Tag></span>
          <span className="kb-doc-cell"><Tag color={meta.color} style={{ margin: 0 }}>{meta.label}</Tag></span>
          <span className="kb-doc-cell kb-doc-num">{doc.status === 'failed' ? '—' : chunkCount}</span>
          <span className="kb-doc-cell">{indexed ? <Tag color="green" style={{ margin: 0 }}>已索引</Tag> : doc.status === 'failed' ? <Tag color="red" style={{ margin: 0 }}>失败</Tag> : <Tag style={{ margin: 0 }}>待处理</Tag>}</span>
          <span className="kb-doc-cell kb-doc-time">{new Date(doc.updated_at ?? doc.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })}</span>
          <span className="kb-doc-op">
            {indexed && <Button type="link" size="small" onClick={() => onViewChunks(doc)}>查看Chunks</Button>}
            {doc.status === 'failed' && <Button type="link" size="small" icon={<ReloadOutlined />} onClick={() => onRetry(doc)}>重新处理</Button>}
            <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => onDelete(doc)}>删除</Button>
          </span>
        </div>
      })}
      {!docs.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无文档，点击上方按钮上传" style={{ padding: 24 }} />}
    </div>
  </div>
}

function ChunkTab({ chunks }: { chunks: KnowledgeChunk[] }) {
  const [page, setPage] = useState(1)
  const [viewing, setViewing] = useState<KnowledgeChunk | null>(null)
  const pageSize = 10
  const paged = chunks.slice((page - 1) * pageSize, page * pageSize)
  return <div className="kb-tab-body">
    {paged.map((chunk) => (
      <div className="kb-chunk-card" key={chunk.id}>
        <div className="kb-chunk-head">
          <span className="kb-chunk-no">Chunk #{chunk.chunk_index}</span>
          <span className="kb-chunk-doc">{chunk.document_name}</span>
          <span className="kb-chunk-meta">{chunk.char_count} 字符</span>
          <Button size="small" type="link" onClick={() => setViewing(chunk)}>查看详情</Button>
        </div>
        <p className="kb-chunk-preview">{chunk.content.slice(0, 180)}{chunk.content.length > 180 ? '…' : ''}</p>
      </div>
    ))}
    {!chunks.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无 Chunk，请先上传并处理文档" />}
    {chunks.length > pageSize && <div className="kb-pagination">
      <Button size="small" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>上一页</Button>
      <span>{page} / {Math.ceil(chunks.length / pageSize)}</span>
      <Button size="small" disabled={page >= Math.ceil(chunks.length / pageSize)} onClick={() => setPage((p) => p + 1)}>下一页</Button>
    </div>}
    <Modal open={Boolean(viewing)} title={`Chunk #${viewing?.chunk_index ?? ''} · ${viewing?.document_name ?? ''}`} footer={null} onCancel={() => setViewing(null)} width={640}>
      <p className="kb-chunk-full">{viewing?.content}</p>
    </Modal>
  </div>
}

function RetrieveTab({ kbId, onJump }: { kbId: string; onJump: (kb: KnowledgeBase) => void }) {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(5)
  const [results, setResults] = useState<RetrieveItem[]>([])
  const [retrieving, setRetrieving] = useState(false)
  const [searched, setSearched] = useState(false)
  const [error, setError] = useState('')
  const run = async () => {
    if (!query.trim()) { message.warning('请输入检索问题'); return }
    setRetrieving(true); setSearched(false); setError('')
    try {
      const data = await knowledgeApi.retrieve(kbId, query, topK)
      setResults(data.items); setSearched(true)
    } catch (e: any) {
      setError(e?.response?.data?.detail || '检索失败'); setResults([])
    } finally { setRetrieving(false) }
  }
  return <div className="kb-retrieve">
    <div className="kb-retrieve-left">
      <div className="kb-retrieve-title"><ThunderboltOutlined /> 检索测试</div>
      <p className="kb-retrieve-note">验证 Embedding + Qdrant 真实召回效果，不调用 DeepSeek。</p>
      <Input.TextArea
        value={query} onChange={(e) => setQuery(e.target.value)} rows={4}
        placeholder="例如：FT3升高需要结合哪些指标判断？" onPressEnter={() => void run()}
      />
      <div className="kb-retrieve-controls">
        <span>Top K</span>
        <Select value={topK} onChange={setTopK} style={{ width: 90 }} options={[3, 5, 8, 10].map((value) => ({ value, label: value }))} />
      </div>
      <Button type="primary" icon={<SearchOutlined />} loading={retrieving} onClick={() => void run()} block>开始检索</Button>
      {error && <Alert type="error" showIcon message={error} style={{ marginTop: 12 }} />}
    </div>
    <div className="kb-retrieve-right">
      {retrieving ? <div className="kb-retrieve-empty"><Spin /> 正在向量化查询并检索 Qdrant...</div>
        : !searched ? <div className="kb-retrieve-empty">输入问题后点击「开始检索」，右侧展示真实 TopK 结果。</div>
          : results.length ? results.map((item, index) => (
            <div className="kb-result-card" key={`${item.document_id}-${item.chunk_index}`}>
              <div className="kb-result-head">
                <span className="kb-result-rank">#{index + 1}</span>
                <span className="kb-result-score">Score {item.score.toFixed(4)}</span>
                <Tag color="green" style={{ margin: 0 }}>{item.source}</Tag>
              </div>
              <div className="kb-result-src">{item.document_name} · Chunk #{item.chunk_index}</div>
              <p className="kb-result-content">{item.content}</p>
              <div className="kb-result-meta">chunk_id: {item.document_id.slice(0, 8)}... · document_id: {item.document_id.slice(0, 8)}...</div>
            </div>
          )) : <div className="kb-retrieve-empty"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未检索到相关内容" /></div>}
    </div>
  </div>
}

function AgentBindingTab({ kb, agents, onSave }: { kb: KnowledgeBase; agents: { id: string; name: string; code: string; category: string }[]; onSave: (ids: string[]) => void }) {
  const [selected, setSelected] = useState<string[]>(kb.agents.map((agent) => agent.id))
  const [saving, setSaving] = useState(false)
  useEffect(() => { setSelected(kb.agents.map((agent) => agent.id)) }, [kb.id, kb.agents])
  const toggle = (id: string) => setSelected((prev) => prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id])
  const save = async () => {
    setSaving(true)
    try { await onSave(selected); message.success('Agent 绑定已保存') }
    catch { /* 已由上层处理 */ }
    finally { setSaving(false) }
  }
  return <div className="kb-tab-body">
    <div className="kb-bind-grid">
      {agents.map((agent) => (
        <label className={`kb-bind-card ${selected.includes(agent.id) ? 'selected' : ''}`} key={agent.id}>
          <Checkbox checked={selected.includes(agent.id)} onChange={() => toggle(agent.id)} />
          <div className="kb-bind-body">
            <b>{agent.name}</b>
            <p>{agent.code}</p>
            <Tag color={agent.category === 'health' ? 'green' : 'default'} style={{ margin: 0 }}>{agent.category}</Tag>
          </div>
        </label>
      ))}
    </div>
    <p className="kb-bind-note">仅被勾选的 Agent 可检索该知识库；Agent 运行时通过 KnowledgeSearchTool 访问。</p>
    <Button type="primary" loading={saving} onClick={() => void save()}>保存绑定</Button>
  </div>
}

export function KnowledgeManagement() {
  const [bases, setBases] = useState<KnowledgeBase[]>([])
  const [agents, setAgents] = useState<{ id: string; name: string; code: string; category: string }[]>([])
  const [ragStatus, setRagStatus] = useState<RagStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const [detail, setDetail] = useState<KnowledgeBase | null>(null)
  const [tab, setTab] = useState<'documents' | 'chunks' | 'retrieve' | 'agents'>('documents')
  const [docs, setDocs] = useState<KnowledgeDocument[]>([])
  const [chunks, setChunks] = useState<KnowledgeChunk[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [pipelineDoc, setPipelineDoc] = useState<KnowledgeDocument | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeDocument | null>(null)
  const [deleteBaseTarget, setDeleteBaseTarget] = useState<KnowledgeBase | null>(null)
  const [acting, setActing] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [data, available, status] = await Promise.all([knowledgeApi.list(), knowledgeApi.agents(), knowledgeApi.ragStatus()])
      setBases(data); setAgents(available); setRagStatus(status)
    } catch { message.error('知识库数据加载失败') } finally { setLoading(false) }
  }, [])
  useEffect(() => { void refresh() }, [refresh])

  const enterDetail = async (kb: KnowledgeBase, initialTab: 'documents' | 'chunks' | 'retrieve' | 'agents' = 'documents') => {
    setDetail(kb); setTab(initialTab); setDetailLoading(true)
    try {
      const [d, c] = await Promise.all([knowledgeApi.documents(kb.id), knowledgeApi.chunks(kb.id)])
      setDocs(d); setChunks(c)
    } catch { message.error('知识库详情加载失败') } finally { setDetailLoading(false) }
  }

  const handleUpload = (file: File) => {
    if (!detail) return false
    void (async () => {
      try {
        const doc = await knowledgeApi.upload(detail.id, file)
        setPipelineDoc(doc)
        setDocs((prev) => [doc, ...prev])
        await enterDetail(detail, 'documents')
        void refresh()
      } catch (e: any) {
        message.error(e?.response?.data?.detail || '文件处理失败')
      }
    })()
    return false
  }

  const handleRetry = async (doc: KnowledgeDocument) => {
    if (!detail) return
    try {
      const updated = await knowledgeApi.retry(detail.id, doc.id)
      setPipelineDoc(updated)
      setDocs((prev) => prev.map((item) => item.id === updated.id ? updated : item))
      await enterDetail(detail, 'documents')
      void refresh()
      message.success('已重新处理')
    } catch (e: any) { message.error(e?.response?.data?.detail || '重试失败') }
  }

  const handleDelete = async () => {
    if (!detail || !deleteTarget) return
    setActing(true)
    try {
      await knowledgeApi.deleteDocument(detail.id, deleteTarget.id)
      setDocs((prev) => prev.filter((item) => item.id !== deleteTarget.id))
      setChunks((prev) => prev.filter((item) => item.document_id !== deleteTarget.id))
      message.success('文档及其 MinIO 对象、Qdrant 向量已删除')
      setDeleteTarget(null)
      void refresh()
    } catch (e: any) { message.error(e?.response?.data?.detail || '删除失败') } finally { setActing(false) }
  }

  const handleDeleteBase = async () => {
    if (!deleteBaseTarget) return
    setActing(true)
    try {
      await knowledgeApi.deleteBase(deleteBaseTarget.id)
      message.success('知识库已删除')
      setDeleteBaseTarget(null)
      setBases((prev) => prev.filter((item) => item.id !== deleteBaseTarget.id))
      if (detail?.id === deleteBaseTarget.id) setDetail(null)
    } catch (e: any) { message.error(e?.response?.data?.detail || '删除失败') } finally { setActing(false) }
  }

  const createBase = async (values: any) => {
    try {
      const kb = await knowledgeApi.create({ name: values.name, domain: values.domain, description: values.description, enabled: true, agent_ids: values.agent_ids || [] })
      message.success('知识库已创建')
      setCreateOpen(false)
      await refresh()
      await enterDetail(kb, 'documents')
    } catch (e: any) { message.error(e?.response?.data?.detail || '创建失败') }
  }

  const saveBindings = async (ids: string[]) => {
    if (!detail) return
    const updated = await knowledgeApi.bindAgents(detail.id, ids)
    setDetail(updated)
    setBases((prev) => prev.map((item) => item.id === updated.id ? updated : item))
  }

  if (detail) {
    const meta = KB_STATUS_META[detail.status] ?? { label: detail.status, color: 'default' }
    return <section className="kb-page knowledge-management-page">
      <div className="kb-detail-head">
        <Button icon={<ArrowLeftOutlined />} onClick={() => setDetail(null)}>返回全部知识库</Button>
        <div className="kb-detail-title">
          <div className="kb-detail-icon"><DatabaseOutlined /></div>
          <div>
            <h3>{detail.name}</h3>
            <p>{detail.description || '暂无描述'}</p>
          </div>
        </div>
        <div className="kb-detail-stats">
          <div><b>{detail.document_count}</b><span>文档</span></div>
          <div><b>{detail.chunk_count}</b><span>Chunks</span></div>
          <div><b>{detail.vector_progress}%</b><span>向量化</span></div>
          <div className="kb-detail-status"><Tag color={meta.color}>{meta.label}</Tag><span>绑定：{detail.agents.map((agent) => agent.name).join('、') || '无'}</span></div>
        </div>
      </div>
      <Card className="kb-card-panel" styles={{ body: { padding: 0 } }}>
        <div className="kb-detail-tabs">
          {([['documents', '文档'], ['chunks', 'Chunks'], ['retrieve', '检索测试'], ['agents', 'Agent 绑定']] as const).map(([key, label]) => (
            <button type="button" key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>{label}</button>
          ))}
        </div>
        <div className="kb-tab-panel">
          {tab === 'documents' && <DocTab docs={docs} onUpload={handleUpload} onRetry={(doc) => void handleRetry(doc)} onDelete={setDeleteTarget} onViewChunks={(doc) => { setTab('chunks'); message.info(`已在 Chunks 中展示该文档的 ${chunks.filter((item) => item.document_id === doc.id).length} 个切片`) }} />}
          {tab === 'chunks' && <ChunkTab chunks={chunks} />}
          {tab === 'retrieve' && <RetrieveTab kbId={detail.id} onJump={(kb) => void enterDetail(kb, 'retrieve')} />}
          {tab === 'agents' && <AgentBindingTab kb={detail} agents={agents} onSave={(ids) => void saveBindings(ids)} />}
          {detailLoading && <div className="kb-tab-loading"><Spin /></div>}
        </div>
      </Card>
      <div className="kb-detail-footer">
        {detail.document_count > 0 && <Button danger icon={<DeleteOutlined />} onClick={() => setDeleteBaseTarget(detail)}>删除知识库</Button>}
      </div>
      <PipelineDrawer doc={pipelineDoc} open={Boolean(pipelineDoc)} onClose={() => setPipelineDoc(null)} onRetry={(doc) => void handleRetry(doc)} />
      <Modal title="删除文档" open={Boolean(deleteTarget)} onCancel={() => setDeleteTarget(null)} onOk={() => void handleDelete()} confirmLoading={acting} okText="确认删除" okButtonProps={{ danger: true }} cancelText="取消">
        <p>将同步删除：文档记录、全部 Chunks、Qdrant 向量点、MinIO 原始文件。此操作不可恢复。</p>
        <p style={{ color: '#dc2626' }}>文档：{deleteTarget?.name}</p>
      </Modal>
      <Modal title="删除知识库" open={Boolean(deleteBaseTarget)} onCancel={() => setDeleteBaseTarget(null)} onOk={() => void handleDeleteBase()} confirmLoading={acting} okText="确认删除" okButtonProps={{ danger: true }} cancelText="取消">
        <p>知识库当前包含 {deleteBaseTarget?.document_count ?? 0} 份文档。删除前请先删除全部文档；若已绑定 Agent 将自动解除绑定。</p>
      </Modal>
    </section>
  }

  return <section className="kb-page knowledge-management-page">
    <div className="kb-page-head">
      <div>
        <p className="kb-subtitle">企业知识内容工作区：上传 → 解析 → 切分 → Embedding → Qdrant，供已绑定 Agent 检索。</p>
      </div>
      <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>新建知识库</Button>
    </div>

    <Row gutter={[16, 16]} className="kb-kpi-row">
      <Col xs={12} xl={6}>
        <Card className="kb-kpi"><div className="kb-kpi-icon" style={{ color: '#16A34A', background: '#16A34A14' }}><DatabaseOutlined /></div><div className="kb-kpi-body"><small>知识库</small><b>{bases.length}</b><p>企业知识库总数</p></div></Card>
      </Col>
      <Col xs={12} xl={6}>
        <Card className="kb-kpi"><div className="kb-kpi-icon" style={{ color: '#0EA5B7', background: '#0EA5B714' }}><FileTextOutlined /></div><div className="kb-kpi-body"><small>知识文档</small><b>{bases.reduce((sum, item) => sum + item.document_count, 0)}</b><p>全部入库文档</p></div></Card>
      </Col>
      <Col xs={12} xl={6}>
        <Card className="kb-kpi"><div className="kb-kpi-icon" style={{ color: '#8B5CF6', background: '#8B5CF614' }}><ThunderboltOutlined /></div><div className="kb-kpi-body"><small>Chunks</small><b>{ragStatus?.stats.total_chunks ?? 0}</b><p>向量切片总数</p></div></Card>
      </Col>
      <Col xs={12} xl={6}>
        <Card className="kb-kpi"><div className="kb-kpi-icon" style={{ color: '#F59E0B', background: '#F59E0B14' }}><ReloadOutlined /></div><div className="kb-kpi-body"><small>待处理 / 异常</small><b>{(ragStatus?.stats.pending_documents ?? 0) + (ragStatus?.stats.index_failures ?? 0)}</b><p>需关注的文档</p></div></Card>
      </Col>
    </Row>

    <Row gutter={[16, 16]} align="stretch">
      <Col xs={24} xl={17}>
        <Card className="kb-card-panel" title={`我的知识库（${bases.length}）`}>
          {loading ? <div className="kb-panel-loading"><Spin /> 加载中...</div> : bases.length ? <Row gutter={[16, 16]}>
            {bases.map((kb) => (
              <Col xs={24} md={12} xl={8} key={kb.id}>
                <KbCard kb={kb} onEnter={() => void enterDetail(kb, 'documents')} onRetrieve={() => void enterDetail(kb, 'retrieve')} />
              </Col>
            ))}
          </Row> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无知识库，点击右上角「新建知识库」开始" style={{ padding: 32 }} />}
        </Card>
      </Col>
      <Col xs={24} xl={7}>
        <RagStatusPanel status={ragStatus} />
      </Col>
    </Row>

    <RecentFeed status={ragStatus} />

    <Modal open={createOpen} title="新建知识库" footer={null} onCancel={() => setCreateOpen(false)} destroyOnClose>
      <Form layout="vertical" onFinish={(values) => void createBase(values)} initialValues={{ domain: DOMAINS[0] }}>
        <Form.Item name="name" label="知识库名称" rules={[{ required: true, message: '请输入知识库名称' }]}>
          <Input placeholder="例如：体检与检验知识库" maxLength={160} />
        </Form.Item>
        <Form.Item name="domain" label="知识领域" rules={[{ required: true }]}>
          <Select options={DOMAINS.map((value) => ({ value, label: value }))} />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <Input.TextArea rows={3} placeholder="说明该知识库覆盖的知识范围与用途" maxLength={2000} />
        </Form.Item>
        <Form.Item name="agent_ids" label="可使用的 Agent（可稍后在详情页调整）">
          <Select mode="multiple" options={agents.map((agent) => ({ value: agent.id, label: agent.name }))} placeholder="选择后可立即绑定" />
        </Form.Item>
        <Button htmlType="submit" type="primary" block>创建并进入管理</Button>
      </Form>
    </Modal>
  </section>
}
