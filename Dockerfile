FROM python:3.12-slim

# پکیج‌های سیستمی لازم برای psycopg2 و کامپایل بعضی وابستگی‌های torch/sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# نسخه‌ی CPU-only torch را نصب می‌کنیم — سبک‌تر است و GPU لازم نداریم
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

COPY . .

# مدل embedding را در زمان build دانلود می‌کنیم تا اولین اجرا کند نباشد
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"

CMD ["python", "-m", "app.bot.main"]
