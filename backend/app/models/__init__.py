"""Persistence models and their shared declarative foundation."""

from backend.app.models.agent import Agent
from backend.app.models.audit import AuditLog
from backend.app.models.base import Base, TimestampMixin
from backend.app.models.conversation import Conversation, Message
from backend.app.models.chunk import DocumentChunk
from backend.app.models.execution import AgentRun
from backend.app.models.knowledge import Document, KnowledgeBase
from backend.app.models.model import ModelConfig, ModelProvider
from backend.app.models.tool import Tool
from backend.app.models.user import User
from backend.app.models.rbac import Company, Employee, Permission, Role, RolePermission
from backend.app.models.organization import Department, Position
from backend.app.models.health_profile import HealthProfile
from backend.app.models.health_records import SleepRecord, ExerciseRecord, HeartRateRecord
from backend.app.models.risk_assessment import RiskAssessment
from backend.app.models.risk_case import RiskCase, RiskCaseAction, RISK_CASE_STATUS, RISK_CASE_ACTIONS
from backend.app.models.health_summary import HealthSummary
from backend.app.models.health_risk_score import HealthRiskScore
from backend.app.models.health_check_report import HealthCheckIndicator, HealthCheckReport
from backend.app.models.health_report_analysis import HealthReportAnalysis
from backend.app.models.health_plan import HealthPlan, HealthPlanTask
from backend.app.models.health_service import EmployeeHealthBenefit, HealthActivity, HealthActivityParticipant, HealthService, HealthServiceBooking
from backend.app.models.mental_health import MentalAssessment, MentalCheckin
from backend.app.models.notification import UserNotification, UserPreference
from backend.app.models.data_authorization import AgentApproval, DataConsent
from backend.app.models.system_monitor import RequestMetric, SystemAlert

__all__ = [
    "Agent",
    "AgentRun",
    "AuditLog",
    "Base",
    "Conversation",
    "Document",
    "DocumentChunk",
    "KnowledgeBase",
    "Message",
    "ModelConfig",
    "ModelProvider",
    "TimestampMixin",
    "Tool",
    "User",
    "Company", "Employee", "Permission", "Role", "RolePermission",
    "Department", "Position", "HealthProfile", "SleepRecord", "ExerciseRecord", "HeartRateRecord", "RiskAssessment", "RiskCase", "RiskCaseAction", "HealthSummary", "HealthRiskScore", "HealthCheckReport", "HealthCheckIndicator", "HealthReportAnalysis", "HealthPlan", "HealthPlanTask", "HealthService", "HealthActivity", "HealthActivityParticipant", "HealthServiceBooking", "EmployeeHealthBenefit", "MentalCheckin", "MentalAssessment", "UserNotification", "UserPreference", "DataConsent", "AgentApproval", "RequestMetric", "SystemAlert",
]
