import logging
import asyncio
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

import app.keyboards as kb
import app.database.requests as rq


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


admin_router = Router()


ADMINS = [932050484, 1186592191, 983660321]


class MessageAllUsersState(StatesGroup):
    Admin_text = State()


class NewPromoCode(StatesGroup):
    day = State()


@admin_router.message(Command("admin"))
async def command_admin(message: Message, state: FSMContext):
    """Получение статистики для Админа"""
    await state.clear()

    if message.from_user.id in ADMINS:

        await message.answer(
            "<b>Админ-панель</b>",
            reply_markup=kb.admin_keyboard,
        )


@admin_router.callback_query(F.data == "back_admin")
async def callback_cansel_send_all_users(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()

    if callback.from_user.id in ADMINS:

        try:
            await callback.message.edit_text(
                "<b>Админ-панель</b>",
                reply_markup=kb.admin_keyboard,
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise


@admin_router.callback_query(F.data == "admin_message_all_users")
async def callback_all_users(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()

    send_message_admin = await callback.message.edit_text(
        "Введите сообщение для рассылки всем пользователям:\n\n"
        "📎 Можно отправить:\n"
        "• 📝 Текст\n"
        "• 📷 Фото (одиночное или несколько) + Текст\n"
        "• 🎬 GIF + Текст\n"
        "• 🎥 Видео-кружок",
        reply_markup=kb.btn_back_admin,
    )
    await state.update_data(send_message_admin=send_message_admin)
    await state.set_state(MessageAllUsersState.Admin_text)


# Хранилище для медиагрупп
media_groups = {}


@admin_router.message(MessageAllUsersState.Admin_text, F.media_group_id)
async def process_media_group(message: Message, state: FSMContext):
    media_group_id = message.media_group_id

    # Удаляем клавиатуру у предыдущего сообщения
    data = await state.get_data()
    send_message_admin: Message = data.get("send_message_admin")

    try:
        await send_message_admin.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    if media_group_id not in media_groups:
        media_groups[media_group_id] = []

        # ✅ запускаем обработку ОТДЕЛЬНОМ ФОНОВЫМ ПОТОКОМ
        asyncio.create_task(process_album_after_delay(media_group_id, state, message))

    # ✅ СРАЗУ добавляем фото
    media_groups[media_group_id].append(message)


async def process_album_after_delay(
    media_group_id, state: FSMContext, message: Message
):
    await asyncio.sleep(1.2)

    messages = media_groups.get(media_group_id)
    if not messages:
        return

    await state.update_data(Admin_text=messages, is_album=True)

    await message.answer(
        f"📸 Получен альбом из {len(messages)} фото.\n"
        "Добавить кнопку 'Купить подписку ✨' под сообщением?",
        reply_markup=kb.btn_need_button_simple,
    )

    del media_groups[media_group_id]


@admin_router.message(MessageAllUsersState.Admin_text)
async def process_single_message(message: Message, state: FSMContext):
    """Обработка одиночных сообщений (текст, одно фото, гифка, видео-кружок)"""
    # Проверяем, что это не часть медиагруппы (на всякий случай)
    if message.media_group_id:
        return

    # Сохраняем сообщение
    await state.update_data(Admin_text=message, is_album=False)

    # Удаляем клавиатуру у предыдущего сообщения
    data = await state.get_data()
    send_message_admin: Message = data.get("send_message_admin")

    try:
        await send_message_admin.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    # Спрашиваем про кнопку
    if message.text:
        preview = f"📝 Текст: {message.text[:100]}..."
    elif message.photo:
        preview = "📷 Фото"
    elif message.animation:
        preview = "🎬 GIF"
    elif message.video_note:
        preview = "🎥 Видео-кружок"
    else:
        preview = "Сообщение"

    await message.answer(
        f"{preview}\n\n" "Добавить кнопку 'Купить подписку ✨' под сообщением?",
        reply_markup=kb.btn_need_button_simple,
    )


@admin_router.callback_query(F.data.in_(["btn_yes", "btn_no"]))
async def show_preview(callback: CallbackQuery, state: FSMContext):
    """Показ предпросмотра"""
    await callback.answer()

    data = await state.get_data()
    admin_text = data.get("Admin_text")
    is_album = data.get("is_album", False)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    btn_text = (
        " <u>с кнопкой</u>" if callback.data == "btn_yes" else " <u>без кнопки</u>"
    )

    if is_album:
        # Для альбома
        first_photo = admin_text[0]
        caption = first_photo.caption or ""

        if caption:
            preview_text = f"📸 Альбом из {len(admin_text)} фото\n{caption[:100]}..."
        else:
            preview_text = f"📸 Альбом из {len(admin_text)} фото"

        await callback.message.answer_photo(
            photo=first_photo.photo[-1].file_id,
            caption=f"{preview_text}\n\n"
            f"Отправить данное сообщение <b>всем пользователям</b>{btn_text}?",
            reply_markup=kb.btn_send_msg,
        )
    else:
        # Для одиночного сообщения
        if admin_text.text:
            await callback.message.answer(
                f"📝 Сообщение\n\n"
                f"{admin_text.text}\n\n"
                f"Отправить данное сообщение <b>всем пользователям</b>{btn_text}?",
                reply_markup=kb.btn_send_msg,
                disable_web_page_preview=True,
            )
        elif admin_text.photo:
            caption = admin_text.caption or ""
            await callback.message.answer_photo(
                photo=admin_text.photo[-1].file_id,
                caption=f"{caption[:100]}\n\n"
                f"Отправить данное сообщение <b>всем пользователям</b>{btn_text}?",
                reply_markup=kb.btn_send_msg,
            )
        elif admin_text.animation:
            caption = admin_text.caption or ""
            await callback.message.answer_animation(
                animation=admin_text.animation.file_id,
                caption=f"{caption[:100]}\n\n"
                f"Отправить данное сообщение <b>всем пользователям</b>{btn_text}?",
                reply_markup=kb.btn_send_msg,
            )
        elif admin_text.video_note:
            await callback.message.answer(
                f"🎥 Видео-кружок\n\n"
                f"Отправить данное сообщение <b>всем пользователям</b>{btn_text}?",
                reply_markup=kb.btn_send_msg,
            )

    # Сохраняем выбор
    need_button = callback.data == "btn_yes"
    await state.update_data(need_button=need_button)


@admin_router.callback_query(F.data == "to_send")
async def callback_to_send_all_users(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if callback.from_user.id in ADMINS:
        data = await state.get_data()
        admin_text = data.get("Admin_text")
        need_button = data.get("need_button", False)
        is_album = data.get("is_album", False)

        # Определяем клавиатуру
        reply_markup = kb.btn_buy_subscription if need_button else None

        # Удаляем сообщения предпросмотра
        try:
            await callback.message.delete()
        except:
            pass

        users = await rq.get_all_users()
        success_count = 0
        fail_count = 0

        await callback.message.answer(
            f"📤 Начинаю рассылку для {len(users)} пользователей..."
        )

        # Обработка разных типов контента
        for user in users:
            user_id = user.telegram_id
            try:
                # Если это альбом
                if is_album:
                    # Создаем медиагруппу
                    media = []
                    for i, msg in enumerate(admin_text):
                        if msg.photo:
                            photo = msg.photo[-1]
                            # Для первого фото добавляем подпись, если есть
                            caption = msg.caption if i == 0 and msg.caption else None
                            media.append(
                                InputMediaPhoto(media=photo.file_id, caption=caption)
                            )

                    if media:
                        await callback.bot.send_media_group(
                            chat_id=user_id, media=media
                        )

                        if reply_markup:
                            await asyncio.sleep(0.07)
                            await callback.bot.send_message(
                                user_id,
                                "👇 Нажмите кнопку ниже:",
                                reply_markup=reply_markup,
                            )

                # Текстовое сообщение
                elif admin_text.text:
                    await callback.bot.send_message(
                        user_id,
                        admin_text.text,
                        disable_web_page_preview=True,
                        reply_markup=reply_markup,
                    )

                # Одиночное фото
                elif admin_text.photo:
                    photo = admin_text.photo[-1]
                    caption = admin_text.caption if admin_text.caption else None
                    await callback.bot.send_photo(
                        chat_id=user_id,
                        photo=photo.file_id,
                        caption=caption,
                        reply_markup=reply_markup,
                    )

                # GIF
                elif admin_text.animation:
                    caption = admin_text.caption if admin_text.caption else None
                    await callback.bot.send_animation(
                        chat_id=user_id,
                        animation=admin_text.animation.file_id,
                        caption=caption,
                        reply_markup=reply_markup,
                    )

                # Видео-кружок
                elif admin_text.video_note:
                    await callback.bot.send_video_note(
                        chat_id=user_id, video_note=admin_text.video_note.file_id
                    )
                    if admin_text.caption or reply_markup:
                        await asyncio.sleep(0.07)
                        await callback.bot.send_message(
                            user_id,
                            admin_text.caption if admin_text.caption else " ",
                            reply_markup=reply_markup,
                        )

                success_count += 1
                await asyncio.sleep(0.05)

            except Exception as e:
                if not (
                    isinstance(e, TelegramBadRequest)
                    and "bot was blocked by the user" in str(e)
                ):
                    logger.info(f"Пользователь {user_id} заблокировал бота.")
                fail_count += 1

        await callback.message.answer(
            f"📤 <b>Рассылка завершена!</b>\n\n"
            f"📊 Всего пользователей: {len(users)}\n"
            f"✅ Успешно: {success_count}\n"
            f"❌ Не удалось: {fail_count}"
        )
        await state.clear()

        # Удаляем исходные сообщения
        try:
            if is_album:
                for msg in admin_text:
                    try:
                        await msg.delete()
                    except:
                        pass
            else:
                try:
                    await admin_text.delete()
                except:
                    pass
        except:
            pass


@admin_router.callback_query(F.data == "admin_promo_codes")
async def callback_promo_codes(callback: CallbackQuery):
    await callback.answer()

    PromoCodes = await rq.get_all_promo_codes()

    if PromoCodes:
        result = (
            "\n".join(
                [
                    f"<code>https://t.me/malina_ezo_bot?start={item.code}</code>\n"
                    f"Дней: <b>{item.days}</b>\n"
                    f"Действует до: <b>{item.valid_before.strftime('%d.%m.%Y')}</b>\n"
                    for item in PromoCodes
                ]
            )
            + "\n"
        )
    else:
        result = "Пока тут пусто..."

    await callback.message.edit_text(
        f"<b>🎟 Промокоды</b>\n\n{result}",
        disable_web_page_preview=True,
        reply_markup=kb.btn_promo_code,
    )


@admin_router.callback_query(F.data == "new_promo_code")
async def callback_new_promo_code(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    send_message = await callback.message.edit_text(
        "Укажите срок действия промокода в днях <i>(Укажите только число)</i>",
        reply_markup=kb.btn_back_admin,
    )
    await state.update_data(send_message_id=send_message.message_id)
    await state.set_state(NewPromoCode.day)


@admin_router.message(NewPromoCode.day)
async def process_promo_code_day(message: Message, state: FSMContext):
    await message.delete()

    send_message_id = await state.get_value("send_message_id")
    try:
        day = int(message.text)

        PromoCode = await rq.create_promo_code(day)

        await message.bot.edit_message_text(
            chat_id=message.from_user.id,
            message_id=send_message_id,
            text=(
                "🆕 Промокод создан: \n"
                f"<code>https://t.me/malina_ezo_bot?start={PromoCode.get('code')}</code>\n"
                f"Дней: <b>{PromoCode.get('days')}</b>\n"
                f"Действует до: <b>{PromoCode.get('valid_before').strftime('%d.%m.%Y')}</b>"
            ),
            disable_web_page_preview=True,
            reply_markup=kb.btn_back_admin,
        )
        await state.clear()
    except ValueError:
        try:
            await message.bot.edit_message_text(
                chat_id=message.from_user.id,
                message_id=send_message_id,
                text=(
                    "Укажите срок действия промокода в днях <i>(Укажите только число)</i>\n\n"
                    "❗️ Ошибка, укажите <b>цифру</b>"
                ),
                reply_markup=kb.btn_back_admin,
            )
        except:
            pass


@admin_router.message(F.animation | F.photo | F.video)
async def message_file_id(message: Message):
    if message.from_user.id == 1186592191:
        if message.photo:
            await message.answer(message.photo[-1].file_id)
        elif message.video:
            await message.answer(message.video.file_id)
        elif message.animation:
            await message.answer(message.animation.file_id)
