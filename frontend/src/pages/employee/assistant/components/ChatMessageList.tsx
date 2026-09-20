import { Avatar, Empty, Spin } from 'antd'
import { RobotOutlined, UserOutlined } from '@ant-design/icons'
import type { ChatMessage } from '../mockHealthAssistant'
import { useEffect, useState } from 'react'
import { getUserAvatar } from '../../../../api/userProfile'
import { useAuthStore } from '../../../../store/authStore'

function MarkdownText({ text }: { text: string }) { return <div className="assistant-markdown">{text.split('\n').map((line, index) => <p key={`${index}-${line}`}>{line.startsWith('### ') ? <strong>{line.slice(4)}</strong> : line.startsWith('## ') ? <strong>{line.slice(3)}</strong> : line.startsWith('- ') ? <>• {line.slice(2)}</> : line || '\u00a0'}</p>)}</div> }
export function ChatMessageList({ messages, loading }: { messages: ChatMessage[]; loading: boolean }) {
  const user = useAuthStore((state) => state.user)
  const [avatarSource, setAvatarSource] = useState<string | null>(null)
  useEffect(() => {
    let source: string | null = null
    if (!user?.avatarUrl) { setAvatarSource(null); return }
    void getUserAvatar().then((blob) => { source = URL.createObjectURL(blob); setAvatarSource(source) }).catch(() => setAvatarSource(null))
    return () => { if (source) URL.revokeObjectURL(source) }
  }, [user?.id, user?.avatarUrl])
  return <div className="assistant-messages">
    {messages.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="开始一次健康咨询吧" /> : messages.map(item => {
      const isPending = loading && item.role === 'assistant' && !item.content
      return <div className={`assistant-message ${item.role}`} key={item.id}>
        <Avatar size={34} src={item.role === 'user' ? (avatarSource ?? user?.avatarUrl ?? undefined) : undefined} icon={item.role === 'user' ? <UserOutlined /> : <RobotOutlined />} className={item.role === 'user' ? 'assistant-user-avatar' : 'assistant-bot-avatar'} />
        <div className="assistant-bubble">{isPending ? <><Spin size="small" /> <span>健康助手正在思考...</span></> : <><MarkdownText text={item.content} />{loading && item.role === 'assistant' && item.content && <span className="assistant-stream-cursor" aria-label="正在生成">▌</span>}</>}</div>
      </div>
    })}
  </div>
}
