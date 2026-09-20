export type ChatMessage = { id: string; role: 'user' | 'assistant'; content: string }

export const quickQuestions = [
  ['睡眠健康', '最近睡眠质量比较差，应该怎么改善？'],
  ['心理压力', '最近工作压力比较大怎么办？'],
  ['营养饮食', '帮我制定一份更健康的饮食建议。'],
  ['运动健身', '如何开始一份适合我的运动计划？'],
  ['体检报告', '解读我的最新体检报告。'],
]

export const starterQuestions = ['最近总是睡不好怎么办？', '帮我分析最近健康状态', '解读我的最新体检报告', '给我制定一个减脂计划', '最近工作压力比较大怎么办？']

export const history = [
  { id: 'sleep', title: '睡眠质量改善', time: '今天 09:42' },
  { id: 'checkup', title: '体检报告咨询', time: '昨天 16:20' },
  { id: 'pressure', title: '工作压力管理', time: '8月18日' },
]

export const mockAnswer = `## 综合分析
近期疲劳可能和睡眠不足有关。建议先从规律作息和降低睡前刺激开始，连续观察一周的状态变化。

### 发现
- 当前健康档案尚未完善，暂时无法进行个性化趋势比较
- 睡眠、运动和心率数据等待接入后端

### 健康建议
1. 尽量固定入睡和起床时间
2. 睡前 30 分钟减少电子设备使用
3. 白天安排 20～30 分钟轻度运动

### 需要关注
如果疲劳持续或明显影响日常工作，请及时寻求专业健康评估。`

export const mockContext = [
  ['年龄', '暂无数据', '用户填写'], ['BMI', '暂无数据', 'Health Profile'],
  ['睡眠', '暂无数据', 'Wearable'], ['运动', '暂无数据', 'Wearable'], ['心率', '暂无数据', 'Wearable'],
  ['最近体检', '暂无报告', '体检报告'], ['当前计划', '暂无计划', 'AI分析'],
]

export const mockAgents = [
  ['Health Supervisor', 'success', '已完成'], ['Sleep Agent', 'success', '已完成'], ['Risk Agent', 'success', '已完成'],
  ['Health Profile Tool', 'success', '已读取'], ['Knowledge RAG', 'success', '已检索'], ['Safety Guard', 'success', '已通过'],
]

export const mockPlan = ['23:30 前准备睡眠，睡前 30 分钟减少电子设备使用', '完成 30 分钟轻度运动，记录当天精力状态', '安排 10 分钟放松练习，避免临睡前处理工作', '保持固定起床时间，评估白天困倦程度', '选择清淡晚餐，睡前避免咖啡因', '复盘一周睡眠变化，调整入睡仪式', '总结改善效果，继续保持稳定作息']
