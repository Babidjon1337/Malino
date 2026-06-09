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
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))

        if not user:
            if args is None:
                session.add(
                    User(
                        telegram_id=telegram_id,
                        user_name=user_name,
                    )
                )

            elif args is not None and "gift" in args and await get_promo_code(args):
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

                # ВАЖНО: Удаляем ТОЛЬКО если это одноразовый купон (начинается на gift-)
                if args.startswith("gift-"):
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
                try:
                    referrer_id = int(args)
                    session.add(
                        User(
                            telegram_id=telegram_id,
                            user_name=user_name,
                            referrar_by=referrer_id,
                        )
                    )

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

            # ВАЖНО: Удаляем ТОЛЬКО если это одноразовый купон (начинается на gift-)
            if args.startswith("gift-"):
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
            remaining_time = subscription.end_date - datetime.now()
            days_left = remaining_time.days
            return {
                "is_active": True,
                "days_left": max(1, days_left),
            }
        return {"is_active": False, "days_left": 0}


async def CardDayRese() -> None:
    async with async_session() as session:
        await session.execute(update(User).where(User.card_day <= 0).values(card_day=1))
        await session.commit()


async def get_user(telegram_id: int):
    async with async_session() as session:
        return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def create_subscription(
    telegram_id: int,
    payment_method_id: str,
    amount: str,
    subscription_id: str = None,
    email: str = None,
) -> None:
    async with async_session() as session:
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
            await session.execute(
                update(Subscription)
                .where(Subscription.telegram_id == telegram_id)
                .values(
                    tariff=tariff_str,
                    is_recurring=True,
                    payment_method_id=payment_method_id,
                    end_date=end_date,
                    payment_attempts=0,
                    subscription_id=subscription_id,
                    email=email,
                )
            )
        else:
            await update_statistic("purchased_subs")
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

        await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(tariff="subscription", is_recurring=True)
        )

        await session.commit()


async def activ_or_reactivate_subscription(telegram_id: int) -> None:
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
            .values(tariff="free", is_recurring=None)
        )
        await session.commit()


async def update_recurring_subscription() -> list[Subscription]:
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


async def get_user_subscription(telegram_id: int) -> Subscription:
    async with async_session() as session:
        return await session.scalar(
            select(Subscription).where(Subscription.telegram_id == telegram_id)
        )


async def get_statistics() -> tuple[int, int]:
    async with async_session() as session:
        user_count_result = await session.execute(select(func.count(User.telegram_id)))
        count_user = user_count_result.scalar()

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


# ИЗМЕНЕНА: Добавлен аргумент validity_days
async def create_promo_code(
    days: int, is_multi: bool = False, validity_days: int = 3
) -> dict:
    async with async_session() as session:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Срок годности теперь зависит от переменной
        valid_before = today + timedelta(days=validity_days)

        random_part = "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(8)
        )

        prefix = "mgift-" if is_multi else "gift-"
        code_str = f"{prefix}{random_part}"

        session.add(
            GiftCode(
                code=code_str,
                days=days,
                valid_before=valid_before,
            )
        )
        await session.commit()

        return {
            "code": code_str,
            "days": days,
            "valid_before": valid_before,
        }


async def del_promo_code() -> None:
    async with async_session() as session:
        await session.execute(
            delete(GiftCode).where(GiftCode.valid_before <= datetime.now())
        )
        await session.commit()


async def add_statistics() -> None:
    async with async_session() as session:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        existing = await session.scalar(
            select(Statistics).where(Statistics.date == today - timedelta(days=1))
        )

        session.add(
            Statistics(
                date=today,
                active_users=existing.active_users if existing else 0,
            )
        )
        await session.commit()


async def update_statistic(value: str, count: int = None) -> None:
    async with async_session() as session:
        data_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        stats = await session.scalar(
            select(Statistics).where(Statistics.date == data_time)
        )

        if not stats:
            await add_statistics()

        column_obj = getattr(Statistics, value)

        await session.execute(
            update(Statistics)
            .where(Statistics.date == data_time)
            .values({value: column_obj + 1 if count is None else count})
        )

        await session.commit()


async def get_statistics_data():
    async with async_session() as session:
        data_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        stats = await session.scalar(
            select(Statistics).where(Statistics.date == data_time)
        )

        if not stats:
            await add_statistics()

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
                all_subs=count_subscription,
            )
        )
        await session.commit()

        stats_result = await session.execute(
            select(Statistics)
            .where(Statistics.date >= seven_days_ago)
            .order_by(Statistics.date.asc())
        )
        stats = stats_result.scalars().all()

        sub_result = await session.execute(select(Subscription))
        subs = sub_result.scalars().all()

        return stats, subs
