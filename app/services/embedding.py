"""
Embedding محلی و رایگان برای dedup — هیچ API call ندارد، هیچ هزینه‌ای ندارد.

مدل: intfloat/multilingual-e5-base (768 بعدی، فارسی را خوب پشتیبانی می‌کند).
نکته‌ی مهم درباره‌ی e5: این خانواده از مدل‌ها با پیشوند "query: " / "passage: " آموزش
دیده‌اند. چون اینجا کاربرد ما متقارن است (مقایسه‌ی سند با سند، نه query-to-document)،
از پیشوند "passage: " برای همه‌ی متن‌ها به‌طور یکسان استفاده می‌کنیم.

این کلاس عمداً sync است (sentence-transformers روی CPU blocking است). Celery worker از
آن در thread pool خودش استفاده می‌کند، پس مشکلی برای بلاک شدن event loop اصلی پیش نمی‌آید.
"""
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import settings

_PASSAGE_PREFIX = "passage: "


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    # lru_cache تضمین می‌کند مدل فقط یک‌بار در هر process لود شود (لود کردن آن کند است)
    return SentenceTransformer(settings.embedding_model_name)


def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    vector = model.encode(_PASSAGE_PREFIX + text, normalize_embeddings=True)
    return vector.tolist()
