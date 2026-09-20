from uuid import UUID, uuid4
from typing import Optional
from pydantic import BaseModel, ConfigDict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import and_, case, delete, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from backend.app.api.deps import get_db
from backend.app.auth.jwt import require_role
from backend.app.auth.security import hash_password
from backend.app.models import Company, Employee, User, Department, Position
from backend.app.utils.pinyin import name_pinyin

router = APIRouter(prefix="/users", tags=["rbac-users"])
logger = logging.getLogger(__name__)
admin = require_role("admin", "company_admin", "system_admin")

class EmployeePayload(BaseModel):
    username: str; password: Optional[str] = None; name: str; employee_no: Optional[str] = None
    company_id: Optional[UUID] = None; department: Optional[str] = None; position: Optional[str] = None
    phone: Optional[str] = None; email: Optional[str] = None; role: str = "employee"
    department_id: Optional[UUID] = None; position_id: Optional[UUID] = None
    model_config = ConfigDict(extra="forbid")

class RolePayload(BaseModel):
    role: str

class StatusPayload(BaseModel):
    status: Optional[str] = None
    # Keep accepting the legacy field while clients migrate to ``status``.
    role: Optional[str] = None

class ResetPasswordPayload(BaseModel):
    password: str = "123456"

def output(user: User, employee: Employee | None = None):
    return {"id": str(user.id), "username": user.username, "name": employee.name if employee else user.display_name,
            "employee_no": employee.employee_no if employee else None, "department": employee.department if employee else user.department,
            "position": employee.position if employee else None, "department_id": str(user.department_id) if user.department_id else None,
            "position_id": str(user.position_id) if user.position_id else None, "phone": employee.phone if employee else user.phone,
            "email": employee.email if employee else user.email, "role": user.role, "status": user.status,
            "company_id": str(employee.company_id) if employee else user.company_id}


def _employee_search_statement(keyword: str | None):
    """Build the shared, relevance-ranked employee search query.

    The table and the type-ahead dropdown intentionally use this one query so
    that a suggestion always represents the same result set as the table.
    ``name_pinyin`` stores both the full pinyin and a space-separated initialism
    (for example ``xieyan xy``), so the second pinyin predicate targets the
    beginning of that initialism token.
    """
    stmt = (
        select(User, Employee)
        .outerjoin(Employee, Employee.user_id == User.id)
        # RAG and other system fixtures are real auth records, but are not
        # enterprise employees and must not appear in the HR management view.
        .where(not_(User.username.ilike("rag-%")))
    )
    if not keyword or not keyword.strip():
        return stmt.order_by(User.created_at.desc())

    value = keyword.strip()
    prefix = f"{value}%"
    contains = f"%{value}%"
    pinyin_initial_prefix = f"% {value}%"

    username_prefix = User.username.ilike(prefix)
    name_prefix = or_(User.display_name.ilike(prefix), Employee.name.ilike(prefix))
    pinyin_prefix = User.name_pinyin.ilike(prefix)
    # ``name_pinyin`` has the form "full-pinyin initials".  This only checks
    # the start of the initials token, rather than matching a random substring.
    initials_prefix = User.name_pinyin.ilike(pinyin_initial_prefix)

    if len(value) == 1:
        # One character is intentionally prefix-only to avoid broad matches,
        # e.g. "e" must not return xieyan or rag-* records.
        return stmt.where(or_(username_prefix, name_prefix, pinyin_prefix, initials_prefix)).order_by(
            case(
                (User.username.ilike(value), 0),
                (username_prefix, 1),
                (name_prefix, 2),
                (pinyin_prefix, 3),
                (initials_prefix, 4),
                else_=5,
            ),
            User.username.asc(),
        )

    exact_match = or_(
        User.username.ilike(value),
        User.display_name.ilike(value),
        Employee.name.ilike(value),
        User.name_pinyin.ilike(value),
    )
    contains_match = or_(
        User.username.ilike(contains),
        User.display_name.ilike(contains),
        Employee.name.ilike(contains),
        User.name_pinyin.ilike(contains),
        User.email.ilike(contains),
    )
    organization_match = or_(
        User.department.ilike(contains),
        Employee.department.ilike(contains),
        Employee.position.ilike(contains),
    )
    return stmt.where(
        or_(
            exact_match,
            username_prefix,
            name_prefix,
            pinyin_prefix,
            initials_prefix,
            contains_match,
            organization_match,
        )
    ).order_by(
        case(
            (exact_match, 0),
            (username_prefix, 1),
            (name_prefix, 2),
            (pinyin_prefix, 3),
            (initials_prefix, 4),
            (contains_match, 5),
            (organization_match, 6),
            else_=7,
        ),
        User.username.asc(),
    )

@router.get("", dependencies=[Depends(admin)])
async def list_managed_users(q: str | None = Query(default=None), keyword: str | None = Query(default=None), session: AsyncSession = Depends(get_db)):
    stmt = _employee_search_statement(q or keyword)
    rows = (await session.execute(stmt)).all()
    return [output(user, employee) for user, employee in rows]

