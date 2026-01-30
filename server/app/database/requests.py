import re
import secrets
import string
import calendar
import logging
from sqlalchemy import select, update, delete, and_, or_, func
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from app.database.models import User, Subscription, GiftCode, Statistics, async_session


logger = logging.getLogger(__name__)


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

            elif args is not None and "gift" in args and await get_promo_code(args):
                # Регистрация с подарком подписки
                gift_days = (await get_promo_code(args)).days

                session.add(
                    User(
                        telegram_id=telegram_id,
                        user_name=user_name,
                        tariff="gift",
                    )
                )

                today = datetime.now()
                end_date = today + relativedelta(days=gift_days)

                session.add(
                    Subscription(
                        telegram_id=telegram_id,
                        tariff="gift",
                        end_date=end_date,
                    )
                )

                await session.execute(delete(GiftCode).where(GiftCode.code == args))

            elif args is not None and "special-link" in args:
                session.add(
                    User(
                        telegram_id=telegram_id,
                        user_name=user_name,
                        tariff="free(special)",
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

                        referrar_count = await session.scalar(
                            select(func.count()).where(User.referrar_by == referrer_id)
                        )

                        if user_ref.tariff == "free(special)" and referrar_count >= 3:
                            await session.execute(
                                update(User)
                                .where(User.telegram_id == referrer_id)
                                .values(tariff="VIP")
                            )

                except (ValueError, TypeError):
                    # Если args не является числом, создаем пользователя без рефера
                    session.add(
                        User(
                            telegram_id=telegram_id,
                            user_name=user_name,
                        )
                    )

        elif (
            user.tariff == "free"
            and args is not None
            and "gift" in args
            and await get_promo_code(args)
        ):

            gift_days = (await get_promo_code(args)).days

            today = datetime.now()
            end_date = today + relativedelta(days=gift_days)

            await session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(tariff="gift")
            )

            session.add(
                Subscription(
                    telegram_id=telegram_id,
                    tariff="gift",
                    end_date=end_date,
                )
            )

            await session.execute(delete(GiftCode).where(GiftCode.code == args))

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

        if not user.tariff.startswith("free"):
            return True

        elif user.tariff.startswith("free") and user.tarot_bonus > 0:
            return True

        await session.commit()
        return False


async def take_away_tarot(telegram_id: int) -> None:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))

        if user.tariff.startswith("free") and user.tarot_bonus > 0:
            user.tarot_bonus -= 1

        await session.commit()


async def caunt_taro(telegram_id: int) -> int:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        return user.tarot_bonus


async def check_subscription(telegram_id: int) -> dict:
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        if not user.tariff.startswith("free"):
            return True
        else:
            return False


