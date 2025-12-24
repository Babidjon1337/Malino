# app/services/async_task.py
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import app.database.requests as rq
from app.services.yookassa_service import yookassa_service
from app.handlers import card_day_10am


logger = logging.getLogger(__name__)


class TaskScheduler:
    def __init__(self, bot):
        self.scheduler = AsyncIOScheduler()
        self.bot = bot

    async def reset_card_day(self):
        """Сбрасывает card_day на 1 для всех пользователей ровно в 00:01"""
        try:
            await rq.CardDayRese()
            logger.info("Карты для обновлены.")

            await rq.del_promo_code()
            logger.info("Ненужные промокоды удалены")

        except Exception as e:
            logger.error(f"Error during card_day reset: {e}", exc_info=True)

    async def reminder_card_day(self):
        """Напиминаем всем пользователям о карте дня в 10:30"""

        users = await rq.get_CardDay_10am()
        logger.info(f"Напоминание Карте дня в 10:30, отправленно: {len(users)}")

        await card_day_10am(users, self.bot)

    async def reset_subscriptions(self):
        """Очистка просроченных подписок и планирование списаний на сегодня"""
        try:
            # Получаем подписки для обработки
            subscriptions = await rq.update_recurring_subscription()
            logger.info(
                f"Найдено рекуррентных подписок для планирования списаний: {len(subscriptions)}"
            )

            # Планируем списания для каждой подписки на время окончания подписки
            for sub in subscriptions:
                await self.schedule_payment(sub)

        except Exception as e:
            logger.error(f"Ошибка при обработке подписок: {e}", exc_info=True)

    async def reset_subscriptions_now(self):
        """Планирование списаний на сегодня при старте"""
        try:
            # Получаем подписки для обработки
            subscriptions = await rq.update_recurring_subscription_now()
            logger.info(
                f"Найдено рекуррентных подписок для планирования списаний: {len(subscriptions)}"
            )

            # Планируем списания для каждой подписки на время окончания подписки
            for sub in subscriptions:
                await self.schedule_payment(sub)

        except Exception as e:
            logger.error(f"Ошибка при обработке подписок: {e}", exc_info=True)

    async def schedule_payment(self, subscription):
        """Планирует списание для подписки на время ее окончания"""
        try:
            # Получаем время окончания подписки
            end_time = subscription.end_date

            # Добавляем задачу на списание в точное время окончания подписки
            # Создаем уникальный ID с timestampом чтобы избежать конфликтов
            job_id = f"subscription_payment_{subscription.telegram_id}_{end_time.timestamp()}"
            self.scheduler.add_job(
                self.process_subscription_payment,
                "date",
                run_date=end_time,
                args=[subscription.telegram_id],
                id=job_id,
                name=f"Списание подписки пользователя {subscription.telegram_id}",
                replace_existing=True,  # Заменяем существующую задачу если есть
            )

            logger.info(
                f"Запланировано списание для пользователя {subscription.telegram_id} на {end_time}"
            )

        except Exception as e:
            logger.error(
                f"Ошибка при планировании списания для подписки {subscription.telegram_id}: {e}",
                exc_info=True,
            )

    async def process_subscription_payment(self, telegram_id):
        """Обрабатывает списание подписки для конкретного пользователя"""
        try:
            logger.info(f"Начинаем обработку списания для пользователя {telegram_id}")
            user_subscription = await rq.get_user_subscription(telegram_id)

            tariff: str = user_subscription.tariff
            if "subscription" in tariff:
                amount_str = tariff.split("(")[1].split(")")[0]  # Получаем "300"
                amount = (
                    "300.00" if amount_str == "99" else f"{amount_str}.00"
                )  # Получаем "300.00"

            if user_subscription.is_recurring:
                await yookassa_service.create_recurring_payment(
                    user_id=telegram_id,
                    payment_method_id=user_subscription.payment_method_id,
                    email=user_subscription.email,
                    amount=amount,
                )
                logger.info(f"Списание выполнено для пользователя {telegram_id}")
            else:
                await rq.del_sub(telegram_id)
                logger.info(
                    f"Подписка уделена для пользователя {telegram_id} из-за изменения авто продления"
                )

        except Exception as e:
            logger.error(
                f"Ошибка при списании для пользователя {telegram_id}: {e}",
                exc_info=True,
            )

    def start(self):
        """Запускает планировщик"""

        # Сбрасываем ЕЖЕДНЕВНО ровно в 00:01
        self.scheduler.add_job(
            self.reset_card_day,
            "cron",
            hour=0,
            minute=0,
            second=1,
            id="card_day_and_subscriptions_reset_job",
            name="Обновления карт дня",
        )

        # Напиминаем всем пользователям о карте дня в 10:30
        self.scheduler.add_job(
            self.reminder_card_day,
            "cron",
            hour=10,
            minute=30,
            second=0,
            id="reminder_card_day_job_startup",
            name="Напиминаем всем пользователям о карте дня в 10:30",
        )

        # Запускаем планировщик подписок каждый день в 23:59
        self.scheduler.add_job(
            self.reset_subscriptions,
            "cron",
            hour=23,
            minute=59,
            second=0,
            id="subscriptions_reset_job",
            name="Планирование списаний подписок",
        )

        # Добавляем немедленный запуск при старте бота
        self.scheduler.add_job(
            self.reset_subscriptions_now,
            "date",
            run_date=None,  # Немедленный запуск
            id="subscriptions_reset_job_startup",
            name="Планирование списаний подписок (при старте)",
        )

        # Альтернатива для тестирования:
        # self.scheduler.add_job(
        #     self.reset_subscriptions,
        #     "interval",
        #     minutes=1,  # Каждые 1 минуты для теста
        #     id="subscriptions_reset_job",
        #     name="Планирование списаний подписок (TEST)",
        # )

        self.scheduler.start()
        logger.info("TaskScheduler начал работу.")

    def shutdown(self):
        """Останавливает планировщик"""
        self.scheduler.shutdown()
        logger.info("TaskScheduler прекратил работу.")
