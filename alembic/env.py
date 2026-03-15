import db.models  # регистрирует все модели в Base.metadata
from config import settings
from tgbotcore.alembic_env import run

run(settings.DATABASE_URL)
