import re
import random
import logging
import asyncio
from functools import wraps
from aiogram import F, Router, Bot, Dispatcher
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from aiogram.exceptions import TelegramBadRequest  # Добавлен импорт исключения

from app.services.yookassa_service import yookassa_service
from app.others.text_message import *
import app.services.AI_model as AI
import app.keyboards as kb
import app.database.requests as rq


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()


class sleep_data(StatesGroup):
    text = State()


class tarot_data(StatesGroup):
    text = State()


class AgreementStates(StatesGroup):
    """
    Группа состояний для процесса согласия с офертой.
    """

    awaiting_offer_agreement = State()  # Пользователь дал согласие с офертой
    awaiting_public_offer_agreement = (
        State()
    )  # Пользователь дал согласие с публичной офертой
    agreement_completed = State()  # Согласие получено, можно переходить к оплате


class email_data(StatesGroup):
    payment_message = State()
    email_message = State()
    email = State()


def handle_old_queries(answer_text: str = None):
    def decorator(func):
        @wraps(func)
        async def wrapper(callback: CallbackQuery, *args, **kwargs):
            try:
                await callback.answer(answer_text)
            except TelegramBadRequest as e:
                if "query is too old" in str(e):
                    logger.info(f"Ignored expired callback query: {callback.data}")
                    return
                raise e
            return await func(callback, *args, **kwargs)

        return wrapper

    return decorator


async def clear_tarot_keyboard_by_state(state: FSMContext, bot: Bot, user_id: int):
    """
    Универсальная функция для очистки клавиатуры таро
    """
    data = await state.get_data()
    tarot_msg_id = data.get("tarot_msg_id")

    if tarot_msg_id:
        try:
            await bot.edit_message_reply_markup(
                chat_id=user_id,
                message_id=tarot_msg_id,
                reply_markup=None,
            )
            logger.info(
                f"Убрана клавиатура у сообщения {tarot_msg_id} для пользователя {user_id}"
            )
            await state.clear()
        except Exception as e:
            logger.warning(
                f"Не удалось убрать клавиатуру у сообщения {tarot_msg_id}: {e}"
            )


@router.message(CommandStart())
async def start_command(message: Message, command: CommandObject, state: FSMContext):
    await clear_tarot_keyboard_by_state(state, message.bot, message.from_user.id)
    await state.clear()
    await rq.add_user(message.from_user.id, message.from_user.username, command.args)
    await message.answer(start_text, reply_markup=kb.menu_start)


@router.callback_query(F.data == "back_to_start")
@handle_old_queries()
async def callback_back_to_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(start_text, reply_markup=kb.menu_start)


@router.callback_query(F.data == "bonus_url")
@handle_old_queries()
async def callback_bonus_url(callback: CallbackQuery, state: FSMContext):
    await clear_tarot_keyboard_by_state(state, callback.bot, callback.from_user.id)
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "<b>🎁 Получить +1 бесплатный расклад</b>\n\n"
        "Пригласите друга по ссылке — и получите новый расклад без платы.\n"
        "🔹 Количество приглашений — неограничено\n"
        "🔹 1 приглашённый = 1 бесплатный расклад\n\n"
        "🔗 Отправь ссылку тем, кто тоже ищет ответы внутри себя.\n",
        reply_markup=kb.bonus_url(callback.from_user.id),
    )


