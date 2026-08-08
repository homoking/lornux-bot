"""
Async DB session (asyncpg driver).

معماری: چون این پروژه FastAPI ندارد (بات با aiogram polling + Celery اجرا می‌شود)،
تنها یک نوع session (async) نگه می‌داریم. Celery task های sync با asyncio.run()
داخل خودشان به کوروتین‌های async وصل می‌شوند — این الگو در app/tasks/pipeline.py دیده می‌شود.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=10)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
