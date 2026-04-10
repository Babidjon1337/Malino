import calendar  # Добавлен импорт
import logging
import re
import traceback
import asyncio
import json
from datetime import datetime, timedelta  # Добавлены datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from app.services.async_task import TaskScheduler
from app.services.yookassa_service import yookassa_service
from app.handlers import router, webapp_tarot
from app.admin_handler import admin_router
from app.database.models import async_main
import app.database.requests as rq
import app.keyboards as kb

from config import (
    BOT_TOKEN,
    WEBHOOK_URL,  # Можно будет убрать из конфига позже, он больше не нужен
    WEBHOOK_SECRET,
    PORT,
    PROXY_URL,
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота с голландским прокси
bot = Bot(
    token=BOT_TOKEN,
    session=AiohttpSession(proxy=PROXY_URL),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

# Очищаем роутер от предыдущих подключений
router._parent_router = None
admin_router._parent_router = None
dp.include_routers(router, admin_router)

# Создаем планировщики
task_scheduler = TaskScheduler(bot)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    polling_task = None

    # Startup
    try:
        task_scheduler.start()
        await async_main()  # Инициализация базы данных

        # =================================================================
        # ВЫБОР РЕЖИМА РАБОТЫ ТЕЛЕГРАМ БОТА (ВЕБХУК ИЛИ ПОЛЛИНГ)
        # =================================================================

        # --- ВАРИАНТ 1: WEBHOOK (Закомментирован) ---
        # Раскомментируйте эти строки, чтобы вернуть вебхуки:
        # webhook_url = f"{WEBHOOK_URL}/webhook"
        # await bot.set_webhook(
        #     url=webhook_url, secret_token=WEBHOOK_SECRET, drop_pending_updates=True
        # )
        # logger.info(f"Вебхук установлен: {webhook_url}")

        # --- ВАРИАНТ 2: LONG POLLING (Активен сейчас) ---
        # Закомментируйте эти строки, если переходите обратно на вебхуки:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Вебхук Telegram удален. Переходим на Long Polling.")
        polling_task = asyncio.create_task(dp.start_polling(bot))
        # -----------------------------------------------------------------

        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"Бот запущен: @{bot_info.username}")

    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")
        raise

    yield  # В этот момент FastAPI начинает принимать запросы от ЮKassa и Mini App

    # Shutdown
    try:
        task_scheduler.shutdown()

        # --- ВАРИАНТ 1: WEBHOOK (Закомментирован) ---
        # Раскомментировать, если возвращаетесь на вебхуки:
        # await bot.delete_webhook()

        # --- ВАРИАНТ 2: LONG POLLING (Активен сейчас) ---
        # Закомментировать, если возвращаетесь на вебхуки:
        if polling_task:
            polling_task.cancel()

        await bot.session.close()
        logger.info("Сессия бота закрыта")
    except Exception as e:
        logger.error(f"Ошибка при завершении работы: {e}")


app = FastAPI(lifespan=lifespan)

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Bot API and YooKassa webhook listener are running!"}


# =====================================================================
# РОУТ ДЛЯ TELEGRAM ВЕБХУКА (Возвращен)
# Если включен Polling, этот роут безопасно простаивает.
# Если вы переключитесь на Вебхук в lifespan, он снова начнет работать.
# =====================================================================
@app.post("/webhook", tags=["Bot 🤖"])
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


@app.post("/api/mini-app", tags=["Taro 🃏"], response_class=JSONResponse)
async def mini_app_data(request: Request) -> JSONResponse:
    """Endpoint для приема данных от Telegram Mini App"""
    try:
        print("=== Получен запрос от Mini App ===")
        await rq.update_statistic("requests_tarot")

        data: Request = await request.json()
        # Извлекаем информацию о пользователе:
        # выбранных картах и вопросе
        user_id = data.get("user_id")
        cards = data.get("cards", [])

        # question = (str(data.get("question", ""))).replace("%20", " ")

        message_id = data.get("message_id", "")  # Извлекаем ID сообщения для удаления

        if user_id and cards and message_id:
            # Формируем сообщение с выпавшими картами
            cards_list = ", ".join([card.get("name", "") for card in cards])

            # Запускаем функцию обработки в фоне, не дожидаясь её завершения
            asyncio.create_task(
                webapp_tarot(
                    bot,
                    dp,
                    user_id,
                    cards_list,
                    int(message_id),
                )
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


@app.get("/api/check-subscription", tags=["Payment 💸"])
async def check_subscription(request: Request):
    """
    Проверка статуса подписки пользователя.
    Принимает GET параметр ?user_id=123
    """
    # Безопасное получение параметра (вернет None, если ключа нет)
    user_id_str = request.query_params.get("user_id")

    if not user_id_str:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing user_id parameter"},
        )

    try:
        user_id = int(user_id_str)

        # Вызов вашей функции проверки (предполагаем, она возвращает dict)
        subscription_data = await rq.check_user_subscription(user_id)

        # Если функция вернула None (пользователя/подписки нет)

        if subscription_data is None:
            return JSONResponse(
                status_code=200,
                content={"is_active": False, "days_left": 0},
            )

        await rq.update_statistic("checkout_initiated")
        return JSONResponse(
            status_code=200,
            content=subscription_data,
        )

    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"error": "user_id must be an integer"},
        )
    except Exception as e:
        # Логируем ошибку для себя
        print(f"Error checking subscription: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )


@app.post("/api/create-payment", tags=["Payment 💸"])
async def payment_page(request: Request):
    """
    Получение ссылки для страницы оплаты от YooKassa
    """

    # Получаем тело запроса и подпись для проверки
    request_body = await request.body()

    # Парсим JSON данные из тела запроса
    data = json.loads(request_body.decode("utf-8"))

    user_id = data.get("user_id")
    message_id = data.get("message_id")
    email = data.get("email", None)
    amount = data.get("amount")
    if not all([user_id, message_id, amount]):
        return JSONResponse(
            status_code=400,
            content={"error": "Missing required parameters"},
        )
    # Создаем ссылку на оплату
    payment = await yookassa_service.create_payment_link(
        user_id=user_id,
        message_id=message_id,
        amount=amount,
        email=email,
    )
    payment_link = payment.confirmation.confirmation_url

    return JSONResponse(status_code=200, content={"payment_url": payment_link})


@app.get("/api/statistics", tags=["Admin 📊"])
async def get_statistics_endpoint():
    """
    API эндпоинт для Админ-панели.
    Преобразует данные из БД в формат для React-графиков.
    """
    try:
        stats_list, subs_list = await rq.get_statistics_data()

        history_users = [stat.total_users for stat in stats_list]
        history_active_users = [stat.active_users for stat in stats_list]

        history_checkout = [stat.checkout_initiated for stat in stats_list]
        history_purchased = [stat.purchased_subs for stat in stats_list]

        history_resp_sonnic = [stat.requests_sonnic for stat in stats_list]
        history_resp_tarot = [stat.requests_tarot for stat in stats_list]
        history_resp_map = [stat.requests_map_day for stat in stats_list]

        history_resps = [
            (stat.requests_sonnic + stat.requests_tarot + stat.requests_map_day)
            for stat in stats_list
        ]

        subscriptions_json = []
        all_subs = len(subs_list)
        for sub in subs_list:
            if "subscription" in str(sub.tariff):
                start_str = (
                    sub.start_date.strftime("%d.%m.%Y %H:%M") if sub.start_date else "-"
                )
                end_str = (
                    sub.end_date.strftime("%d.%m.%Y %H:%M") if sub.end_date else "-"
                )
                amount = str(sub.tariff).replace("subscription(", "").replace(")", "")

                subscriptions_json.append(
                    {
                        "recurrent": sub.is_recurring,
                        "price": f"{amount} ₽",
                        "start": start_str,
                        "end": end_str,
                        "attempts": sub.payment_attempts,
                    }
                )

        response_data = {
            #   // --- БЛОК 1: ПОЛЬЗОВАТЕЛИ ---
            "users": {
                "total": history_users[-1] if history_users else 0,
                "history": history_users,
            },
            #   // --- БЛОК 2: ПОДПИСКИ (КРАТКО) ---
            "active_users": {
                "total": history_active_users[-1] if history_active_users else 0,
                "history": history_active_users,
            },
            #   // --- БЛОК 3: АКТИВНЫХ ПОЛЬЗОВАТЕЛЕЙ ---
            "all_subs": {"total": all_subs},
            #   // --- БЛОК 4: ВОРОНКА ПРОДАЖ (НАЧАЛО) ---
            "checkout_initiated": {
                "total": history_checkout[-1] if history_checkout else 0,
                "history": history_checkout,
            },
            #   // --- БЛОК 5: ВОРОНКА ПРОДАЖ (УСПЕХ) ---
            "purchased": {
                "total": history_purchased[-1] if history_purchased else 0,
                "history": history_purchased,
            },
            #   // --- БЛОК 6: АКТИВНОСТЬ (ЗАПРОСЫ) ---
            "requests": {
                "total": history_resps[-1] if history_resps else 0,
                "history": history_resps,
                "breakdown": [
                    {
                        "id": 1,
                        "total": history_resp_sonnic[-1] if history_resp_sonnic else 0,
                        "history": history_resp_sonnic,
                    },
                    {
                        "id": 2,
                        "total": history_resp_map[-1] if history_resp_map else 0,
                        "history": history_resp_map,
                    },
                    {
                        "id": 3,
                        "total": history_resp_tarot[-1] if history_resp_tarot else 0,
                        "history": history_resp_tarot,
                    },
                ],
            },
            #   // --- БЛОК 7: ПОДПИСКИ (ПОДРОБНО) ---
            "subscriptions": subscriptions_json,
        }
        return JSONResponse(status_code=200, content=response_data)
    except Exception as e:
        logger.error(f"Ошибка при формировании статистики: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


# =====================================================================
# ВЕБХУК ЮKASSA СОХРАНЕН!
# FastAPI продолжает слушать этот URL без перебоев
# =====================================================================
@app.post("/webhook/yookassa", tags=["Payment 💸"])
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
        recurrent = metadata.get("recurrent")
        # Извлекаем metadata из платежа
        telegram_id = metadata.get("user_id")
        massage_id = metadata.get("message_id")
        email = metadata.get("email")

        # Извлекаем payment_method_id из данных платежа
        payment_method_id = payment_data.get("payment_method", {}).get("id")

        logger.info(
            f"Обработка события: {event_type}, платеж: {payment_id}, цена: {amount}, статус: {payment_status}"
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
                        if amount == "99.00":
                            end_date = (today + timedelta(days=1)).strftime("%d.%m.%Y")

                        else:
                            end_date = (today + timedelta(days=days_in_month)).strftime(
                                "%d.%m.%Y"
                            )

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
                await bot.send_message(
                    chat_id=1186592191,
                    text=f"✨ <b>Приобретена подписка</b>\n\n" f"{amount} рублей",
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
            if recurrent:
                if await rq.update_cansel_subscription(telegram_id):
                    logger.info(
                        f"Подписка пользователя {telegram_id} отменена. 3 попытки оплаты."
                    )
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=(
                            "⚠️ <b>Ваша подписка была отменена.</b>\n\n"
                            "Мы не смогли списать оплату за подписку после 3 попыток.\n"
                            "Чтобы продолжить пользоваться всеми функциями бота, пожалуйста, оформите новую подписку."
                        ),
                    )

        else:
            logger.info(f"Получено неизвестное событие {event_type}: {payment_id}")

        return JSONResponse(status_code=200, content={"status": "processed"})

    except Exception as e:
        logger.error(f"Ошибка обработки вебхука YooKassa: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
