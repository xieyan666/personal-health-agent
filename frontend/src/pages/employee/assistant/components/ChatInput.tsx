import { PaperClipOutlined, SendOutlined } from '@ant-design/icons'
import { Button, Dropdown, Input, message } from 'antd'
import { useRef, useState } from 'react'

export function ChatInput({ value, loading, onChange, onSend, onUpload }: { value: string; loading: boolean; onChange: (value: string) => void; onSend: () => void; onUpload: (name: string) => void }) {
  const [fileName, setFileName] = useState(''); const fileRef = useRef<HTMLInputElement>(null)
  const upload = (file: File) => { setFileName(file.name); onUpload(file.name); message.info('文件已加入准备队列（Mock）') }
  return <div className="assistant-input-wrap"><Dropdown menu={{ items: [{ key: 'checkup', label: '上传体检报告' }, { key: 'exam', label: '上传检查报告' }, { key: 'pdf', label: '上传健康 PDF' }], onClick: () => fileRef.current?.click() }}><Button shape="circle" icon={<PaperClipOutlined />} /></Dropdown><input ref={fileRef} hidden type="file" accept=".pdf,.doc,.docx" onChange={e => e.target.files?.[0] && upload(e.target.files[0])} /><Input.TextArea value={value} autoSize={{ minRows: 1, maxRows: 4 }} placeholder={fileName || '输入你的健康问题...'} onChange={e => onChange(e.target.value)} onPressEnter={e => { if (!e.shiftKey) { e.preventDefault(); onSend() } }} /><Button type="primary" icon={<SendOutlined />} loading={loading} onClick={onSend}>发送</Button></div>
}
