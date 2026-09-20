import { CheckCircleOutlined, HeartOutlined, RobotOutlined, ThunderboltOutlined, TeamOutlined, CoffeeOutlined, AppstoreOutlined, BookOutlined } from '@ant-design/icons'
import { Button, Card, Checkbox, Col, Empty, Input, Modal, Progress, Radio, Row, Slider, Spin, Tabs, Tag, message } from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import * as echarts from 'echarts'
import { getMentalAssessmentDefinitions, getMentalAssessments, getMentalTrend, getMentalWorkload, getTodayMentalCheckin, saveMentalCheckin, type MentalAssessment, type MentalAssessmentDefinition, type MentalCheckin, type MentalTrend } from '../../api/mentalHealth'
import { MentalAssessmentFlow } from '../../components/employee/MentalAssessmentFlow'
import './mental-wellness.css'

const MOODS = [
  { label: '很好', emoji: '😄' }, { label: '不错', emoji: '🙂' }, { label: '一般', emoji: '😐' }, { label: '有压力', emoji: '😟' }, { label: '状态较差', emoji: '😞' },
]
const SLEEP_FEELINGS = ['很好', '不错', '一般', '较差']
const STRESS_SOURCES = ['工作任务', '人际沟通', '睡眠不足', '家庭', '身体状态', '经济压力', '其他']
const MOOD_SCORE: Record<string, number> = { 很好: 5, 不错: 4, 一般: 3, 有压力: 2, 状态较差: 1 }
const MOOD_EMOJI: Record<string, string> = { 很好: '😄', 不错: '🙂', 一般: '😐', 有压力: '😟', 状态较差: '😞' }

const ASSESSMENT_COLORS: Record<string, string> = { 'WHO-5': '#0891b2', 'PSS-10': '#d97706', 'GAD-7': '#7c3aed', 'PHQ-9': '#dc2626' }

function TrendChart({ trend }: { trend: MentalTrend }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current)
    const isMood = trend.type === 'mood'
    chart.setOption({
      grid: { left: 40, right: 20, top: 24, bottom: 30 },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const point = params[0]
          const value = isMood ? MOODS.find((item) => MOOD_SCORE[item.label] === point.value)?.label ?? point.value : point.value
          return `${point.axisValue}<br/>${isMood ? '情绪' : trend.type === 'stress' ? '压力' : '精力'}：${value}`
        },
      },
      xAxis: { type: 'category', data: trend.data.map((item) => item.date.slice(5)), axisLabel: { color: '#7d91aa' }, axisLine: { lineStyle: { color: '#dce7e2' } } },
      yAxis: { type: 'value', min: isMood ? 1 : 0, max: 10, interval: isMood ? 1 : undefined, axisLabel: { color: '#7d91aa' }, splitLine: { lineStyle: { color: '#eef2f6' } } },
      series: [{
        type: 'line', data: trend.data.map((item) => item.value), smooth: true,
        symbol: 'circle', symbolSize: 6,
        lineStyle: { width: 3, color: trend.type === 'stress' ? '#16a34a' : trend.type === 'energy' ? '#0891b2' : '#d97706' },
        itemStyle: { color: trend.type === 'stress' ? '#16a34a' : trend.type === 'energy' ? '#0891b2' : '#d97706' },
        areaStyle: { color: 'rgba(22,163,74,0.08)' },
      }],
    })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, [trend])
  return <div ref={ref} className="mental-chart" />
}