@router.callback_query(F.data == "sleep")
@handle_old_queries()
async def callback_sleep(callback: CallbackQuery, state: FSMContext):
    await clear_tarot_keyboard_by_state(state, callback.bot, callback.from_user.id)
    await callback.answer()

    await state.clear()
    if await rq.check_subscription(callback.from_user.id):
        await callback.message.answer(
            f"🌙 <b>Добро пожаловать в Сонник, {callback.from_user.first_name}!</b>\n\n"
            "Пожалуйста, опишите свой сон подробно — где вы были, что происходило, "
            "какие эмоции испытывали. Чем больше деталей, тем точнее будет анализ.💫"
        )
        await state.set_state(sleep_data.text)
    else:
        await callback.message.answer(
            "🌙 <b>Сонник доступен только обладателю подписки</b> — чтобы расшифровать сны глубже, вам нужно стать Premium пользователем.\n\n"
            "✨ Выберите свой путь:\n"
            "🔹 <b>Получите ещё одно бесплатное гадание</b> — пригласите друга и раскрой новую возможность.\n"
            "🔹 <b>Получите безграничные возможности</b> — теперь вы можешь гадать сколько угодно раз, каждый день, без ограничений.\n\n"
            f"💡 Сейчас вам доступно {await rq.caunt_taro(callback.from_user.id)} таро-гаданий.\n\n"
            "— Малина всегда с вами ❤️",
            reply_markup=kb.btn_attempts,
        )


@router.message(sleep_data.text)
async def message_sleep(message: Message, state: FSMContext):
    msg = await message.answer(
        "Проникаю в туман сновидений...\n✨ Раскрываю скрытые послания вашей души из ночного путешествия"
    )

    await state.update_data(text=message.text)
    data = await state.get_data()
    await state.clear()

    response = await AI.generate_response(
        text=data.get("text"),
        prompt="sleep",
    )

    logger.info(f"🌙 Сон пользователя: {data.get('text')}")
    await msg.delete()

    try:
        await message.answer(response)
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e):
            clean_response = re.sub(r"<[^>]+>", "", response)
            await message.answer(clean_response)
        else:
            await message.answer(
                "В данный момент эта функция не доступна 😢\n"
                "Пожалуйста, попробуйте позже."
            )
            raise e


@router.callback_query(F.data.in_(["tarot", "tarot_reminder"]))
@handle_old_queries()
async def callback_tarot(callback: CallbackQuery, state: FSMContext):
    await clear_tarot_keyboard_by_state(state, callback.bot, callback.from_user.id)
    await callback.answer()

    await state.clear()

    if await rq.check_tarot(callback.from_user.id):

        if callback.data == "tarot_reminder":
            await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "🃏 Готовы получить ответ от карт Таро?\n\n" "<b>Задай свой вопрос:</b>"
        )
        await state.set_state(tarot_data.text)
    else:
        await callback.message.answer(
            "🔮 <b>Ваши бесплатные расклады закончились</b>, но Малина по-прежнему с вами!\n\n"
            "✨ Выберите свой путь:\n"
            "🔹 <b>Получите ещё одно бесплатное гадание</b> — пригласите друга и раскрой новую возможность.\n"
            "🔹 <b>Получите безграничные возможности</b> — теперь вы можешь гадать сколько угодно раз, каждый день, без ограничений.\n\n"
            f"💡 Сейчас вам доступно 0 таро-гаданий.\n\n"
            "— Малина всегда с вами ❤️",
            reply_markup=kb.btn_attempts,
        )


