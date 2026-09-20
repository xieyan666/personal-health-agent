"""Reset the two local development accounts with deterministic roles."""
import asyncio
from sqlalchemy import delete, select
from backend.app.auth.security import hash_password
from backend.app.core.database import AsyncSessionFactory
from backend.app.models import Company, Employee, User

async def main():
    async with AsyncSessionFactory() as session:
        old_users = (await session.scalars(select(User).where(User.username.in_(["employee001", "admin001"])))).all()
        old_ids = [u.id for u in old_users]
        if old_ids:
            await session.execute(delete(Employee).where(Employee.user_id.in_(old_ids)))
            await session.execute(delete(User).where(User.id.in_(old_ids)))
        company = await session.scalar(select(Company).where(Company.code == "local-company"))
        if company is None:
            company = Company(name="稷生科技有限公司", code="local-company")
            session.add(company)
            await session.flush()
        password_hash = hash_password("123456")
        employee = User(username="employee001", display_name="测试员工", auth_source="local", password_hash=password_hash, role="employee", company_id=str(company.id), department="研发部")
        admin = User(username="admin001", display_name="系统管理员", auth_source="local", password_hash=password_hash, role="admin", company_id=str(company.id))
        session.add_all([employee, admin])
        await session.flush()
        session.add(Employee(user_id=employee.id, company_id=company.id, employee_no="EMP001", name="测试员工", department="研发部", position="算法工程师"))
        await session.commit()

if __name__ == "__main__":
    asyncio.run(main())
