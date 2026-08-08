"""
Admin API — رابط جایگزین/مکمل دستورات بات برای مدیریت منابع و دیدن آمار.

اجرا: uvicorn app.api.main:app --host 0.0.0.0 --port 8000
(یا از طریق docker-compose، سرویس api)

تصمیم معماری: این API فقط عملیات مدیریتی (منابع، مشاهده‌ی آیتم‌ها/آمار) را پوشش
می‌دهد، نه تأیید/رد پست‌ها — آن جریان عمداً فقط از طریق تلگرام (دکمه‌های inline)
باقی می‌ماند چون تصمیم‌گیری real-time و تعاملی است و تلگرام برای آن UX بهتری دارد.

تست‌شده روی Postgres واقعی (۱۳ سناریو: auth، CRUD منابع، فیلتر آیتم‌ها، serialization
کامل evaluation، digest خالی) — نگاه کنید به تاریخچه‌ی توسعه برای جزئیات.
"""
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.auth import verify_api_key
from app.api.schemas import EvaluationOut, ItemOut, SourceCreate, SourceOut, SourceUpdate
from app.db.models import ItemStatus, RawItem, Source
from app.db.session import AsyncSessionLocal
from app.services import source_admin
from app.services.digest import build_daily_digest_text

app = FastAPI(title="Lornux Admin API", version="1.0.0")


def _source_to_out(s: Source) -> SourceOut:
    return SourceOut(
        id=source_admin.short_id(s),
        name=s.name,
        url=s.url,
        source_type=s.source_type.value,
        rating=s.rating,
        is_active=s.is_active,
        is_blacklisted=s.is_blacklisted,
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/sources", response_model=list[SourceOut], dependencies=[Depends(verify_api_key)])
async def list_sources_endpoint() -> list[SourceOut]:
    async with AsyncSessionLocal() as session:
        sources = await source_admin.list_sources(session)
    return [_source_to_out(s) for s in sources]


@app.post("/sources", response_model=SourceOut, dependencies=[Depends(verify_api_key)])
async def create_source_endpoint(payload: SourceCreate) -> SourceOut:
    async with AsyncSessionLocal() as session:
        try:
            source = await source_admin.add_source(session, url=payload.url, name=payload.name, rating=payload.rating)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        await session.commit()
    return _source_to_out(source)


@app.patch("/sources/{short_id}", response_model=SourceOut, dependencies=[Depends(verify_api_key)])
async def update_source_endpoint(short_id: str, payload: SourceUpdate) -> SourceOut:
    async with AsyncSessionLocal() as session:
        try:
            source = await source_admin.resolve_source(session, short_id)
            if payload.is_active is not None:
                source = await source_admin.set_active(session, short_id, payload.is_active)
            if payload.is_blacklisted is not None:
                source = await source_admin.set_blacklisted(session, short_id, payload.is_blacklisted)
            if payload.rating is not None:
                source = await source_admin.set_rating(session, short_id, payload.rating)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        await session.commit()
    return _source_to_out(source)


@app.get("/items", response_model=list[ItemOut], dependencies=[Depends(verify_api_key)])
async def list_items_endpoint(status_filter: str | None = None, limit: int = 50) -> list[ItemOut]:
    async with AsyncSessionLocal() as session:
        stmt = (
            select(RawItem)
            .options(selectinload(RawItem.source), selectinload(RawItem.evaluations))
            .order_by(RawItem.fetched_at.desc())
            .limit(limit)
        )
        if status_filter:
            try:
                status_enum = ItemStatus(status_filter)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"وضعیت نامعتبر: {status_filter}")
            stmt = stmt.where(RawItem.status == status_enum)

        result = await session.execute(stmt)
        items = result.scalars().unique().all()

    out: list[ItemOut] = []
    for item in items:
        latest_eval = item.evaluations[-1] if item.evaluations else None
        out.append(ItemOut(
            id=str(item.id),
            title=item.title,
            url=item.url,
            status=item.status.value,
            source_name=item.source.name,
            published_at=item.published_at,
            latest_evaluation=EvaluationOut(
                score_overall=latest_eval.score_overall,
                content_type=latest_eval.content_type.value if latest_eval.content_type else None,
                hashtag=latest_eval.hashtag,
                worth_posting=latest_eval.worth_posting,
                rewritten_post=latest_eval.rewritten_post,
                llm_provider=latest_eval.llm_provider.value,
            ) if latest_eval else None,
        ))
    return out


@app.get("/digest/today", dependencies=[Depends(verify_api_key)])
async def digest_today_endpoint() -> dict:
    async with AsyncSessionLocal() as session:
        text = await build_daily_digest_text(session)
    return {"digest_html": text}
