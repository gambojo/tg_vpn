import db.models  # регистрирует все модели в Base.metadata
from config import settings
from tg_core.alembic_env import run

run(settings.DATABASE_URL)