@router.message(tarot_data.text)
async def message_tarot(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    data = await state.get_data()
    question = data.get("text")

    await state.clear()

    msg = await message.answer(
        "<b>Выберите <b>3 карты</b>, которые говорят с вашей душой.</b>\n\n"
        "✨ Выбранные карты появятся здесь. Когда закончите, нажмите «Трактовка»."
    )
    await msg.edit_reply_markup(reply_markup=kb.webapp_button(msg.message_id))
    await state.update_data(question=question, tarot_msg_id=msg.message_id)


async def webapp_tarot(
    bot: Bot,
    dp: Dispatcher,
    user_id: int,
    cards_list: str,
    message_id: int,
):
    try:
        storage_key = StorageKey(
            chat_id=user_id,
            user_id=user_id,
            bot_id=bot.id,
        )
        state: FSMContext = FSMContext(
            storage=dp.storage,
            key=storage_key,
        )
        data = await state.get_data()
        question = data.get("question")
        tarot_new_continuation = data.get("tarot_new_continuation", False)

        await rq.take_away_tarot(user_id)
        # Редактируем исходное сообщение вместо удаления
        await bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text="Карты настраиваются на ваш запрос...\n🃏 Ответ придет через мгновение",
            parse_mode="HTML",
        )

        if tarot_new_continuation:
            # Это новый продолженный расклад таро.
            logger.info("🔮 Это новый продолженный расклад таро.")
            question = data.get("question")
            continuation_response_text = data.get("continuation_response_text")

            response = await AI.generate_response(
                f"Вопрос: {question}\nКарты: {cards_list}",
                "cards_taro",
                continuation_response_text,
                question,
            )
        else:
            # Генерируем ответ
            response = await AI.generate_response(
                text=f"Вопрос: {question}\nКарты: {cards_list}",
                prompt="cards_taro",
            )

        logger.info(
            f"""Пользователь: {user_id}.
            Карты: {cards_list}.
            Вопрос: {question}.
            ID сообщения: {message_id}."""
        )

        # Редактируем сообщение снова, показывая результат
        try:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=response,
                parse_mode="HTML",
            )

        except TelegramBadRequest as e:
            if "can't parse entities" in str(e):
                response = re.sub(r"<[^>]+>", "", response)

                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text=response,
                    parse_mode="HTML",
                )
            else:
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=message_id,
                    text=(
                        "В данный момент эта функция не доступна 😢\n"
                        "Пожалуйста, попробуйте позже."
                    ),
                )
                raise e

        # # Генерируем продолжение
        # continuation_response_text = f"Вопрос: {question}\n\n{response}"

        # question_response = await AI.generate_response(
        #     text=continuation_response_text,
        #     prompt="continuation_tarot",
        # )

        # # Редактируем сообщение снова, показывая результат
        # try:
        #     msg_id = await bot.send_message(
        #         chat_id=user_id,
        #         text=question_response,
        #         reply_markup=kb.btn_continuation_tarot,
        #     )
        # except TelegramBadRequest as e:
        #     if "can't parse entities" in str(e):
        #         question_response = re.sub(r"<[^>]+>", "", question_response)

        #         msg_id = await bot.send_message(
        #             chat_id=user_id,
        #             text=question_response,
        #             reply_markup=kb.btn_continuation_tarot,
        #         )
        #     else:
        #         raise e

        # await state.update_data(
        #     continuation_response_text=continuation_response_text,
        #     question=question_response,
        #     tarot_msg_id=msg_id.message_id,
        # )
    except Exception as e:
        print(f"Ошибка при обработке расклада таро продолжение: {e}")
        import traceback

        traceback.print_exc()


@router.callback_query(F.data == "continuation_tarot")
@handle_old_queries()
async def callback_continuation_tarot(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    tarot_msg_id: Message = data.get("tarot_msg_id")

    if tarot_msg_id:
        if await rq.check_tarot(callback.from_user.id):

            await callback.message.edit_reply_markup(reply_markup=None)
            msg = await callback.message.answer(
                "<b>Выберите <b>3 карты</b>, которые говорят с вашей душой.</b>\n\n"
                "✨ Выбранные карты появятся здесь. Когда закончите, нажмите «Трактовка»."
            )

            await msg.edit_reply_markup(reply_markup=kb.webapp_button(msg.message_id))
            await state.update_data(tarot_new_continuation=True)

        else:
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.answer(
                "🔮 <b>Ваши бесплатные расклады закончились</b>, но Малина по-прежнему с вами!\n\n"
                "✨ Выберите свой путь:\n"
                "🔹 <b>Получите ещё одно бесплатное гадание</b> — пригласите друга и раскрой новую возможность.\n"
                "🔹 <b>Получите безграничные возможности</b> — теперь вы можешь гадать сколько угодно раз, каждый день, без ограничений.\n\n"
                f"💡 Сейчас вам доступно 0 таро-гаданий.\n\n"
                "— Малина всегда с вами ❤️",
                reply_markup=kb.btn_attempts,
            )
            await state.clear()
    else:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "Произошла ошибка😢\nПожалуйста, начните новый расклад таро."
        )
        await state.clear()


