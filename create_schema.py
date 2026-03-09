import tg_core.create_schema as core_schema
from db.models import User, Subscription, PreActionLog  # регистрирует модели в Base.metadata

if __name__ == "__main__":
    core_schema.run()
