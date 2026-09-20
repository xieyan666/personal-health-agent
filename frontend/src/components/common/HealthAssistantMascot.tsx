import { useNavigate } from 'react-router-dom'
import mascotImage from '../../assets/health-assistant-mascot.png'
import './health-assistant-mascot.css'

export function HealthAssistantMascot() {
  const navigate = useNavigate()

  return (
    <button
      className="health-assistant-mascot"
      type="button"
      aria-label="打开 AI 健康助手"
      onClick={() => navigate('/employee/assistant')}
      title="打开 AI 健康助手"
    >
      <span className="mascot-hint">健康助手在线</span>
      <img className="mascot-image" src={mascotImage} alt="运动健康助手" />
    </button>
  )
}