function CheckinModal({ open, initial, onClose, onSaved }: { open: boolean; initial: MentalCheckin | null; onClose: () => void; onSaved: () => void }) {
  const [mood, setMood] = useState('一般')
  const [stress, setStress] = useState(5)
  const [energy, setEnergy] = useState(5)
  const [sleep, setSleep] = useState('一般')
  const [sources, setSources] = useState<string[]>([])
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    if (open) {
      setMood(initial?.mood ?? '一般')
      setStress(initial?.stress_level ?? 5)
      setEnergy(initial?.energy_level ?? 5)
      setSleep(initial?.sleep_feeling ?? '一般')
      setSources(initial?.stress_sources ?? [])
      setNote(initial?.note ?? '')
    }
  }, [open, initial])
  const submit = async () => {
    setSaving(true)
    try {
      await saveMentalCheckin({ mood, stress_level: stress, energy_level: energy, sleep_feeling: sleep, stress_sources: sources, note: note || null })
      message.success('今日心理状态已保存')
      onSaved()
    } catch { message.error('保存失败，请稍后重试') } finally { setSaving(false) }
  }
  return <Modal open={open} title="记录今日状态" onCancel={onClose} footer={<><Button onClick={onClose}>取消</Button><Button type="primary" loading={saving} onClick={() => void submit()}>保存今日状态</Button></>} destroyOnClose>
    <div className="mental-form">
      <div className="mental-form-label">今天整体感觉怎么样？</div>
      <div className="mental-moods">
        {MOODS.map((item) => <button key={item.label} type="button" className={mood === item.label ? 'active' : ''} onClick={() => setMood(item.label)}><span>{item.emoji}</span><small>{item.label}</small></button>)}
      </div>
      <div className="mental-form-label">压力程度 <small>{stress} / 10</small></div>
      <Slider min={1} max={10} value={stress} onChange={setStress} marks={{ 1: '低', 5: '中', 10: '高' }} />
      <div className="mental-form-label">精力程度 <small>{energy} / 10</small></div>
      <Slider min={1} max={10} value={energy} onChange={setEnergy} marks={{ 1: '低', 5: '中', 10: '高' }} />
      <div className="mental-form-label">睡眠感受</div>
      <Radio.Group value={sleep} onChange={(event) => setSleep(event.target.value)} options={SLEEP_FEELINGS.map((item) => ({ label: item, value: item }))} optionType="button" />
      <div className="mental-form-label">主要压力来源（可多选）</div>
      <Checkbox.Group value={sources} onChange={(values) => setSources(values as string[])} options={STRESS_SOURCES} />
      <div className="mental-form-label">备注</div>
      <Input.TextArea rows={3} value={note} onChange={(event) => setNote(event.target.value)} maxLength={500} placeholder="记录一下今天的感受（可选）" />
    </div>
  </Modal>
}