@router.callback_query(F.data.in_(["card_day", "card_day_reminder"]))
@handle_old_queries()
async def callback_card_day(callback: CallbackQuery, state: FSMContext):
    await clear_tarot_keyboard_by_state(state, callback.bot, callback.from_user.id)
    await callback.answer()

    await state.clear()

    if callback.data == "card_day_reminder":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass

    if await rq.check_card_day(callback.from_user.id):
        msg = await callback.message.answer(
            "Соединяюсь с космической энергией...\n🌌 Раскрываю тайны Вселенной для вашей карты дня"
        )

        selected_card = random.choice(tarot_deck)
        file_id = file_id_cards[selected_card]

        response = await AI.generate_response(
            text=f"Карта дня: {selected_card}",
            prompt="card_day",
        )

        await msg.delete()

        if response != (
            "В данный момент эта функция не доступна 😢\n"
            "Пожалуйста, попробуйте позже."
        ):
            ...
            # await callback.message.answer_photo(photo=file_id, parse_mode="HTML")

        try:
            await callback.message.answer(response)
        except TelegramBadRequest as e:
            if "can't parse entities" in str(e):
                clean_response = re.sub(r"<[^>]+>", "", response)
                await callback.message.answer(clean_response)
            else:
                await callback.message.answer(
                    "В данный момент эта функция не доступна 😢\n"
                    "Пожалуйста, попробуйте позже."
                )
                raise e

        if callback.data == "card_day_reminder":
            await asyncio.sleep(5)
            remaining_tarot = await rq.caunt_taro(callback.from_user.id)

            if await rq.check_subscription(callback.from_user.id):
                await callback.message.answer(
                    "💫 Не забывайте, у Малины всегда есть для вас:\n\n"
                    "🃏 <b>Расклад таро</b> — получите ответ на любой вопрос\n"
                    "🌙 <b>Сонник</b> — расшифруйте послания ваших снов\n\n"
                    "Твоя подписка открывает все возможности!",
                    reply_markup=kb.btn_reminder_subscription,
                )
            elif remaining_tarot > 0:
                await callback.message.answer(
                    f"💡 <b>У вас ещё есть {remaining_tarot} таро-гаданий</b>\n\n"
                    "✨ Если есть вопрос - нажмите на кнопку, и я раскрою тайны ваших карт",
                    reply_markup=kb.btn_tarot_from_reminder,
                )
            else:
                await callback.message.answer(
                    "🔮 Кстати, ваши бесплатные таро-гадания закончились.\n"
                    "Хотите, я расскажу, как получить ещё?",
                    reply_markup=kb.btn_more_info_from_reminder,
                )

    else:
        await callback.message.answer(
            "<b>🔮 Вы уже получили свою Карту Дня сегодня.</b>\n"
            "Энергия этой карты ещё с вами — прислушайся к её шепоту.\n\n"
            "✨ Следующая Карта Дня откроется для вас завтра.\n"
            "Не спешите — Вселенная даёт ответы в своё время.\n\n"
            "Ждите утром… или просто приходите, когда почувствуете — она будет ждать. 💫\n\n"
            "— Малина всегда с вами ❤️"
        )


@router.callback_query(F.data == "learn_more")
@handle_old_queries()
async def callback_learn_more(callback: CallbackQuery, state: FSMContext):
    await clear_tarot_keyboard_by_state(state, callback.bot, callback.from_user.id)
    await callback.answer()
    await state.clear()

    await callback.message.edit_text(
        "🔮 <b>Ваши бесплатные расклады закончились</b>, но Малина по-прежнему с вами!\n\n"
        "✨ Выберите свой путь:\n"
        "🔹 <b>Получите ещё одно бесплатное гадание</b> — пригласите друга и раскрой новую возможность.\n"
        "🔹 <b>Получите безграничные возможности</b> — теперь вы можешь гадать сколько угодно раз, каждый день, без ограничений.\n\n"
        f"💡 Сейчас вам доступно 0 таро-гаданий.\n\n"
        "— Малина всегда с вами ❤️",
        reply_markup=kb.btn_attempts,
    )


