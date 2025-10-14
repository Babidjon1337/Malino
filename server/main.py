import calendar  # Добавлен импорт
import logging
import traceback
import asyncio
import json
import hashlib
import hmac
import base64
from datetime import date, datetime, timedelta  # Добавлены datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import (
    BOT_TOKEN,
    WEBHOOK_URL,
    WEBHOOK_SECRET,
    PORT,
)

from app.services.async_task import TaskScheduler
from app.handlers import router, webapp_tarot
import app.database.requests as rq
import app.keyboards as kb
from app.services.yookassa_service import yookassa_service

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация CloudPayments сервиса


bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Очищаем роутер от предыдущих подключений
router._parent_router = None
dp.include_router(router)

# Создаем планировщики
task_scheduler = TaskScheduler(bot)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    try:
        task_scheduler.start()
        # Устанавливаем webhook
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await bot.set_webhook(
            url=webhook_url, secret_token=WEBHOOK_SECRET, drop_pending_updates=True
        )
        logger.info(f"Вебхук установлен: {webhook_url}")

        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"Бот запущен: @{bot_info.username}")

    except Exception as e:
        logger.error(f"Ошибка при установке вебхука: {e}")
        raise

    yield

    # Shutdown
    try:
        task_scheduler.shutdown()
        await bot.delete_webhook()
        await bot.session.close()
        logger.info("Вебхук удален, сессия бота закрыта")
    except Exception as e:
        logger.error(f"Ошибка при завершении работы: {e}")


app = FastAPI(lifespan=lifespan)

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    # allow_origins=[
    #     ["https://malinaezo.ru", "https://www.malinaezo.ru"]
    # ],  # В production лучше указать конкретные origins
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Bot is running!"}


@app.post("/webhook")
async def webhook(request: Request):
    # Проверяем секретный токен
    if WEBHOOK_SECRET:
        secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret_token != WEBHOOK_SECRET:
            return {"error": "Forbidden"}

    body = await request.json()
    update = Update(**body)
    await dp.feed_update(bot, update)

    return {"status": "ok"}


@app.post("/api/mini-app", response_class=JSONResponse)
async def mini_app_data(request: Request) -> JSONResponse:
    """Endpoint для приема данных от Telegram Mini App"""
    try:
        print("=== Получен запрос от Mini App ===")

        data: Request = await request.json()
        # Извлекаем информацию о пользователе:
        # выбранных картах и вопросе
        user_id = data.get("user_id")
        cards = data.get("cards", [])
        question = (str(data.get("question", ""))).replace("%20", " ")
        message_id = data.get("message_id", "")  # Извлекаем ID сообщения для удаления

        if user_id and cards and question and message_id:
            # Формируем сообщение с выпавшими картами
            cards_list = ", ".join([card.get("name", "") for card in cards])
            print(
                f"Пользователь: {user_id}.\nКарты: {cards_list}.\nВопрос: {question}.\nID сообщения: {message_id}.\n"
            )

            # Запускаем функцию обработки в фоне, не дожидаясь её завершения

            asyncio.create_task(
                webapp_tarot(bot, user_id, cards_list, question, int(message_id))
            )

            return {"status": "ok", "message": "Processing started"}
        else:
            error_msg = "Отсутствуют данные пользователя, карт или вопроса"
            print(f"Ошибка: {error_msg}")
            return {"status": "error", "message": error_msg}

    except Exception as e:
        print(f"Ошибка в mini_app_data: {e}")

        print(traceback.format_exc())
        return {"status": "error", "message": str(e)}


@app.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    """
    Обработчик webhook уведомлений от YooKassa.
    """
    try:
        # Получаем тело запроса и подпись для проверки
        request_body = await request.body()

        # Парсим JSON данные из тела запроса
        data = json.loads(request_body.decode("utf-8"))

        # Извлекаем тип события и данные платежа
        event_type = data.get("event")
        payment_data = data.get("object", {})
        payment_id = payment_data.get("id")
        payment_status = payment_data.get("status")
        metadata = payment_data.get("metadata", {})
        amount = payment_data.get("amount").get("value")
        print(amount)
        # Извлекаем metadata из платежа
        telegram_id = metadata.get("user_id")
        massage_id = metadata.get("message_id")
        email = metadata.get("email")

        # Извлекаем payment_method_id из данных платежа
        payment_method_id = payment_data.get("payment_method", {}).get("id")

        logger.info(
            f"Обработка события: {event_type}, платеж: {payment_id}, статус: {payment_status}"
        )

        if event_type == "payment.succeeded":
            # Обрабатываем успешный платеж
            if telegram_id and payment_method_id:
                if massage_id:
                    await rq.create_subscription(
                        telegram_id,
                        payment_method_id,
                        amount,
                        payment_id,
                        email,
                    )
                    try:
                        logger.info(
                            f"Пользователя {telegram_id} оплатил подписку, message_id: {massage_id}"
                        )
                        today = datetime.now()
                        _, days_in_month = calendar.monthrange(
                            today.year,
                            today.month,
                        )
                        if amount == "799.00":
                            end_date = (today + timedelta(days=days_in_month)).strftime(
                                "%d.%m.%Y"
                            )
                        else:
                            end_date = (today + timedelta(days=1)).strftime("%d.%m.%Y")

                        await bot.edit_message_text(
                            chat_id=telegram_id,
                            message_id=massage_id,
                            text=(
                                f"✨ <b>Ваша подписка активна!</b>\n\n"
                                f"📅 Действует до: {end_date}\n"
                                f"🔄 Автопродление: Включено ✅\n\n"
                                f"Вы можете отменить автопродление в любой момент."
                            ),
                            reply_markup=kb.btn_management_subscription,  # Убедитесь, что kb импортирован
                        )
                    except Exception as bot_error:
                        logger.error(
                            f"Failed to edit/send confirmation message for user {telegram_id}: {bot_error}"
                        )
                else:
                    logger.info(
                        f"massage_id не предоставлен в metadata, telegram_id: {telegram_id} юкасса списала деньги за подписку"
                    )
                    await rq.create_subscription(
                        telegram_id,
                        payment_method_id,
                        amount,
                        payment_id,
                        email,
                    )

                logger.info(
                    f"Успешный платеж {payment_id} для пользователя {telegram_id} обработан, подписка создана"
                )

            else:
                logger.warning(
                    f"Недостаточно данных для обработки платежа: telegram_id={telegram_id}, payment_method_id={payment_method_id}"
                )

        elif event_type == "payment.waiting_for_capture":
            # Платеж ожидает подтверждения (например, для ручной проверки)
            logger.info(f"Платеж ожидает подтверждения: {payment_id}")
            # ЗАПИСЬ В БАЗУ ДАННЫХ: можно обновить статус платежа в базе, если нужно

        elif event_type == "payment.canceled":
            # Платеж отменен
            logger.info(f"Платеж отменен: {payment_id}")
            await rq.update_cansel_subscription(telegram_id)

        else:
            logger.info(f"Получено неизвестное событие {event_type}: {payment_id}")

        return JSONResponse(status_code=200, content={"status": "processed"})

    except Exception as e:
        logger.error(f"Ошибка обработки вебхука YooKassa: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
