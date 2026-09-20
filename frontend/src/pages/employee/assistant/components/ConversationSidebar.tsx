import { PlusOutlined } from '@ant-design/icons'
import { Button, Empty, List, Tag } from 'antd'
import { quickQuestions } from '../mockHealthAssistant'

export function ConversationSidebar({ active, sessions, onNew, onSelect, onQuick }: { active: string | null; sessions: { id: string; title?: string | null; updated_at: string; last_message_at?: string | null }[]; onNew: () => void; onSelect: (id: string) => void; onQuick: (text: string) => void }) {
  const formatTime = (value: string) => new Date(value).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
  return <aside className="assistant-conversations"><Button type="primary" block icon={<PlusOutlined />} onClick={onNew}>新建健康咨询</Button><div className="assistant-side-title">最近会话</div><List dataSource={sessions} locale={{ emptyText: <Empty description="暂无会话" /> }} renderItem={item => <List.Item className={active === item.id ? 'assistant-session active' : 'assistant-session'} onClick={() => onSelect(item.id)}><div><strong>{item.title || '新的健康咨询'}</strong><small>{formatTime(item.last_message_at || item.updated_at)}</small></div></List.Item>} /><div className="assistant-side-title">快捷咨询</div><div className="assistant-quick-list">{quickQuestions.map(([label, text]) => <Tag key={label} onClick={() => onQuick(text)}>{label}</Tag>)}</div></aside>
}
