import { Modal, Tag } from 'antd'
import { mockPlan } from '../mockHealthAssistant'

export function HealthPlanModal({ open, onClose }: { open: boolean; onClose: () => void }) { return <Modal title="7天睡眠改善计划" open={open} onCancel={onClose} onOk={() => { onClose() }} okText="保存到健康计划" cancelText="取消"><p className="assistant-plan-intro">根据当前 Mock 分析，为你生成一份循序渐进的睡眠改善计划。</p>{mockPlan.map((item, index) => <div className="assistant-plan-day" key={item}><Tag color="green">Day {index + 1}</Tag><span>{item}</span></div>)}</Modal> }