async def check_user_subscription(telegram_id: int) -> Subscription | None:
    async with async_session() as session:
        subscription = await session.scalar(
            select(Subscription).where(Subscription.telegram_id == telegram_id)
        )
        if subscription and subscription.end_date > datetime.now():

            # Считаем разницу времени
            remaining_time = subscription.end_date - datetime.now()
            days_left = remaining_time.days

            # Если осталось меньше дня, но время еще есть, считаем как 1 день (или 0, на твое усмотрение)
            # Здесь логика: если есть подписка, то возвращаем True
            return {
                "is_active": True,
                "days_left": max(1, days_left),  # Защита от отрицательных чисел
            }

        # Если подписки нет в базе или срок истек
        return {"is_active": False, "days_left": 0}


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
        if amount == "99.00":
            end_date = today + timedelta(days=1)
        else:
            end_date = today + timedelta(days=days_in_month)

        tariff_str = f"subscription({amount.split('.')[0]})"

        if subscription:
            # Обновляем существующую подписку
            await session.execute(
                update(Subscription)
                .where(Subscription.telegram_id == telegram_id)
                .values(
                    tariff=tariff_str,
                    is_recurring=True,
                    payment_method_id=payment_method_id,
                    end_date=end_date,  # Подписка на 30 дней
                    payment_attempts=0,
                    subscription_id=subscription_id,
                    email=email,
                )
            )
        else:
            await update_statistic("purchased_subs")
            # Создаем новую подписку
            session.add(
                Subscription(
                    telegram_id=telegram_id,
                    tariff=tariff_str,
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


async def update_cansel_subscription(telegram_id: int) -> bool:
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
            await session.commit()
            return True

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
            return False


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
                        Subscription.tariff.like("subscription%"),
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
                        Subscription.tariff.like("subscription%"),
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
            select(func.count(User.telegram_id)).where(User.tariff == "subscription")
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
    tariffs: list = ["gift", "free", "subscription", "VIP", "free(special)"]
) -> list[User]:
    async with async_session() as session:
        return (
            (await session.execute(select(User).where(User.tariff.in_(tariffs))))
            .scalars()
            .all()
        )


async def get_all_promo_codes() -> list[GiftCode]:
    async with async_session() as session:
        return (await session.execute(select(GiftCode))).scalars().all()


async def get_promo_code(code) -> GiftCode:
    async with async_session() as session:
        return await session.scalar(select(GiftCode).where(GiftCode.code == code))


async def create_promo_code(days: str) -> dict:
    async with async_session() as session:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        valid_before = today + timedelta(days=3)

        random_part = "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(8)
        )

        session.add(
            GiftCode(
                code=f"gift-{random_part}",
                days=days,
                valid_before=valid_before,
            )
        )
        await session.commit()

        return {
            "code": f"gift-{random_part}",
            "days": days,
            "valid_before": valid_before,
        }


async def del_promo_code() -> None:
    async with async_session() as session:
        await session.execute(
            delete(GiftCode).where(GiftCode.valid_before <= datetime.now())
        )
        await session.commit()


# ================== Статистика =======================
async def add_statistics() -> None:
    """Добавляет запись статистики за текущий день."""
    async with async_session() as session:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        session.add(Statistics(date=today))
        await session.commit()


async def update_statistic(value: str) -> None:
    """Увеличивает счетчик checkout_initiated на 1 за текущий день."""
    async with async_session() as session:
        data_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        stats = await session.scalar(
            select(Statistics).where(Statistics.date == data_time)
        )

        if not stats:
            # Если статистика за сегодня отсутствует, создаем новую запись
            await add_statistics()

        column_obj = getattr(Statistics, value)

        await session.execute(
            update(Statistics)
            .where(Statistics.date == data_time)
            .values({value: column_obj + 1})  # Словарь: {"имя_колонки": выражение + 1}
        )

        await session.commit()


async def get_statistics_data():
    """
    Получает сырые данные из БД:
    1. Статистику за последние 7 дней.
    2. Все подписки (или последние N, если их много).
    """
    async with async_session() as session:
        data_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        stats = await session.scalar(
            select(Statistics).where(Statistics.date == data_time)
        )

        if not stats:
            # Если статистика за сегодня отсутствует, создаем новую запись
            await add_statistics()

        # Берем данные за 7 дней
        seven_days_ago = datetime.now() - timedelta(days=7)

        user_count_result = await session.execute(select(func.count(User.telegram_id)))
        count_user = user_count_result.scalar()

        subscription_count_result = await session.execute(
            select(func.count(User.telegram_id)).where(User.tariff == "subscription")
        )
        count_subscription = subscription_count_result.scalar()

        await session.execute(
            update(Statistics)
            .where(Statistics.date == data_time)
            .values(
                total_users=count_user,
                active_subs=count_subscription,
            )
        )
        await session.commit()

        # Запрос статистики (сортируем по дате, чтобы график был правильным)
        stats_result = await session.execute(
            select(Statistics)
            .where(Statistics.date >= seven_days_ago)
            .order_by(Statistics.date.asc())
        )
        stats = stats_result.scalars().all()

        # Запрос подписок (можно добавить лимит .limit(50))
        sub_result = await session.execute(select(Subscription))
        subs = sub_result.scalars().all()

        return stats, subs
