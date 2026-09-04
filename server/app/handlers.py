import re
import html
import time
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
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramRetryAfter,
)  # Добавлен импорт исключений

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


# Драфт — «живая» печать ответа. Телеграм держит драфт как 30-секундный
# превью, поэтому весь текст нужно успеть напечатать за это окно.
DRAFT_TICK = 0.7  # как часто обновляем драфт, сек
DRAFT_MIN_CHARS = 60  # минимум символов за тик (темп для коротких ответов)
DRAFT_TOTAL_SECONDS = 20  # за столько секунд печать должна закончиться

ERROR_TEXT = "В данный момент эта функция не доступна 😢\nПожалуйста, попробуйте позже."


def _plain(text: str) -> str:
    """
    Текст для драфта: без HTML-тегов. Драфт разметку не форматирует,
    поэтому теги в нем видны как обычный текст (<b>Карта дня</b>).
    """
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def _snap_to_word(text: str, pos: int) -> int:
    """Сдвигает границу показа к концу слова, чтобы не рвать слова посередине."""
    if pos >= len(text):
        return len(text)
    start = max(0, pos - 30)
    best = max(text.rfind(" ", start, pos), text.rfind("\n", start, pos))
    return best + 1 if best > 0 else pos


async def stream_to_draft(
    bot: Bot,
    chat_id: int,
    agen,
    placeholder_id: int | None = None,
    on_first_chunk=None,
) -> str:
    """
    Показывает ответ AI «вживую»: текст допечатывается в драфт-сообщении
    ровным читаемым темпом, а в конце приходит обычное сообщение с полным
    ответом (оно же убирает драфт).

    Модель генерирует в разы быстрее, чем человек читает, поэтому темп
    показа задают тики, а не скорость провайдера: на каждом тике остаток
    делится на число оставшихся тиков до DRAFT_TOTAL_SECONDS. Так печать
    идет плавно и всегда успевает закончиться внутри 30-секундного окна.

    - placeholder_id — сообщение «генерирую...», убирается на первом кусочке
    - on_first_chunk — корутина, вызывается на первом кусочке (например, фото карты)
    - возвращает финальный текст ответа (или ERROR_TEXT при сбое)
    """
    draft_id = random.randint(1, 1_000_000)
    raw_text = ""  # последний накопленный ответ (с HTML-разметкой)
    stream_done = False
    stream_error = None

    async def reader():
        nonlocal raw_text, stream_done, stream_error
        try:
            async for visible in agen:
                raw_text = visible
        except Exception as e:
            stream_error = e
        finally:
            stream_done = True

    async def drop_placeholder():
        nonlocal placeholder_id
        if placeholder_id is None:
            return
        msg_id, placeholder_id = placeholder_id, None
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except TelegramBadRequest as e:
            logger.warning(f"⚠️ Не удалось убрать сообщение-заглушку: {e}")

    reader_task = asyncio.create_task(reader())
    shown = 0
    started = None

    try:
        while True:
            plain = _plain(raw_text).strip()

            if plain and started is None:
                # Первый кусочек текста: убираем заглушку и отдаем управление хендлеру
                started = time.monotonic()
                await drop_placeholder()
                if on_first_chunk is not None:
                    try:
                        await on_first_chunk()
                    except Exception:
                        logger.exception("⚠️ on_first_chunk упал (не критично)")
                    on_first_chunk = None

            if plain:
                elapsed = time.monotonic() - started
                behind = len(plain) - shown
                # Сколько тиков осталось до конца отведенного времени
                ticks_left = max(1, int((DRAFT_TOTAL_SECONDS - elapsed) / DRAFT_TICK))
                step = max(DRAFT_MIN_CHARS, -(-behind // ticks_left))  # ceil
                out_of_time = elapsed >= DRAFT_TOTAL_SECONDS

                if out_of_time or (stream_done and behind <= step):
                    target = len(plain)  # хвост показываем целиком
                else:
                    target = _snap_to_word(plain, shown + step)

                if target > shown:
                    shown = target
                    try:
                        await bot.send_message_draft(
                            chat_id=chat_id, draft_id=draft_id, text=plain[:shown]
                        )
                    except TelegramRetryAfter as e:
                        logger.warning(
                            f"⚠️ Флуд-лимит на драфте, ждем {e.retry_after} сек"
                        )
                        await asyncio.sleep(e.retry_after)
                    except TelegramBadRequest as e:
                        # Драфт не критичен: текст все равно придет сообщением
                        logger.warning(f"⚠️ Драфт не обновился: {e}")

                if out_of_time or (stream_done and shown >= len(plain)):
                    break
            elif stream_done:
                break

            await asyncio.sleep(DRAFT_TICK)
    finally:
        # Дочитываем остаток потока, чтобы отправить полный ответ
        try:
            await reader_task
        except Exception as e:
            logger.error(f"🔴 Ошибка чтения стрима: {e}")

    if stream_error:
        logger.error(f"🔴 Стрим завершился с ошибкой: {stream_error}")

    if not raw_text.strip():
        await drop_placeholder()
        await bot.send_message(chat_id=chat_id, text=ERROR_TEXT)
        return ERROR_TEXT

    # Финальное сообщение с полным ответом — оно же убирает драфт
    try:
        await bot.send_message(chat_id=chat_id, text=raw_text, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e):
            clean_response = _plain(raw_text)
            await bot.send_message(chat_id=chat_id, text=clean_response)
            return clean_response
        raise

    return raw_text


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
            ...
            # logger.warning(
            #     f"Не удалось убрать клавиатуру у сообщения {tarot_msg_id}: {e}"
            # )


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


@router.callback_query(F.data == "back_to_subscription")
@handle_old_queries()
async def callback_back_to_subscription(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()

    await callback.message.edit_text(
        "<b>✨ Выберите свой путь:</b>\n\n"
        "🔹 <b>Получите ещё одно бесплатное гадание</b> — пригласите друга и раскрой новую возможность.\n"
        "🔹 <b>Получите безграничные возможности</b> — теперь вы можете гадать сколько угодно раз, каждый день, без ограничений.\n\n"
        f"💡 Сейчас вам доступно {await rq.caunt_taro(callback.from_user.id)} таро-гаданий.\n\n"
        "— Малина всегда с вами ❤️",
        reply_markup=kb.btn_attempts,
    )


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
            "🔹 <b>Получите безграничные возможности</b> — теперь вы можете гадать сколько угодно раз, каждый день, без ограничений.\n\n"
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

    stream = AI.generate_response_stream(
        text=data.get("text"),
        prompt="sleep",
    )
    await stream_to_draft(
        message.bot,
        message.from_user.id,
        stream,
        placeholder_id=msg.message_id,
    )
    await rq.update_statistic("requests_sonnic")

    logger.info(f"🌙 Сон пользователя: {data.get('text')}")


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
            "🔹 <b>Получите безграничные возможности</b> — теперь вы можете гадать сколько угодно раз, каждый день, без ограничений.\n\n"
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

            stream = AI.generate_response_stream(
                f"Вопрос: {question}\nКарты: {cards_list}",
                "cards_taro",
                continuation_response_text,
                question,
            )
        else:
            # Генерируем ответ
            stream = AI.generate_response_stream(
                text=f"Вопрос: {question}\nКарты: {cards_list}",
                prompt="cards_taro",
            )

        logger.info(
            f"""Пользователь: {user_id}.
            Карты: {cards_list}.
            Вопрос: {question}.
            ID сообщения: {message_id}."""
        )

        # Показываем трактовку «вживую»: драфт печатается по мере генерации,
        # в конце приходит обычное сообщение с полным текстом.
        # Сообщение с кнопкой выбора карт убираем, когда пришел первый кусочек
        response = await stream_to_draft(
            bot,
            user_id,
            stream,
            placeholder_id=message_id,
        )

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
                "🔹 <b>Получите безграничные возможности</b> — теперь вы можете гадать сколько угодно раз, каждый день, без ограничений.\n\n"
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
        await rq.update_statistic("requests_map_day")

        selected_card = random.choice(tarot_deck)
        file_id = file_id_cards[selected_card]

        async def send_card_photo():
            await callback.message.answer_photo(photo=file_id, parse_mode="HTML")

        stream = AI.generate_response_stream(
            text=f"Карта дня: {selected_card}",
            prompt="card_day",
        )

        await stream_to_draft(
            callback.bot,
            callback.from_user.id,
            stream,
            placeholder_id=msg.message_id,
            on_first_chunk=send_card_photo,
        )

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
        "🔹 <b>Получите безграничные возможности</b> — теперь вы можете гадать сколько угодно раз, каждый день, без ограничений.\n\n"
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

    await rq.update_statistic(
        "active_users", success_count + len(await rq.get_all_users()) - len(users)
    )

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

        mes_payment = await message.answer(subscription_text)
        await mes_payment.edit_reply_markup(
            reply_markup=kb.btn_web_payment(
                mes_payment.message_id, message.from_user.id
            )
        )


@router.callback_query(F.data == "subscription_message_all")
async def subscription_message_all(callback: CallbackQuery, state: FSMContext):
    """Обработчик команды /subscription."""

    await state.clear()
    await callback.answer()

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

        mes_payment = await callback.message.edit_text(
            subscription_text,
            disable_web_page_preview=True,
        )
        await mes_payment.edit_reply_markup(
            reply_markup=kb.btn_web_payment(
                mes_payment.message_id, callback.from_user.id, True
            )
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
