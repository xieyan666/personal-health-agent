import { FilePdfOutlined, HeartFilled } from '@ant-design/icons'
import { Button, Card, message } from 'antd'
import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../../store/authStore'
import { createConversation, listConversationMessages, listConversations, streamHealth, type ConversationSummary, type HealthChatRequest } from '../../../api/healthAgent'
import { AgentTracePanel } from './components/AgentTracePanel'
import { ChatInput } from './components/ChatInput'
import { ChatMessageList } from './components/ChatMessageList'
import { ConversationSidebar } from './components/ConversationSidebar'
import { HealthContextPanel } from './components/HealthContextPanel'
import { HealthPlanModal } from './components/HealthPlanModal'
import { starterQuestions, type ChatMessage } from './mockHealthAssistant'
import { getMentalAssessments, type MentalAssessment } from '../../../api/mentalHealth'
import '../../../styles/assistant-layout.css'

export function HealthAssistant() {
  const username = useAuthStore(s => s.user?.username || '员工')
  const location = useLocation()
  const navigate = useNavigate()
  const [active, setActive] = useState<string | null>(null); const [sessions, setSessions] = useState<ConversationSummary[]>([]); const [input, setInput] = useState(''); const [messages, setMessages] = useState<ChatMessage[]>([]); const [loading, setLoading] = useState(false); const [planOpen, setPlanOpen] = useState(false); const [uploadName, setUploadName] = useState(''); const [assessmentContext, setAssessmentContext] = useState<HealthChatRequest['source_context']>(null); const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const state = location.state as { source?: string; assessmentId?: string; assessmentType?: string } | null
    if (state?.source !== 'mental_assessment' || !state.assessmentId || !state.assessmentType) return
    void getMentalAssessments().then((records) => {
      const assessment = records.find((item) => item.id === state.assessmentId && item.assessment_type === state.assessmentType)
      if (!assessment) { message.error('未找到本次心理测评结果，请从测评结果页重新发起咨询。'); return }
      setInput(buildMentalAssessmentPrefill(assessment))
      setAssessmentContext({ source: 'mental_assessment', assessment_id: assessment.id, assessment_type: assessment.assessment_type })
    }).catch(() => message.error('心理测评结果加载失败，请稍后重试'))
      .finally(() => navigate(location.pathname, { replace: true, state: null }))
  }, [location.key, location.pathname, location.state, navigate])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])
  const refreshSessions = async () => { const data = await listConversations(); setSessions(data); return data }
  useEffect(() => {
    void refreshSessions().then(data => {
      if (!data[0]) return
      setActive(data[0].id)
      void listConversationMessages(data[0].id).then(items => {
        const restored = items
          .filter(item => item.role === 'user' || item.role === 'assistant')
          .map(item => ({ id: item.id, role: item.role as 'user' | 'assistant', content: item.content }))
        setMessages(restored)
      })
    }).catch(() => message.error('会话加载失败，请稍后重试'))
  }, [])
  const newConversation = async () => { try { const item = await createConversation('新的健康咨询'); setActive(item.id); setMessages([]); setInput(''); setUploadName(''); setAssessmentContext(null); await refreshSessions() } catch { message.error('新建会话失败，请稍后重试') } }
  const selectConversation = async (id: string) => { try { const items = await listConversationMessages(id); setActive(id); setMessages(items.filter(item => item.role === 'user' || item.role === 'assistant').map(item => ({ id: item.id, role: item.role as 'user' | 'assistant', content: item.content }))) } catch { message.error('历史消息加载失败，请稍后重试') } }
  const send = async () => { const text = input.trim(); if (!text || loading) return; const id = String(Date.now()); let conversationId = active; const sourceContext = assessmentContext; setMessages(current => [...current, { id: `${id}-u`, role: 'user', content: text }, { id: `${id}-a`, role: 'assistant', content: '' }]); setInput(''); setLoading(true); try { if (!conversationId) { const item = await createConversation(text.slice(0, 80)); conversationId = item.id; setActive(item.id) } await streamHealth({ message: text, conversation_id: conversationId, source_context: sourceContext }, (chunk, returnedId) => { if (returnedId && returnedId !== conversationId) { conversationId = returnedId; setActive(returnedId) }; setMessages(current => current.map(item => item.id === `${id}-a` ? { ...item, content: item.content + chunk } : item)) }); await refreshSessions() } catch { setMessages(current => current.map(item => item.id === `${id}-a` && !item.content ? { ...item, content: 'AI服务暂时不可用，请稍后重试。' } : item)); message.error('AI服务暂时不可用，请稍后重试。') } finally { setAssessmentContext(null); setLoading(false) } }
  const chooseQuick = (text: string) => { setInput(text) }
  return <section className="assistant-page"><div className="assistant-heading"><div><div className="eyebrow">HEALTH SUPERVISOR AGENT</div><p>面向员工的统一健康咨询与改善建议</p></div><div className="assistant-mode"><HeartFilled /> Health Supervisor</div></div><div className="assistant-layout"><ConversationSidebar active={active} sessions={sessions} onNew={() => void newConversation()} onSelect={id => void selectConversation(id)} onQuick={chooseQuick} /><main className="assistant-chat"><div className="assistant-chat-header"><div><strong>{active ? (sessions.find(item => item.id === active)?.title || '健康咨询') : '新的健康咨询'}</strong><small>你的健康信息仅用于本次咨询展示</small></div><Button type="text" onClick={() => void newConversation()}>新建</Button></div><div className="assistant-chat-scroll"><div className="assistant-welcome"><div className="assistant-welcome-icon"><HeartFilled /></div><h3>你好，{username} 👋</h3><p>我是你的 AI 健康助手。<br />我可以结合你的健康档案、体检报告和近期健康数据，帮助你了解健康状态并制定改善计划。</p><div className="assistant-starters">{starterQuestions.map(question => <Button key={question} onClick={() => chooseQuick(question)}>{question}</Button>)}</div></div><ChatMessageList messages={messages} loading={loading} /><div ref={bottomRef} /></div><ChatInput value={input} loading={loading} onChange={setInput} onSend={send} onUpload={name => setUploadName(name)} />{uploadName && <div className="assistant-upload-status"><FilePdfOutlined /> {uploadName}<span>正在准备上传... Mock解析完成</span><Button type="link" onClick={() => setInput(`请解读我的文件：${uploadName}`)}>立即解读</Button></div>}</main><aside className="assistant-context"><HealthContextPanel /><AgentTracePanel /><Card className="assistant-plan-card"><strong>健康计划</strong><p>把对话中的建议整理成可执行的 7 天计划。</p><Button type="link" onClick={() => setPlanOpen(true)}>生成7天健康计划</Button></Card></aside></div><HealthPlanModal open={planOpen} onClose={() => setPlanOpen(false)} /></section>
}