# Отправка в 10:30 напоминание о Карте Дня
async def card_day_10am(users: list, bot: Bot):
    success_count = 0
    fail_count = 0

    for user in users:
        try:
            user_name = (await bot.get_chat(user.telegram_id)).first_name

            user_id = user.telegram_id
            user_name = user_name + ", " if user_name != None else ""

            await bot.send_message(
                chat_id=user_id,
                text=(
                    f"<b>{user_name}Вам доступна карта дня! 🔮</b>\n\n"
                    "Нажмите Получить карту дня, и я отправлю предсказание 🙌"
                ),
                reply_markup=kb.btn_card_day,
            )

            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1

    await bot.send_message(
        chat_id=1186592191,
        text=(
            f"📤 <b>Рассылка в 10:30 о карте дня завершена!</b>\n\n"
            f"📊 Всего пользователей: <b>{len(users)}</b>\n"
            f"✅ Успешно: <b>{success_count}</b>\n"
            f"❌ Не удалось: <b>{fail_count}</b>"
        ),
    )


@router.message(Command("subscription"))
async def command_subscription(message: Message, state: FSMContext):
    """Обработчик команды /subscription."""
    await clear_tarot_keyboard_by_state(state, message.bot, message.from_user.id)

    await state.clear()

    user_id = message.from_user.id
    logger.info(f"Юзер {user_id} оправил запрос на подписку /subscription.")

    user = await rq.get_user(user_id)

    if user.tariff == "VIP":

        await message.answer(
            f"✨ <b>Ваша подписка активна!</b>\n\n" "Действие подписки безлимито 🌟"
        )
        logger.info(f"Юзер {user_id} VIP")
    elif user.tariff == "gift":

        subscription = await rq.get_user_subscription(user_id)

        end_date_str = subscription.end_date.strftime("%d.%m.%Y")
        await message.answer(
            f"✨ <b>Ваша подписка активна!</b>\n\n" f"📅 Действует до: {end_date_str}"
        )
        logger.info(f"Юзер {user_id} gift")
    elif user.tariff == "subscription":

        subscription = await rq.get_user_subscription(user_id)

        end_date_str = subscription.end_date.strftime("%d.%m.%Y")
        await message.answer(
            f"✨ <b>Ваша подписка активна!</b>\n\n"
            f"📅 Действует до: {end_date_str}\n"
            f"🔄 Автопродление: {'Включено ✅' if subscription.is_recurring else 'Отключено ❌'}\n\n"
            f"Вы можете {'отменить' if subscription.is_recurring else 'включить'} автопродление в любой момент.",
            reply_markup=kb.btn_management_subscription,
        )
        logger.info(f"User {user_id} already has an active subscription.")
    else:

        await message.answer(
            subscription_text,
            disable_web_page_preview=True,
            reply_markup=kb.btn_create_subscription_99_or_300,
        )


@router.callback_query(F.data == "subscription_message_all")
async def subscription_message_all(callback: CallbackQuery, state: FSMContext):
    """Обработчик команды /subscription."""

    await state.clear()

    await callback.message.edit_reply_markup(reply_markup=None)

    user_id = callback.from_user.id
    logger.info(f"Юзер {user_id} оправил запрос на подписку /subscription.")

    user = await rq.get_user(user_id)

    if user.tariff == "VIP":

        await callback.message.answer(
            f"✨ <b>Ваша подписка активна!</b>\n\n" "Действие подписки безлимито 🌟"
        )
        logger.info(f"Юзер {user_id} VIP")
    elif user.tariff == "gift":

        subscription = await rq.get_user_subscription(user_id)

        end_date_str = subscription.end_date.strftime("%d.%m.%Y")
        await callback.message.answer(
            f"✨ <b>Ваша подписка активна!</b>\n\n" f"📅 Действует до: {end_date_str}"
        )
        logger.info(f"Юзер {user_id} gift")
    elif user.tariff == "subscription":

        subscription = await rq.get_user_subscription(user_id)

        end_date_str = subscription.end_date.strftime("%d.%m.%Y")
        await callback.message.answer(
            f"✨ <b>Ваша подписка активна!</b>\n\n"
            f"📅 Действует до: {end_date_str}\n"
            f"🔄 Автопродление: {'Включено ✅' if subscription.is_recurring else 'Отключено ❌'}\n\n"
            f"Вы можете {'отменить' if subscription.is_recurring else 'включить'} автопродление в любой момент.",
            reply_markup=kb.btn_management_subscription,
        )
        logger.info(f"User {user_id} already has an active subscription.")
    else:

        await callback.message.answer(
            subscription_text,
            disable_web_page_preview=True,
            reply_markup=kb.btn_create_subscription_99_or_300,
        )


