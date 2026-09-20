import { Alert, Button, Modal, Progress, Radio, Result, Space, Tag, Typography, message } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { submitMentalAssessment, type MentalAssessment, type MentalAssessmentDefinition } from '../../api/mentalHealth'

type View = 'info' | 'assessment' | 'result'

interface Props {
  definition: MentalAssessmentDefinition | null
  open: boolean
  initialView: 'info' | 'assessment' | 'result'
  existingResult?: MentalAssessment | null
  onClose: () => void
  onCompleted: () => void
}

export function MentalAssessmentFlow({ definition, open, initialView, existingResult, onClose, onCompleted }: Props) {
  const navigate = useNavigate()
  const [view, setView] = useState<View>(initialView)
  const [index, setIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<MentalAssessment | null>(null)

  useEffect(() => {
    if (open) { setView(initialView); setIndex(0); setAnswers({}); setResult(existingResult ?? null) }
  }, [open, initialView, definition?.assessment_type, existingResult])

  const question = definition?.questions[index]
  const total = definition?.questions.length ?? 0
  const unavailable = definition?.questionnaire_status !== 'configured'
  const answered = question ? Object.prototype.hasOwnProperty.call(answers, question.id) : false
  const isLast = index === total - 1
  const completion = useMemo(() => total ? Math.round(Object.keys(answers).length / total * 100) : 0, [answers, total])
  const resultSummary = result?.result_summary ?? {}
  const displayLevel = typeof resultSummary.display_level === 'string' ? resultSummary.display_level : result?.level
  const maxScore = typeof resultSummary.max_score === 'number' ? resultSummary.max_score : undefined

  const submit = async () => {
    if (!definition || unavailable) return
    if (Object.keys(answers).length !== total) { message.warning('请完成全部题目后再提交'); return }
    setSubmitting(true)
    try {
      const record = await submitMentalAssessment({ assessment_type: definition.assessment_type, assessment_version: definition.version, answers: definition.questions.map((item) => ({ question_id: item.id, value: answers[item.id] })) })
      setResult(record); setView('result'); onCompleted()
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      message.error(detail?.message || '提交失败，请稍后重试')
    } finally { setSubmitting(false) }
  }

  const footer = view === 'info'
    ? [<Button key="close" onClick={onClose}>关闭</Button>, <Button key="start" type="primary" onClick={() => setView('assessment')}>开始测评</Button>]
    : view === 'assessment'
      ? [<Button key="cancel" onClick={onClose}>放弃本次测评</Button>, !unavailable && index > 0 ? <Button key="previous" onClick={() => setIndex((value) => value - 1)}>上一题</Button> : null, !unavailable && !isLast ? <Button key="next" type="primary" disabled={!answered} onClick={() => setIndex((value) => value + 1)}>下一题</Button> : null, !unavailable && isLast ? <Button key="submit" type="primary" loading={submitting} disabled={!answered} onClick={() => void submit()}>提交测评</Button> : null]
      : [<Button key="close" onClick={onClose}>完成</Button>, <Button key="assistant" type="primary" disabled={!result?.id} onClick={() => navigate('/employee/assistant', {
        state: {
          source: 'mental_assessment',
          assessmentId: result?.id,
          assessmentType: result?.assessment_type,
        },
      })}>咨询 AI 健康助手</Button>]

  return <Modal open={open} width={620} title={definition ? `${definition.name} · ${definition.title}` : '心理健康自评'} onCancel={onClose} footer={footer} destroyOnClose>
    {!definition ? null : view === 'info' ? <div className="assessment-info">
      <Typography.Title level={4}>{definition.title}</Typography.Title>
      <p>{definition.description}</p>
      <div className="assessment-info-grid"><span>量表名称</span><b>{definition.name}</b><span>参考时间</span><b>{definition.period || '过去两周'}</b><span>题目数量</span><b>{definition.question_count} 题</b><span>预计耗时</span><b>{definition.estimated_duration || `约 ${definition.estimated_minutes} 分钟`}</b><span>结果用途</span><b>{definition.result_usage}</b></div>
      <Alert type="info" showIcon message="测评说明" description={definition.disclaimer} />
      {definition.source?.source_name && <p className="assessment-source">量表来源：{definition.source.source_name}{definition.source.source_version ? ` · ${definition.source.source_version}` : ''}</p>}
      {unavailable && <Alert className="assessment-unavailable" type="warning" showIcon message="量表待配置" description="当前尚未配置经确认的正式题目、语言版本与评分规则；系统不会展示或使用未经确认的题目。" />}
    </div> : view === 'assessment' ? unavailable ? <div className="assessment-unavailable-state"><Result status="warning" title="该量表暂未开放" subTitle="正式题目、评分规则和使用许可尚未配置完成，因此无法开始测评。" /></div> : <div className="assessment-runner">
      <div className="assessment-progress"><span>进度 {index + 1} / {total}</span><Progress percent={completion} showInfo={false} strokeColor="#16a34a" /></div>
      {question && <><h3>{question.order}. {question.text}</h3><Radio.Group className="assessment-options" value={answers[question.id]} onChange={(event) => setAnswers((value) => ({ ...value, [question.id]: event.target.value }))}><Space direction="vertical">{question.options.map((option) => <Radio key={option.value} value={option.value}>{option.label}</Radio>)}</Space></Radio.Group></>}
      <p className="assessment-disclaimer">{definition.disclaimer}</p>
    </div> : <Result status={result?.safety_flag ? 'warning' : 'success'} title="测评完成" subTitle={`${definition.name} · ${definition.title}`} extra={<div className="assessment-result">
      {result?.safety_flag && <Alert type="error" showIcon message="我们注意到你报告了需要额外关注的情况" description="如果你现在感到无法保证自身安全，或情况正在加重，请及时联系当地紧急服务、专业支持人员或你信任的人。" action={<Space direction="vertical"><Button size="small" onClick={() => Modal.info({ title: '专业支持', content: '请考虑联系当地紧急服务、医疗机构或心理健康专业人员，获得及时支持。' })}>查看专业支持</Button><Button size="small" onClick={() => Modal.info({ title: '联系可信任的人', content: '可以尝试联系家人、朋友、同事或其他你信任的人，告诉他们你此刻需要陪伴或支持。' })}>联系可信任的人</Button></Space>} />}
      <p>完成时间：{result?.completed_at ? new Date(result.completed_at).toLocaleString('zh-CN', { hour12: false }) : '--'}</p>
      <p>测评分数：<b>{result?.raw_score ?? result?.score ?? '--'}{maxScore ? ` / ${maxScore}` : ''}</b>{result?.percentage_score != null ? `（${result.percentage_score}%）` : ''}</p>
      <p>筛查结果：{displayLevel ? <Tag color={result?.safety_flag || result?.needs_follow_up ? 'orange' : 'green'}>{displayLevel}</Tag> : '--'}</p>
      {result?.needs_follow_up && <p>建议：如相关困扰持续或影响日常生活，可考虑寻求专业支持。</p>}
      <p>{typeof resultSummary.result_note === 'string' ? resultSummary.result_note : definition.disclaimer}</p>
    </div>} />}
  </Modal>
}
