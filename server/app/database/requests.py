import re
import calendar
import logging
from sqlalchemy import select, update, delete, and_, or_, func
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from app.database.models import User, Subscription, async_session


logger = logging.getLogger(__name__)


def extract_months(gift: str) -> int:
    """Извлекает количество месяцев из gift-строки"""
    match = re.search(r"gift-(\d*)month", gift)
    if match:
        number_str = match.group(1)
        return int(number_str) if number_str else 1
    return 1


async def add_user(telegram_id: int, user_name: str, args: str | None) -> None:
    async with async_session() as session:
        # Проверяем, существует ли пользователь
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))

        if not user:
            # Обрабатываем разные сценарии args
            if args is None:
                # Обычная регистрация без рефера и без подарка
                session.add(
                    User(
                        telegram_id=telegram_id,
                        user_name=user_name,
                    )
                )

            elif "gift" in args:
                # Регистрация с подарком подписки
                gift_month = extract_months(args)

                session.add(
                    User(
                        telegram_id=telegram_id,
                        user_name=user_name,
                        tariff="gift",
                    )
                )

                today = datetime.now()
                end_date = today + relativedelta(months=gift_month)

                session.add(
                    Subscription(
                        telegram_id=telegram_id,
                        tariff="gift",
                        end_date=end_date,
                    )
                )

            else:
                # Реферальная регистрация
                try:
                    referrer_id = int(args)
                    session.add(
                        User(
                            telegram_id=telegram_id,
                            user_name=user_name,
                            referrar_by=referrer_id,
                        )
                    )

                    # Начисляем бонус рефереру
                    user_ref = await session.scalar(
                        select(User).where(User.telegram_id == referrer_id)
                    )
                    if user_ref:
                        await session.execute(
                            update(User)
                            .where(User.telegram_id == referrer_id)
                            .values(tarot_bonus=user_ref.tarot_bonus + 1)
                        )

                except (ValueError, TypeError):
                    # Если args не является числом, создаем пользователя без рефера
                    session.add(
                        User(
                            telegram_id=telegram_id,
                            user_name=user_name,
                        )
                    )

        await session.commit()


async def check_card_day(telegram_id: int) -> bool:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))

        if user.tariff == "VIP" or user.card_day > 0:

            if user.tariff != "VIP":
                user.card_day -= 1
            await session.commit()
            return True

        await session.commit()
        return False


async def check_tarot(telegram_id: int) -> bool:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))

        if user.tariff != "free":
            return True

        elif user.tariff == "free" and user.tarot_bonus > 0:
            return True

        await session.commit()
        return False


async def take_away_tarot(telegram_id: int) -> None:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))

        if user.tariff == "free" and user.tarot_bonus > 0:
            user.tarot_bonus -= 1

        await session.commit()


async def caunt_taro(telegram_id: int) -> int:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        return user.tarot_bonus


async def check_subscription(telegram_id: int) -> dict:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user.tariff != "free":
            return True
        else:
            return False


async def CardDayRese() -> None:
    """Сбрасывает card_day на 1 для всех пользователей."""
    async with async_session() as session:
        await session.execute(update(User).where(User.card_day <= 0).values(card_day=1))
        await session.commit()


# --- Обновленная функция для получения подписки ---
async def get_user(telegram_id: int):
    """
    Получает информацию о подписке пользователя.
    Возвращает объект Subscription, User или False, если подписки нет.
    """
    async with async_session() as session:
        return await session.scalar(select(User).where(User.telegram_id == telegram_id))


# Добавить функцию для создания подписки при успешной оплате
async def create_subscription(
    telegram_id: int,
    payment_method_id: str,
    amount: str,
    subscription_id: str = None,
    email: str = None,
) -> None:
    """Создает или обновляет подписку пользователя после успешной оплаты"""
    async with async_session() as session:
        # Проверяем существующую подписку
        subscription = await session.scalar(
            select(Subscription).where(Subscription.telegram_id == telegram_id)
        )
        today = datetime.now()
        _, days_in_month = calendar.monthrange(
            today.year,
            today.month,
        )
        if amount == "799.00":
            end_date = today + timedelta(days=days_in_month)
        else:
            end_date = today + timedelta(days=1)

        if subscription:
            # Обновляем существующую подписку
            await session.execute(
                update(Subscription)
                .where(Subscription.telegram_id == telegram_id)
                .values(
                    tariff="subscription",
                    is_recurring=True,
                    payment_method_id=payment_method_id,
                    end_date=end_date,  # Подписка на 30 дней
                    payment_attempts=0,
                    subscription_id=subscription_id,
                    email=email,
                )
            )
        else:
            # Создаем новую подписку
            session.add(
                Subscription(
                    telegram_id=telegram_id,
                    tariff="subscription",
                    is_recurring=True,
                    payment_method_id=payment_method_id,
                    end_date=end_date,
                    payment_attempts=0,
                    subscription_id=subscription_id,
                    email=email,
                )
            )

        # Также обновляем пользователя
        await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(tariff="subscription", is_recurring=True)
        )

        await session.commit()


