import {Card,Empty,Tag} from 'antd'
import type {HealthSummary} from '../../api/healthSummary'
import {adaptHealthSummary} from './AIHealthSummary/adapter'
import {HealthStatusCard} from './AIHealthSummary/HealthStatusCard'
import {HealthMetricCard} from './AIHealthSummary/HealthMetricCard'
import {HealthAttentionCard} from './AIHealthSummary/HealthAttentionCard'
import {HealthSuggestionList} from './AIHealthSummary/HealthSuggestionList'
import './AIHealthSummary/summary.css'
export function AIHealthSummaryCard({summary}:{summary:HealthSummary|null}){const view=adaptHealthSummary(summary);return <Card className="profile-card ai-summary-card" title={<div className="summary-title"><span>AI 健康摘要</span><div><Tag color="green">AI Analysis</Tag>{view&&<small>更新时间：{view.updatedAt}</small>}</div></div>}>{view?<><HealthStatusCard text={view.overall}/>{view.metrics.length>0&&<section><h4>健康发现</h4><div className="summary-metrics">{view.metrics.map(metric=><HealthMetricCard key={metric.label} metric={metric}/>)}</div></section>}<HealthAttentionCard items={view.attention}/><HealthSuggestionList items={view.suggestions}/></>:<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="正在生成健康摘要"/>}</Card>}