@router.post("", status_code=201)
async def create_managed_user(payload: EmployeePayload, session: AsyncSession = Depends(get_db), current_user: User = Depends(admin)):
    if await session.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(409, "Username already exists")
    # Company admins create users only inside their own company; the client
    # does not need to know or submit the internal company id.
    company_id = payload.company_id
    if company_id is None and current_user.company_id:
        # Legacy auth rows store the company code (e.g. local-company), while
        # the RBAC Employee relation stores the Company's UUID.
        try:
            company_id = UUID(current_user.company_id)
        except ValueError:
            company = await session.scalar(select(Company).where(Company.code == current_user.company_id))
            company_id = company.id if company else None
    if not company_id:
        raise HTTPException(422, "管理员未绑定企业")
    if current_user.role == "company_admin" and str(company_id) != str(current_user.company_id):
        raise HTTPException(403, "不能为其他企业创建员工")
    if await session.get(Company, company_id) is None:
        raise HTTPException(404, "Company not found")
    department = await session.get(Department, payload.department_id) if payload.department_id else None
    position = await session.get(Position, payload.position_id) if payload.position_id else None
    if position and (not department or position.department_id != department.id): raise HTTPException(422, "职位不属于所选部门")
    department_name = department.name if department else payload.department
    position_name = position.name if position else payload.position
    user = User(id=uuid4(), username=payload.username, display_name=payload.name, name_pinyin=name_pinyin(payload.name), auth_source="local", password_hash=hash_password(payload.password or "ChangeMe123!"), role=payload.role, company_id=str(company_id), department=department_name, department_id=payload.department_id, position_id=payload.position_id, phone=payload.phone, email=payload.email)
    employee = Employee(user_id=user.id, company_id=company_id, employee_no=payload.employee_no or user.username, name=payload.name, department=department_name, position=position_name, phone=payload.phone, email=payload.email)
    try:
        # Flush the parent first; Employee has an FK to users.id and there is
        # intentionally no ORM relationship configured between these models.
        session.add(user)
        await session.flush()
        session.add(employee)
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("create managed user transaction failed")
        raise HTTPException(409, "员工账号或员工编号已存在")
    return output(user, employee)

@router.get("/departments")
async def departments(session: AsyncSession = Depends(get_db)):
    return [{"id": str(x.id), "name": x.name} for x in (await session.scalars(select(Department).order_by(Department.name))).all()]

@router.get("/positions")
async def positions(department_id: UUID, session: AsyncSession = Depends(get_db)):
    return [{"id": str(x.id), "name": x.name} for x in (await session.scalars(select(Position).where(Position.department_id == department_id).order_by(Position.name))).all()]

@router.get("/search", dependencies=[Depends(admin)])
async def search_users(keyword: str = Query(min_length=1), session: AsyncSession = Depends(get_db)):
    stmt = _employee_search_statement(keyword).limit(10)
    rows = (await session.execute(stmt)).all()
    return [{"id": str(user.id), "username": user.username, "display_name": employee.name if employee else user.display_name,
             "department": employee.department if employee else user.department, "position": employee.position if employee else None,
             "role": user.role} for user, employee in rows]

@router.put("/{user_id}", dependencies=[Depends(admin)])
async def update_managed_user(user_id: UUID, payload: EmployeePayload, session: AsyncSession = Depends(get_db)):
    user = await session.get(User, user_id); employee = await session.scalar(select(Employee).where(Employee.user_id == user_id))
    if not user or not employee: raise HTTPException(404, "Employee not found")
    department = await session.get(Department, payload.department_id) if payload.department_id else None
    position = await session.get(Position, payload.position_id) if payload.position_id else None
    if position and (not department or position.department_id != department.id): raise HTTPException(422, "职位不属于所选部门")
    department_name = department.name if department else payload.department; position_name = position.name if position else payload.position
    user.display_name = payload.name; user.name_pinyin = name_pinyin(payload.name); user.department = department_name; user.phone = payload.phone; user.email = payload.email
    user.department_id = payload.department_id; user.position_id = payload.position_id
    employee.name = payload.name; employee.employee_no = payload.employee_no or employee.employee_no; employee.department = department_name; employee.position = position_name; employee.phone = payload.phone; employee.email = payload.email
    await session.commit(); return output(user, employee)

@router.put("/{user_id}/role", dependencies=[Depends(admin)])
async def update_role(user_id: UUID, payload: RolePayload, session: AsyncSession = Depends(get_db)):
    if payload.role not in {"employee", "admin", "health_manager", "company_admin", "system_admin"}: raise HTTPException(422, "Invalid role")
    user = await session.get(User, user_id)
    if not user: raise HTTPException(404, "User not found")
    user.role = payload.role; await session.commit(); return {"id": str(user.id), "role": user.role}

@router.patch("/{user_id}/status", dependencies=[Depends(admin)])
async def update_status(user_id: UUID, payload: StatusPayload, session: AsyncSession = Depends(get_db)):
    next_status = payload.status or payload.role
    if next_status not in {"active", "disabled"}: raise HTTPException(422, "Invalid status")
    user = await session.get(User, user_id)
    if not user: raise HTTPException(404, "User not found")
    user.status = next_status; await session.commit(); return {"id": str(user.id), "status": user.status}

@router.delete("/{user_id}", status_code=204, dependencies=[Depends(admin)])
async def delete_managed_user(user_id: UUID, session: AsyncSession = Depends(get_db)):
    user = await session.get(User, user_id)
    if not user: raise HTTPException(404, "User not found")
    await session.execute(delete(Employee).where(Employee.user_id == user_id))
    await session.delete(user)
    try: await session.commit()
    except Exception:
        await session.rollback(); raise HTTPException(409, "用户仍被业务数据引用，无法删除")

@router.post("/{user_id}/reset-password", dependencies=[Depends(admin)])
async def reset_password(user_id: UUID, payload: ResetPasswordPayload, session: AsyncSession = Depends(get_db)):
    user = await session.get(User, user_id)
    if not user: raise HTTPException(404, "User not found")
    user.password_hash = hash_password(payload.password); await session.commit(); return {"status": "ok"}

@router.put("/{user_id}/reset-password", dependencies=[Depends(admin)])
async def reset_password_put(user_id: UUID, payload: ResetPasswordPayload, session: AsyncSession = Depends(get_db)):
    return await reset_password(user_id, payload, session)
