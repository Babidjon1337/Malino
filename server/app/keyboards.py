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
                text="✨ Пробная подписка на сутки за 99 ₽",
                callback_data="create_subscription_99",
            )
        ],
        [
            InlineKeyboardButton(
                text="💎 Безлимит на месяц за 300 ₽",
                callback_data="create_subscription_300",
            )
        ],
    ]
)
btn_create_subscription_99_or_300 = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔮 Пробная подписка на сутки за 99 ₽",
                callback_data="create_subscription_99",
            )
        ],
        [
            InlineKeyboardButton(
                text="🚀 Безлимит на месяц за 300 ₽",
                callback_data="create_subscription_300",
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
        ]
    )


def subscription_payment(payment_link: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_link)],
        ]
    )


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
                    web_app=WebAppInfo(url=f"{WEB_APP_URL}?message_id={message_id}"),
                )
            ],
        ],
    )


def get_dis_keyboard(
    agreed_to_offer: bool, agreed_to_public_offer: bool
) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для команды /dis с кнопками "согласие с офертой" и "согласие публичная офрта".
    Отображает галочки, если пользователь согласился.

    :param agreed_to_offer: True, если пользователь согласился с офертой.
    :param agreed_to_public_offer: True, если пользователь согласился с публичной офертой.
    :return: InlineKeyboardMarkup.
    """
    keyboard = []

    # Кнопка "согласие с офертой"
    offer_text = f"{'✅ ' if agreed_to_offer else ''}согласие с офертой"
    keyboard.append(
        [InlineKeyboardButton(text=offer_text, callback_data="agree_offer")]
    )

    # Кнопка "согласие публичная офрта"
    public_offer_text = (
        f"{'✅ ' if agreed_to_public_offer else ''}согласие с публичной оферта"
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                text=public_offer_text, callback_data="agree_public_offer"
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ----------------------- Admin -------------------------


admin_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
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

btn_buy_subscription = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Купить подписку ✨", callback_data="subscription_message_all"
            )
        ]
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
