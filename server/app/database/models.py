import asyncio
from datetime import datetime
from pathlib import Path

from sqlalchemy import BigInteger, String, Integer, DateTime, Boolean, func
from sqlalchemy.orm import DeclarativeBase, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, AsyncAttrs, async_sessionmaker


# Получаем абсолютный путь к текущему файлу
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "db.sqlite3"  # или "database/db.sqlite3", если нужно

# Создаем путь к базе данных
engine = create_async_engine(
    url=f"sqlite+aiosqlite:///{DATABASE_PATH}", future=True, echo=False
)
async_session = async_sessionmaker(engine)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    telegram_id = mapped_column(BigInteger, primary_key=True)  # Telegram ID
    user_name = mapped_column(String(255))
    tariff = mapped_column(String(20), default="free")  # free, gift, subscription, VIP
    tarot_bonus = mapped_column(Integer, default=3)  # +1 за каждого друга
    card_day = mapped_column(Integer, default=1)
    referrar_by = mapped_column(BigInteger, nullable=True)
    is_recurring = mapped_column(Boolean, nullable=True)


class Subscription(Base):
    __tablename__ = "subscriptions"

    telegram_id = mapped_column(BigInteger, primary_key=True)  # Telegram ID
    tariff = mapped_column(String(20), default="free")  # free, gift, subscription, VIP,
    is_recurring = mapped_column(Boolean, nullable=True)
    email = mapped_column(String(100), nullable=True)
    start_date = mapped_column(DateTime, default=func.datetime("now", "localtime"))
    end_date = mapped_column(DateTime)
    payment_attempts = mapped_column(Integer, default=0)
    payment_method_id = mapped_column(String(50), nullable=True)
    subscription_id = mapped_column(
        String(100), nullable=True
    )  # ID подписки в CloudPayments


class GiftCode(Base):
    __tablename__ = "gift_codes"

    id = mapped_column(Integer, primary_key=True)
    code = mapped_column(
        String, unique=True, nullable=False
    )  # Уникальный код "gift-abc1232"
    days = mapped_column(Integer, nullable=False)  # дней действует
    valid_before = mapped_column(DateTime)


async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(async_main())