export function MentalWellness() {
  const navigate = useNavigate()
  const [today, setToday] = useState<MentalCheckin | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [workload, setWorkload] = useState<{ week_avg_stress: number; high_stress_days: number; avg_energy: number; recovery_status: string; stress_sources: { name: string; percent: number }[]; has_data: boolean } | null>(null)
  const [assessments, setAssessments] = useState<MentalAssessment[]>([])
  const [assessmentDefinitions, setAssessmentDefinitions] = useState<MentalAssessmentDefinition[]>([])
  const [selectedDefinition, setSelectedDefinition] = useState<MentalAssessmentDefinition | null>(null)
  const [assessmentView, setAssessmentView] = useState<'info' | 'assessment' | 'result'>('info')
  const [selectedResult, setSelectedResult] = useState<MentalAssessment | null>(null)
  const [assessmentOpen, setAssessmentOpen] = useState(false)
  const [historyDefinition, setHistoryDefinition] = useState<MentalAssessmentDefinition | null>(null)
  const [trend, setTrend] = useState<MentalTrend | null>(null)
  const [trendType, setTrendType] = useState<'mood' | 'stress' | 'energy'>('stress')
  const [trendDays, setTrendDays] = useState(30)
  const [loading, setLoading] = useState(true)

  const refreshToday = async () => { const checkin = await getTodayMentalCheckin(); setToday(checkin) }
  useEffect(() => {
    void (async () => {
      try {
        const [checkinResult, workloadResult, assessmentsResult, definitionsResult] = await Promise.allSettled([
          getTodayMentalCheckin(),
          getMentalWorkload(),
          getMentalAssessments(),
          getMentalAssessmentDefinitions(),
        ])
        if (checkinResult.status === 'fulfilled') setToday(checkinResult.value)
        if (workloadResult.status === 'fulfilled') setWorkload(workloadResult.value)
        if (assessmentsResult.status === 'fulfilled') setAssessments(assessmentsResult.value)
        if (definitionsResult.status === 'fulfilled') setAssessmentDefinitions(definitionsResult.value)
        if ([checkinResult, workloadResult, assessmentsResult, definitionsResult].some((result) => result.status === 'rejected')) {
          message.warning('部分心理健康数据暂时未能加载，请稍后刷新重试')
        }
      } finally { setLoading(false) }
    })()
  }, [])
  useEffect(() => {
    getMentalTrend(trendType, trendDays).then(setTrend).catch(() => setTrend(null))
  }, [trendType, trendDays])

  const moodLabel = today ? `${MOOD_EMOJI[today.mood] ?? ''} ${today.mood}` : '--'
  const stressPercent = today ? Math.round(today.stress_level / 10 * 100) : 0
  const stressText = today ? (today.stress_level >= 7 ? '偏高' : today.stress_level >= 5 ? '中等' : '较低') : '--'
  const sourceRows = useMemo(() => workload?.stress_sources?.slice(0, 5) ?? [], [workload])
  const refreshAssessments = async () => setAssessments(await getMentalAssessments())
  const openAssessment = (definition: MentalAssessmentDefinition, view: 'info' | 'assessment' | 'result', result: MentalAssessment | null = null) => {
    setSelectedDefinition(definition); setSelectedResult(result); setAssessmentView(view); setAssessmentOpen(true)
  }

  if (loading) return <div className="mental-loading"><Spin />正在加载心理健康数据...</div>
  return <section className="mental-page">
    <div className="mental-heading">
      <div><p>关注情绪、压力与工作状态，建立持续的心理健康记录</p></div>
      <Button type="primary" icon={<CheckCircleOutlined />} onClick={() => setModalOpen(true)}>记录今日状态</Button>
    </div>

    <Row gutter={[16, 16]} className="mental-cards">
      <Col xs={12} md={6}><div className="mental-status-card"><div className="mental-status-icon">😊</div><span>今日情绪</span><b>{moodLabel}</b></div></Col>
      <Col xs={12} md={6}><div className="mental-status-card"><div className="mental-status-icon">🌡️</div><span>压力水平</span><b>{today ? `${today.stress_level} / 10` : '--'}</b><small>{stressText}</small></div></Col>
      <Col xs={12} md={6}><div className="mental-status-card"><div className="mental-status-icon">⚡</div><span>精力状态</span><b>{today ? `${today.energy_level} / 10` : '--'}</b></div></Col>
      <Col xs={12} md={6}><div className="mental-status-card"><div className="mental-status-icon">😴</div><span>睡眠感受</span><b>{today?.sleep_feeling ?? '--'}</b></div></Col>
    </Row>

    <Card className="mental-card" title="心理状态趋势" extra={<div className="mental-trend-extra"><Tabs size="small" activeKey={trendType} onChange={(key) => setTrendType(key as 'mood' | 'stress' | 'energy')} items={[
      { key: 'mood', label: '情绪趋势' }, { key: 'stress', label: '压力趋势' }, { key: 'energy', label: '精力趋势' },
    ]} /><div className="mental-range"><Radio.Group size="small" value={trendDays} onChange={(event) => setTrendDays(event.target.value)} options={[
      { label: '近7天', value: 7 }, { label: '近30天', value: 30 }, { label: '近90天', value: 90 },
    ]} optionType="button" /></div></div>}>
      {trend && <div className="mental-trend-head">
        <span>近{trend.period}天平均{trend.type === 'mood' ? '情绪' : trend.type === 'stress' ? '压力' : '精力'}：<b>{trend.average}</b> / 10</span>
        <span className={trend.change > 0 && trend.type === 'stress' ? 'trend-up' : trend.change < 0 && trend.type === 'stress' ? 'trend-down' : trend.change >= 0 ? 'trend-down' : 'trend-up'}>
          {trend.type === 'mood' ? (trend.change >= 0 ? '↑' : '↓') : (trend.change >= 0 ? '↑' : '↓')} {Math.abs(trend.change)}
        </span>
      </div>}
      {trend && trend.data.length ? <TrendChart trend={trend} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无足够的心理状态记录，请先完成每日打卡" />}
    </Card>

    <Row gutter={[16, 16]} align="stretch" style={{ display: 'flex', alignItems: 'stretch' }}>
      <Col xs={24} xl={12} style={{ display: 'flex' }}><Card className="mental-card mental-workload" title="工作压力分析" style={{ flex: 1, width: '100%' }}>
        {!workload?.has_data ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无足够心理状态记录，请先完成每日打卡" /> : <>
          <Row gutter={[12, 12]}>
            <Col span={12}><div className="mental-metric"><small>本周平均压力</small><b>{workload.week_avg_stress} <em>/ 10</em></b></div></Col>
            <Col span={12}><div className="mental-metric"><small>连续高压力天数</small><b>{workload.high_stress_days} <em>天</em></b></div></Col>
            <Col span={12}><div className="mental-metric"><small>平均精力</small><b>{workload.avg_energy} <em>/ 10</em></b></div></Col>
            <Col span={12}><div className="mental-metric"><small>恢复状态</small><b>{workload.recovery_status}</b></div></Col>
          </Row>
          <div className="mental-source-title">主要压力来源</div>
          <div className="mental-sources">
            {sourceRows.map((item) => <div className="mental-source" key={item.name}>
              <span>{item.name}</span><Progress percent={item.percent} strokeColor="#16a34a" size="small" />
            </div>)}
          </div>
        </>}
      </Card></Col>
      <Col xs={24} xl={12} style={{ display: 'flex' }}><Card className="mental-card" title="心理健康自评" extra={<span className="mental-sensitive-label">敏感个人数据</span>} style={{ flex: 1, width: '100%' }}>
        <p className="mental-desc">帮助你了解近期心理状态变化。测评结果仅用于心理健康筛查与自我了解，不构成医学诊断。</p>
        <div className="mental-assessments">
          {assessmentDefinitions.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可用的心理健康自评量表" /> : assessmentDefinitions.map((item) => {
            const latest = assessments.find((row) => row.assessment_type === item.assessment_type)
            const color = ASSESSMENT_COLORS[item.assessment_type] ?? '#16a34a'
            const latestDisplayLevel = typeof latest?.result_summary?.display_level === 'string' ? latest.result_summary.display_level : latest?.level
            return <div className="mental-assessment" key={item.assessment_type}>
              <div className="mental-assessment-icon" style={{ background: `${color}1a`, color }}>{item.assessment_type === 'WHO-5' ? <HeartOutlined /> : item.assessment_type === 'PSS-10' ? <AppstoreOutlined /> : item.assessment_type === 'GAD-7' ? <ThunderboltOutlined /> : <CoffeeOutlined />}</div>
              <div className="mental-assessment-body">
                <b>{item.name} · {item.title}</b>
                {latest ? <small>最近完成：{latest.completed_at ? new Date(latest.completed_at).toLocaleDateString('zh-CN') : '--'}　结果：{latestDisplayLevel ?? '--'}</small> : <small>{item.questionnaire_status === 'configured' ? '尚未完成' : '正式题库待配置'}</small>}
              </div>
              <div className="mental-assessment-actions"><Button size="small" type="link" onClick={() => openAssessment(item, latest ? 'result' : 'info', latest ?? null)}>{latest ? '查看结果' : '查看说明'}</Button>{assessments.some((row) => row.assessment_type === item.assessment_type) && <Button size="small" type="link" onClick={() => setHistoryDefinition(item)}>历史记录</Button>}<Button size="small" type="primary" ghost onClick={() => openAssessment(item, 'assessment')}>{latest ? '重新测评' : '开始测评'}</Button></div>
            </div>
          })}
        </div>
      </Card></Col>
    </Row>

    <Card className="mental-card mental-ai-support">
      <div className="mental-ai-icon"><RobotOutlined /></div>
      <div className="mental-ai-body">
        <h3>AI心理支持</h3>
        <p>最近工作压力比较大？AI健康助手可以结合你的近期心理状态记录，为你提供压力管理和生活方式建议。</p>
      </div>
      <Button type="primary" size="large" icon={<RobotOutlined />} onClick={() => navigate('/employee/assistant?prompt=最近工作压力比较大，我想聊聊。')}>开始心理健康咨询</Button>
    </Card>

    <CheckinModal open={modalOpen} initial={today} onClose={() => setModalOpen(false)} onSaved={() => { setModalOpen(false); void refreshToday() }} />
    <MentalAssessmentFlow definition={selectedDefinition} open={assessmentOpen} initialView={assessmentView} existingResult={selectedResult} onClose={() => setAssessmentOpen(false)} onCompleted={() => { void refreshAssessments() }} />
    <Modal open={Boolean(historyDefinition)} title={`${historyDefinition?.name ?? ''} 历史记录`} footer={<Button onClick={() => setHistoryDefinition(null)}>关闭</Button>} onCancel={() => setHistoryDefinition(null)}>
      <div className="assessment-history">{assessments.filter((row) => row.assessment_type === historyDefinition?.assessment_type).map((row) => <button type="button" key={row.id} onClick={() => { setHistoryDefinition(null); openAssessment(historyDefinition!, 'result', row) }}><span>{row.completed_at ? new Date(row.completed_at).toLocaleDateString('zh-CN') : '--'}</span><b>{row.raw_score ?? row.score ?? '--'} 分</b><Tag color="green">{typeof row.result_summary?.display_level === 'string' ? row.result_summary.display_level : row.level ?? '已完成'}</Tag></button>)}</div>
    </Modal>
  </section>
}
