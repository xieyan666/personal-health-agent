import { AppstoreOutlined, ExperimentOutlined, SafetyOutlined, TeamOutlined, UserOutlined } from '@ant-design/icons'
import { Card, Col, Empty, Progress, Radio, Row, Select, Skeleton, Table, Tag, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import * as echarts from 'echarts'
import { useEffect, useRef, useState } from 'react'
import { getHealthAnalyticsSummary, type HealthAnalyticsSummary } from '../../api/adminAnalytics'
import { listDepartments } from '../../api/adminUsers'
import './employee-health-analysis.css'

const LEVEL_COLOR: Record<string, string> = { good: '#16A34A', stable: '#0EA5B7', attention: '#F59E0B', critical: '#EF4444', unknown: '#94A3B8' }

function useChart(id: string, option: echarts.EChartsOption | null, deps: unknown[]) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current || !option) return
    const chart = echarts.init(ref.current)
    chart.setOption(option)
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => { window.removeEventListener('resize', onResize); chart.dispose() }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps
  return ref
}

export function EmployeeHealthAnalysis() {
  const [period, setPeriod] = useState('30d')
  // The selected department only controls the current aggregation request.
  // Keep the complete option collection in separate state so a filtered
  // analytics response can never collapse the Select menu to one department.
  const [selectedDepartment, setSelectedDepartment] = useState<string | undefined>(undefined)
  const [allDepartments, setAllDepartments] = useState<string[]>([])
  const [data, setData] = useState<HealthAnalyticsSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    listDepartments()
      .then((items) => {
        if (!active) return
        setAllDepartments([...new Set(items.map(item => item.name.trim()).filter(Boolean))])
      })
      .catch(() => {
        // The summary endpoint is retained as a read-only fallback for older
        // deployments that do not expose the department catalog endpoint.
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    setLoading(true)
    getHealthAnalyticsSummary(period, selectedDepartment)
      .then((summary) => {
        setData(summary)
        // Only use the summary-provided list to fill an initially unavailable
        // catalog. Never replace a complete catalog after a filter is chosen.
        setAllDepartments((current) => current.length
          ? current
          : [...new Set((summary.available_departments ?? []).map(item => item.trim()).filter(Boolean))])
      })
      .catch(() => { message.error('健康分析数据加载失败'); setData(null) })
      .finally(() => setLoading(false))
  }, [period, selectedDepartment])
  const overview = data?.overview

  const distributionRef = useChart('distribution', data && data.health_distribution.length ? {
    tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
    legend: { bottom: 0, icon: 'circle', itemWidth: 8, itemHeight: 8, textStyle: { color: '#64748B', fontSize: 11 } },
    color: ['#16A34A', '#0EA5B7', '#F59E0B', '#EF4444', '#CBD5E1'],
    series: [{
      type: 'pie', radius: ['48%', '72%'], center: ['50%', '44%'],
      label: { show: false }, labelLine: { show: false },
      data: data!.health_distribution.map(item => ({ name: item.label, value: item.count })),
    }],
  } as echarts.EChartsOption : null, [data])

  const trendRef = useChart('trend', data && data.risk_trend.length ? {
    tooltip: { trigger: 'axis', formatter: (params: any) => `${params[0].axisValue}<br/>需关注比例：${params[0].value}%` },
    grid: { left: 42, right: 18, top: 24, bottom: 30 },
    xAxis: { type: 'category', data: data!.risk_trend.map(item => item.label), axisLabel: { color: '#7D91AA', fontSize: 11 }, axisLine: { lineStyle: { color: '#DCE7E2' } } },
    yAxis: { type: 'value', max: 100, axisLabel: { color: '#7D91AA', formatter: '{value}%' }, splitLine: { lineStyle: { color: '#EEF2F6' } } },
    series: [{
      type: 'line', smooth: true, data: data!.risk_trend.map(item => item.value),
      symbol: 'circle', symbolSize: 6,
      lineStyle: { width: 3, color: '#16A34A' },
      itemStyle: { color: '#16A34A' },
      areaStyle: { color: 'rgba(22,163,74,0.08)' },
    }],
  } as echarts.EChartsOption : null, [data])

  const columns: ColumnsType<{ department: string; total: number; coverage_rate: number; healthy_rate: number; attention_count: number; attention_rate: number; top_risk: string | null; sample_too_small: boolean }> = [
    { title: '部门', dataIndex: 'department', key: 'department', render: (value) => <b className="a-dep-name">{value}</b> },
    { title: '有效员工数', dataIndex: 'total', key: 'total', width: 100, align: 'center', render: (value) => `${value}人` },
    {
      title: '健康数据覆盖率', dataIndex: 'coverage_rate', key: 'coverage_rate', width: 170,
      render: (value: number, row) => row.sample_too_small ? <span className="a-sample-warn">样本量不足</span>
        : <span className="a-rate-cell"><Progress percent={value} size="small" strokeColor="#16A34A" /><em>{value}%</em></span>,
    },
    {
      title: '健康良好率', dataIndex: 'healthy_rate', key: 'healthy_rate', width: 170,
      render: (value: number, row) => row.sample_too_small ? <span className="a-sample-warn">样本量不足</span>
        : <span className="a-rate-cell"><Progress percent={value} size="small" strokeColor="#0EA5B7" /><em>{value}%</em></span>,
    },
    {
      title: '需关注人数', dataIndex: 'attention_count', key: 'attention_count', width: 110, align: 'center',
      render: (value: number) => value > 0 ? <Tag color="orange">{value}人</Tag> : <span className="a-none">{value}人</span>,
    },
    { title: '需关注率', dataIndex: 'attention_rate', key: 'attention_rate', width: 90, align: 'center', render: (value: number) => `${value}%` },
    { title: '主要风险', dataIndex: 'top_risk', key: 'top_risk', render: (value: string | null) => value ? <Tag color="red">{value}</Tag> : <span className="a-none">暂无</span> },
  ]

  if (loading) {
    return <section className="a-page employee-health-analytics-page">
      <div className="a-heading"><div><div className="eyebrow">EMPLOYEE HEALTH ANALYTICS</div><h2>员工健康分析</h2><p>基于员工健康档案、体检与风险评估的匿名聚合分析，帮助企业了解整体健康趋势。</p></div></div>
      <Card className="a-card"><Skeleton active paragraph={{ rows: 8 }} /></Card>
    </section>
  }

  const kpis = [
    { icon: <TeamOutlined />, label: '健康数据覆盖', value: overview?.covered_employees ?? 0, suffix: '人', note: `占企业员工 ${overview?.coverage_rate ?? 0}%`, color: '#16A34A' },
    { icon: <SafetyOutlined />, label: '当前需关注', value: overview?.attention_employees ?? 0, suffix: '人', note: `占有效评估员工 ${overview?.attention_rate ?? 0}%`, color: '#F59E0B' },
    { icon: <ExperimentOutlined />, label: '体检异常', value: overview?.abnormal_exam_employees ?? 0, suffix: '人', note: '存在至少1项需关注指标', color: '#EF4444' },
    { icon: <AppstoreOutlined />, label: '健康计划参与率', value: overview?.plan_participation_rate ?? 0, suffix: '%', note: `${overview?.plan_participants ?? 0} 人参与健康计划`, color: '#0EA5B7' },
  ]

  return <section className="a-page employee-health-analytics-page">
    <div className="a-heading">
      <div><div className="eyebrow">EMPLOYEE HEALTH ANALYTICS</div><h2>员工健康分析</h2><p>基于员工健康档案、体检与风险评估的匿名聚合分析，帮助企业了解整体健康趋势。</p></div>
      <div className="a-filters">
        <Select value={selectedDepartment ?? 'all'} style={{ width: 160 }} listHeight={300} placeholder="全部部门" popupClassName="a-dept-popup" showSearch={false} filterOption={false} options={[{ value: 'all', label: '全部部门' }, ...allDepartments.map(item => ({ value: item, label: item }))]} onChange={(value) => setSelectedDepartment(value === 'all' ? undefined : value)} />
        <Radio.Group size="middle" value={period} onChange={(event) => setPeriod(event.target.value)} options={[
          { label: '近7天', value: '7d' }, { label: '近30天', value: '30d' }, { label: '近90天', value: '90d' },
        ]} optionType="button" buttonStyle="solid" />
      </div>
    </div>

    <Row gutter={[16, 16]} className="a-kpi-row">
      {kpis.map((item) => (
        <Col xs={12} xl={6} key={item.label}>
          <Card className="a-kpi" style={{ borderLeft: `3px solid ${item.color}` }}>
            <div className="a-kpi-icon" style={{ color: item.color, background: `${item.color}14` }}>{item.icon}</div>
            <div className="a-kpi-body">
              <small>{item.label}</small>
              <b>{item.value}<em>{item.suffix}</em></b>
              <p>{item.note}</p>
            </div>
          </Card>
        </Col>
      ))}
    </Row>

    <Row gutter={[16, 16]}>
      <Col xs={24} lg={12}>
        <Card className="a-card" title="健康状态分布">
          {data?.health_distribution.length ? (
            <>
              <div ref={distributionRef} className="a-chart a-chart-donut" />
              <div className="a-distribution-list">
                {data.health_distribution.map(item => (
                  <div className="a-distribution-item" key={item.level}>
                    <span className="a-dot" style={{ background: LEVEL_COLOR[item.level] ?? '#94A3B8' }} /><span className="a-distribution-name">{item.label}</span>
                    <span className="a-distribution-percent">{item.percent}%</span><span className="a-distribution-count">{item.count}人</span>
                  </div>
                ))}
              </div>
            </>
          ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无健康风险数据" />}
        </Card>
      </Col>
      <Col xs={24} lg={12}>
        <Card className="a-card" title="主要风险类型">
          {data?.risk_ranking.length ? (
            <div className="a-risk-list">
              {data.risk_ranking.map((item, index) => (
                <div className="a-risk-item" key={item.risk_type}>
                  <span className="a-risk-rank">{index + 1}</span>
                  <span className="a-risk-name">{item.label}</span>
                  <Progress percent={Math.min(item.percent, 100)} showInfo={false} strokeColor="#16A34A" size="small" />
                  <span className="a-risk-meta">{item.count}人 {item.percent}%</span>
                </div>
              ))}
            </div>
          ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无风险数据" />}
        </Card>
      </Col>
    </Row>

    <Card className="a-card" title="部门健康状况" style={{ marginTop: 16 }}>
      {data?.department_stats.length
        ? <Table rowKey="department" columns={columns} dataSource={data.department_stats} pagination={false} size="middle" />
        : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无部门数据" />}
    </Card>

    <Card className="a-card" title="企业健康趋势（需关注员工比例）" style={{ marginTop: 16 }}>
      {data?.risk_trend.length
        ? <div ref={trendRef} className="a-chart" style={{ height: 280 }} />
        : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无趋势数据" />}
    </Card>
  </section>
}