@router.callback_query(
    F.data.in_(["create_subscription_99", "create_subscription_300"])
)
@handle_old_queries()
async def callback_create_subscription(callback: CallbackQuery, state: FSMContext):
    """Обработчик создания подписки."""
    await clear_tarot_keyboard_by_state(state, callback.bot, callback.from_user.id)

    await callback.answer()
    await state.clear()

    subscription_text = (
        subscription_text_99
        if callback.data == "create_subscription_99"
        else subscription_text_300
    )

    user_id = callback.from_user.id
    logger.info(f"Юзер {user_id} оправил запрос на подписку.")

    user = await rq.get_user(user_id)

    if user.tariff == "VIP":

        await callback.message.edit_text(
            f"✨ <b>Ваша подписка активна!</b>\n\n" "Действие подписки безлимито 🌟"
        )
        logger.info(f"Юзер {user_id} VIP")
    elif user.tariff == "subscription":

        subscription = await rq.get_user_subscription(user_id)

        end_date_str = subscription.end_date.strftime("%d.%m.%Y")
        await callback.message.edit_text(
            f"✨ <b>Ваша подписка активна!</b>\n\n"
            f"📅 Действует до: {end_date_str}\n"
            f"🔄 Автопродление: {'Включено ✅' if subscription.is_recurring else 'Отключено ❌'}\n\n"
            f"Вы можете {'отменить' if subscription.is_recurring else 'включить'} автопродление в любой момент.",
            reply_markup=kb.btn_management_subscription,
        )
        logger.info(f"User {user_id} already has an active subscription.")
    else:
        # --- Создание ссылки ---
        logger.info(f"User {user_id} requested /dis.")

        # Сбрасываем состояние пользователя
        await state.clear()

        await state.set_state(AgreementStates.awaiting_offer_agreement)
        await state.update_data(
            agreed_to_offer=False,
            agreed_to_public_offer=False,
            subscription_text=callback.data,
        )
        # Отправляем сообщение с клавиатурой и устанавливаем начальное состояние
        await callback.message.answer(
            subscription_text,
            disable_web_page_preview=True,
            reply_markup=kb.get_dis_keyboard(
                agreed_to_offer=False, agreed_to_public_offer=False
            ),
        )