async def activ_or_reactivate_subscription(telegram_id: int) -> None:
    """Активирует или реактивирует подписку пользователя"""
    async with async_session() as session:
        subscription = await session.scalar(
            select(User).where(User.telegram_id == telegram_id)
        )
        is_recurring = not subscription.is_recurring
        await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(is_recurring=is_recurring)
        )
        await session.execute(
            update(Subscription)
            .where(Subscription.telegram_id == telegram_id)
            .values(is_recurring=is_recurring)
        )
        await session.commit()


async def update_cansel_subscription(telegram_id: int) -> None:
    """Отменяет подписку пользователя если она payment_attempts >= 2"""
    async with async_session() as session:
        subscription = await session.scalar(
            select(Subscription).where(Subscription.telegram_id == telegram_id)
        )
        if subscription and subscription.payment_attempts >= 2:
            await session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(tariff="free", is_recurring=None)
            )
            await session.execute(
                delete(Subscription).where(Subscription.telegram_id == telegram_id)
            )
        elif subscription:
            await session.execute(
                update(Subscription)
                .where(Subscription.telegram_id == telegram_id)
                .values(
                    payment_attempts=subscription.payment_attempts + 1,
                    end_date=subscription.end_date + timedelta(days=1),
                )
            )
        await session.commit()


async def del_sub(telegram_id) -> None:
    async with async_session() as session:

        await session.execute(
            delete(Subscription).where(Subscription.telegram_id == telegram_id)
        )
        await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(
                tariff="free", is_recurring=None
            )  # Сбрасываем тариф и флаг рекуррентности
        )
        await session.commit()


async def update_recurring_subscription() -> list[Subscription]:
    """
    Создает задачу на оплату в определенное время.
    """
    async with async_session() as session:
        today_start = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        today_end = today_start + timedelta(days=1)

        expired_subscriptions = await session.execute(
            select(Subscription).where(
                and_(
                    Subscription.end_date >= today_start,
                    Subscription.end_date <= today_end,
                    or_(
                        Subscription.tariff == "subscription",
                        Subscription.tariff == "gift",
                    ),
                )
            )
        )

        return expired_subscriptions.scalars().all()


async def update_recurring_subscription_now() -> list[Subscription]:
    """
    Создает задачу на оплату в определенное время.
    """
    async with async_session() as session:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        expired_subscriptions = await session.execute(
            select(Subscription).where(
                and_(
                    Subscription.end_date >= today_start,
                    Subscription.end_date <= today_end,
                    or_(
                        Subscription.tariff == "subscription",
                        Subscription.tariff == "gift",
                    ),
                )
            )
        )

        return expired_subscriptions.scalars().all()


# Добавить функцию для получения подписки пользователя
async def get_user_subscription(telegram_id: int) -> Subscription:
    """Получает подписку пользователя"""
    async with async_session() as session:
        return await session.scalar(
            select(Subscription).where(Subscription.telegram_id == telegram_id)
        )


async def get_statistics() -> tuple[int, int]:
    """Получение статистики для Админа"""
    async with async_session() as session:
        # Количество всех пользователей
        user_count_result = await session.execute(select(func.count(User.telegram_id)))
        count_user = user_count_result.scalar()

        # Количество всех подписок
        subscription_count_result = await session.execute(
            select(func.count(Subscription.telegram_id)).where(
                Subscription.tariff == "subscription"
            )
        )
        count_subscription = subscription_count_result.scalar()

        return count_user, count_subscription


async def get_CardDay_10am() -> list[User]:
    async with async_session() as session:
        return (
            (await session.execute(select(User).where(User.card_day >= 1)))
            .scalars()
            .all()
        )


async def get_all_users(
    tariffs: list = ["gift", "free", "subscription", "subscription(799)", "VIP"]
) -> list[User]:
    async with async_session() as session:
        return (
            (await session.execute(select(User).where(User.tariff.in_(tariffs))))
            .scalars()
            .all()
        )
