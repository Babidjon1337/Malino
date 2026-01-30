from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from urllib.parse import quote

from config import WEB_APP_URL
import app.database.requests as rq

menu_start = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🌙 Сонник", callback_data="sleep")],
        [InlineKeyboardButton(text="🃏 Расклад таро", callback_data="tarot")],
        [InlineKeyboardButton(text="📅 Карта дня", callback_data="card_day")],
    ]
)

btn_card_day = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Получить карту дня 🌞", callback_data="card_day_reminder"
            )
        ],
    ]
)

# Клавиатура для напоминания пользователям с подпиской
btn_reminder_subscription = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🃏 Расклад таро", callback_data="tarot")],
        [InlineKeyboardButton(text="🌙 Сонник", callback_data="sleep")],
    ]
)

# Клавиатура для напоминания, когда есть таро-гаданий
btn_tarot_from_reminder = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🃏 Задать вопрос", callback_data="tarot_reminder")]
    ]
)

# продолжение карт тыро
btn_continuation_tarot = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✨ Узнать больше", callback_data="continuation_tarot"
            )
        ],
        [InlineKeyboardButton(text="🚀 Назад", callback_data="back_to_start")],
    ]
)

# Клавиатура для напоминания, когда нет таро-гаданий
btn_more_info_from_reminder = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✨ Узнать больше", callback_data="learn_more")]
    ]
)


btn_attempts = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🎁 Получи ещё 1 бесплатное гадание", callback_data="bonus_url"
            )
        ],
        [
            InlineKeyboardButton(
                text="💎 Безлимитный доступ",
                callback_data="subscription_message_all",
            )
        ],
    ]
)


def btn_web_payment(message_id: str, user_id: int, back: bool = False):
    # Кодируем вопрос для безопасной передачи в URL
    if back:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💎 Выбрать подписку",
                        web_app=WebAppInfo(
                            url=f"{WEB_APP_URL}/payment?message_id={message_id}&user_id={user_id}"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад", callback_data="back_to_subscription"
                    )
                ],
            ]
        )
    else:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💎 Выбрать подписку",
                        web_app=WebAppInfo(
                            url=f"{WEB_APP_URL}/payment?message_id={message_id}&user_id={user_id}"
                        ),
                    )
                ],
            ]
        )


def bonus_url(telegram_id: str):
    copy_text = f"🔮 Присоединяйся к Malina Bot:\n\nhttps://t.me/malina_ezo_bot?start={telegram_id}"
    share_url = f"https://t.me/share/url?url={quote(copy_text)}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📤 Отправить другу", url=share_url)],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад", callback_data="back_to_subscription"
                )
            ],
        ]
    )


back_to_subscription = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_subscription")],
    ]
)


# def subscription_payment(payment_link: str):
#     return InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_link)],
#         ]
#     )


btn_management_subscription = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Изменить автопродление",
                callback_data="management_subscription",
            )
        ],
    ]
)


def webapp_button(message_id: str):
    # Кодируем вопрос для безопасной передачи в URL
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔮 Выбрать карты",
                    web_app=WebAppInfo(
                        url=f"{WEB_APP_URL}/home?message_id={message_id}"
                    ),
                )
            ],
        ],
    )


# ----------------------- Admin -------------------------


admin_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Вся статистика 📊",
                web_app=WebAppInfo(url=f"{WEB_APP_URL}/admin"),
            ),
        ],
        [
            InlineKeyboardButton(
                text="Рассылка 📩",
                callback_data="admin_message_all_users",
            ),
            InlineKeyboardButton(
                text="Промокоды 🎟",
                callback_data="admin_promo_codes",
            ),
        ],
    ]
)


btn_back_admin = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_admin"),
        ]
    ]
)

btn_need_button_simple = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Добавить кнопку", callback_data="btn_yes"),
            InlineKeyboardButton(text="❌ Без кнопки", callback_data="btn_no"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_admin")],
    ]
)

btn_send_msg = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Разослать", callback_data="to_send"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="back_admin"),
        ],
    ]
)

btn_promo_code = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ Создать новый", callback_data="new_promo_code"
            ),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_admin"),
        ],
    ]
)