@router.callback_query(F.data == "management_subscription")
@handle_old_queries()
async def callback_management_subscription(callback: CallbackQuery, state: FSMContext):
    """🔄 Изменить автопродление"""
    await clear_tarot_keyboard_by_state(state, callback.bot, callback.from_user.id)

    await callback.answer()
    await state.clear()

    user_id = callback.from_user.id

    subscription = await rq.get_user_subscription(user_id)

    if subscription and subscription.tariff != "VIP":

        # --- Отменяем автопродление ---
        logger.info(f"User {user_id} requested to cancel recurring payment.")

        # 1. Получаем ID подписки YooKassa из БД
        subscription_id = subscription.subscription_id

        if not subscription_id:
            logger.warning(
                f"Не найден идентификатор подписки на YooKassa для пользователя {user_id}. "
                "Помечено как отмененное в базе данных."
            )
            # Если ID подписки CP нет, просто обновляем БД

            await callback.message.edit_text(
                text=f"⚠️ Автопродление отключено.\n"
                f"Если у вас были проблемы с оплатой, пожалуйста, свяжитесь с поддержкой.",
                reply_markup=kb.btn_management_subscription,
            )
        else:
            logger.info(
                f"Подписка YooKassa {subscription_id} для пользователя {user_id} успешно изменина."
            )
            # 2. Отменяем подписку в YooKassa
            await rq.activ_or_reactivate_subscription(user_id)

            msg = await callback.message.edit_text(
                text=(
                    f"✨ <b>Ваша подписка активна!</b>\n\n"
                    f"📅 Действует до: {subscription.end_date.strftime('%d.%m.%Y')}\n"
                    f"🔄 Автопродление: {'Отключено ❌' if subscription.is_recurring else 'Включено ✅'}\n\n"
                    f"Вы можете {'включить' if subscription.is_recurring else 'отменить'} автопродление в любой момент."
                ),
            )
            await asyncio.sleep(2)
            await msg.edit_reply_markup(reply_markup=kb.btn_management_subscription)

    elif subscription and subscription.tariff == "VIP":
        await callback.message.edit_text(
            text=f"✨ <b>Ваша подписка VIP активна!</b>\n\nДействие подписки безлимитно 🌟"
        )
        logger.info(f"Пользователь {user_id} имеет VIP-подписку.")

    else:
        await callback.message.edit_text(
            "<b>⏳ Ваша подписка закончилась</b> — и доступ к безлимиту приостановлен.\n\n"
            "Вы уже знаешь, как удобно гадать по Таро без ограничений, раскрывать сны в Соннике и получать персональные ответы каждый день.\n"
            "Сейчас это доступно только по активной подписке."
        )


# @router.message()
# async def message_text(message: Message, state: FSMContext):
#     await state.clear()
#     await message.answer("Я тебя не понимаю😢")


@router.callback_query(F.data == "agree_offer")
@handle_old_queries()
async def callback_agree_offer(callback: CallbackQuery, state: FSMContext):
    await clear_tarot_keyboard_by_state(state, callback.bot, callback.from_user.id)

    """Callback обработчик для согласия с офертой."""
    try:
        await callback.answer()

        user_id = callback.from_user.id
        logger.info(f"User {user_id} toggled offer agreement.")

        # Получаем текущее состояние данных FSM
        user_data = await state.get_data()

        # Безопасное получение значений с дефолтом False
        current_offer = user_data.get("agreed_to_offer", False)
        current_public_offer = user_data.get("agreed_to_public_offer", False)

        # Инвертируем значение
        new_offer_value = not current_offer

        # Обновляем данные состояния
        await state.update_data(
            agreed_to_offer=new_offer_value, agreed_to_public_offer=current_public_offer
        )

        await state.set_state(AgreementStates.awaiting_offer_agreement)

        # Обновляем клавиатуру
        try:
            await callback.message.edit_reply_markup(
                reply_markup=kb.get_dis_keyboard(
                    agreed_to_offer=new_offer_value,
                    agreed_to_public_offer=current_public_offer,
                )
            )
        except Exception as e:
            logger.warning(f"Could not update keyboard: {e}")

        # Проверяем, согласен ли пользователь с обоими пунктами
        if new_offer_value and current_public_offer:
            await proceed_to_payment(callback, state, user_id)
        elif not current_public_offer:
            await state.set_state(AgreementStates.awaiting_public_offer_agreement)

    except Exception as e:
        logger.error(f"Error in callback_agree_offer: {e}")


