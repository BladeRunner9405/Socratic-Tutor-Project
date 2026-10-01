from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config.config import settings

# Определение базового класса для ORM-моделей
Base = declarative_base()

# Создание движка БД
engine = create_engine(
    settings.get_db_url(),
    connect_args={"check_same_thread": False} if "sqlite" in settings.get_db_url() else {},
    echo=False
)

# Фабрика сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Инициализация базы данных и создание всех таблиц"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Генератор сессии БД для изолированного использования"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()