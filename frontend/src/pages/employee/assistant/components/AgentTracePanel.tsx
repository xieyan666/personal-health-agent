import { CheckCircleFilled, ClockCircleOutlined } from '@ant-design/icons'
import { Card, Collapse, Tag } from 'antd'
import { mockAgents } from '../mockHealthAssistant'

export function AgentTracePanel() { return <Card title="AI 分析过程" className="assistant-panel-card"><Collapse ghost items={[{ key: 'trace', label: '查看本次分析流程', children: <div className="assistant-trace">{mockAgents.map(([name, status, text]) => <div className="assistant-trace-row" key={name}><span>{status === 'success' ? <CheckCircleFilled className="trace-success" /> : <ClockCircleOutlined />} {name}</span><Tag color={status === 'success' ? 'success' : 'processing'}>{text}</Tag></div>)}</div> }]} /></Card> }