function buildMentalAssessmentPrefill(assessment: MentalAssessment) {
  const score = assessment.raw_score ?? assessment.score ?? '--'
  const result = typeof assessment.result_summary?.display_level === 'string' ? assessment.result_summary.display_level : assessment.level ?? '已完成'
  if (assessment.assessment_type === 'PSS-10') return `我刚完成 PSS-10 压力感受自评，得分 ${score}/40，结果为“${result}”。请结合我近期的心理状态和健康数据，帮我分析目前主要需要关注的问题，并给出非诊断性的改善建议。`
  if (assessment.assessment_type === 'WHO-5') return `我刚完成 WHO-5 幸福感自评，得分 ${score}/25，幸福感指数 ${assessment.percentage_score ?? '--'}/100。请结合我近期的心理状态，帮我分析哪些方面值得继续保持、哪些方面需要关注。`
  if (assessment.assessment_type === 'GAD-7') return `我刚完成 GAD-7 焦虑症状筛查，得分 ${score}/21，结果为“${result}”。请结合我近期状态，帮我进行非诊断性的分析，并给出改善建议。`
  if (assessment.assessment_type === 'PHQ-9') return `我刚完成 PHQ-9 抑郁症状筛查，得分 ${score}/27，结果为“${result}”。请结合我近期状态进行非诊断性的分析，并告诉我接下来可以关注哪些方面。`
  return `我刚完成 ${assessment.assessment_type} 心理健康自评，得分 ${score}，结果为“${result}”。请基于本次结果提供非诊断性的心理健康建议。`
}