@router.callback_query(F.data == "agree_public_offer")
@handle_old_queries()
async def callback_agree_public_offer(callback: CallbackQuery, state: FSMContext):
    """Callback обработчик для согласия с публичной офертой."""

    await clear_tarot_keyboard_by_state(state, callback.bot, callback.from_user.id)
    try:
        await callback.answer()

        user_id = callback.from_user.id
        logger.info(f"User {user_id} toggled public offer agreement.")

        # Получаем текущее состояние данных FSM
        user_data = await state.get_data()
        # Безопасное получение значений с дефолтом False
        current_offer = user_data.get("agreed_to_offer", False)
        current_public_offer = user_data.get("agreed_to_public_offer", False)

        # Инвертируем значение
        new_public_offer_value = not current_public_offer

        # Обновляем данные состояния
        await state.update_data(
            agreed_to_offer=current_offer, agreed_to_public_offer=new_public_offer_value
        )

        await state.set_state(AgreementStates.awaiting_offer_agreement)

        # Обновляем клавиатуру
        try:
            await callback.message.edit_reply_markup(
                reply_markup=kb.get_dis_keyboard(
                    agreed_to_offer=current_offer,
                    agreed_to_public_offer=new_public_offer_value,
                )
            )
        except Exception as e:
            logger.warning(f"Could not update keyboard: {e}")

        # Проверяем, согласен ли пользователь с обоими пунктами
        if current_offer and new_public_offer_value:
            await proceed_to_payment(callback, state, user_id)
        elif not current_offer:
            await state.set_state(AgreementStates.awaiting_offer_agreement)

    except Exception as e:
        logger.error(f"Error in callback_agree_public_offer: {e}")


async def proceed_to_payment(callback: CallbackQuery, state: FSMContext, user_id: int):
    """Общая функция для перехода к оплате"""

    try:
        logger.info(f"User {user_id} proceeding to payment.")
        data_subscription_text = (await state.get_data()).get("subscription_text")

        subscription_text = (
            subscription_text_99
            if data_subscription_text == "create_subscription_99"
            else subscription_text_300
        )
        # Меняем текст сообщения
        sent_message = await callback.message.edit_text(
            subscription_text,
            reply_markup=None,
            disable_web_page_preview=True,
        )

        # Устанавливаем состояние "отправка почты"
        await state.clear()
        await state.set_state(email_data.email)
        email_message = await callback.message.answer(
            "Напиши свою почту для отправки чека:"
        )
        await state.update_data(
            payment_message=sent_message, email_message=email_message.message_id
        )

    except Exception as e:
        logger.error(f"Error in proceed_to_payment: {e}")
        # Можно отправить сообщение об ошибке пользователю
        await callback.message.answer("Произошла ошибка, попробуйте еще раз.")


@router.message(email_data.email)
async def message_email(message: Message, state: FSMContext):
    # Получаем объект сообщениий из состояния
    user_data = await state.get_data()

    payment_message: Message = user_data.get("payment_message")
    email_message = user_data.get("email_message")

    user_message = message.text
    await message.delete()
    # Проверяем, является ли введенный текст валидным email
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if re.match(email_pattern, user_message):
        await message.bot.delete_message(
            chat_id=message.from_user.id, message_id=email_message
        )

        await payment_message.edit_text(
            text=payment_message.text + f"\n\n✅ Ваша почта принята: {user_message}\n"
            "Теперь вы можете перейти к оплате.",
            reply_markup=None,
            disable_web_page_preview=True,
        )

        amount = (
            "99.00"
            if "Пробная подписка — 99 ₽ / 24 часа" in payment_message.text
            else "300.00"
        )

        # Создаем ссылку на оплату
        payment = await yookassa_service.create_payment_link(
            user_id=message.from_user.id,
            message_id=payment_message.message_id,
            amount=amount,
            email=user_message,
        )
        payment_link = payment.confirmation.confirmation_url

        # Редактируем сообщение с ссылкой на оплату
        await payment_message.edit_reply_markup(
            reply_markup=kb.subscription_payment(payment_link),
        )

        await state.clear()

    else:

        # Email невалиден, просим ввести снова
        try:
            email_message = await message.bot.edit_message_text(
                chat_id=message.from_user.id,
                message_id=email_message,
                text="Пожалуйста, введите <b>корректный email...</b>\n\nНапиши свою почту для отправки чека:",
            )
            await state.update_data(email_message=email_message.message_id)
        except:
            pass
