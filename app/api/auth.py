"""
احراز هویت ساده با API key ثابت — برای یک ابزار مدیریتی شخصی کافی است.

⚠️ اگر این API را به اینترنت عمومی expose می‌کنید (نه فقط localhost/شبکه‌ی داخلی)،
حتماً پشت HTTPS بگذارید — یک API key ساده به‌تنهایی بدون TLS کافی نیست (قابل شنود است).
"""
from fastapi import Header, HTTPException, status

from app.config import settings


async def verify_api_key(x_api_key: str = Header(...)) -> None:
    if x_api_key != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key نامعتبر است")
