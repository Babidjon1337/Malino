import logging
import asyncio
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import app.keyboards as kb
import app.database.requests as rq


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


admin_router = Router()


ADMINS = [932050484, 1186592191, 983660321]


class MessageAllUsersState(StatesGroup):
    Admin_text = State()


@admin_router.message(Command("admin"))
async def command_admin(message: Message, state: FSMContext):
    """Получение статистики для Админа"""
    await state.clear()

    if message.from_user.id in ADMINS:

        users_count, subscriptions_count = await rq.get_statistics()

        await message.answer(
            "<b>Админ-панель</b>\n\n"
            "<b>📊 Статистика</b>\n"
            f"👥 Всего пользователей: {users_count}\n"
            f"💸 Подписок: {subscriptions_count}",
            reply_markup=kb.admin_keyboard,
        )
    else:
        pass


@admin_router.callback_query(F.data == "back_admin")
async def callback_cansel_send_all_users(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()

    if callback.from_user.id in ADMINS:

        users_count, subscriptions_count = await rq.get_statistics()

        await callback.message.edit_text(
            "<b>Админ-панель</b>\n\n"
            "<b>📊 Статистика</b>\n"
            f"👥 Всего пользователей: {users_count}\n"
            f"💸 Подписок: {subscriptions_count}",
            reply_markup=kb.admin_keyboard,
        )
    else:
        pass


@admin_router.callback_query(F.data == "admin_message_all_users")
async def callback_all_users(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    send_message = await callback.message.edit_text(
        "Введите сообщение для рассылки всем пользователям:",
        reply_markup=kb.btn_back_admin,
    )
    await state.update_data(send_message=send_message)
    await state.set_state(MessageAllUsersState.Admin_text)


@admin_router.message(MessageAllUsersState.Admin_text)
async def process_message_all_users(message: Message, state: FSMContext):
    """Отправляет (сообщение, сообщение+фото, сообщение+Gif, Кружок телеграм) всем пользователям"""
    await state.update_data(Admin_text=message)

    data = await state.get_data()
    send_message: Message = data.get("send_message")

    await send_message.edit_reply_markup(reply_markup=None)

    if message.from_user.id in ADMINS:
        await message.answer(
            "Отправить данное сообщение <b>всем пользователям</b>?",
            reply_markup=kb.btn_send_msg,
        )


@admin_router.callback_query(F.data == "to_send")
async def callback_to_send_all_users(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if callback.from_user.id in ADMINS:
        data = await state.get_data()
        text: Message = data.get("Admin_text")

        await text.delete()
        await callback.message.delete()

        users = await rq.get_all_users()
        # users = [1186592191, 7469479410, 23434234, 2342432]  # Тестовые ID
        success_count = 0
        fail_count = 0

        progress_msg = await callback.message.answer(
            f"📤 Начинаю рассылку для {len(users)} пользователей..."
        )

        # Обработка разных типов контента
        for user_id in users:
            user_id = user_id.telegram_id
            try:
                # Текстовое сообщение
                if text.text and not (text.photo or text.animation or text.video_note):
                    await callback.bot.send_message(
                        user_id,
                        text.text,
                        disable_web_page_preview=True,
                    )

                # Фото с текстом или без
                elif text.photo:
                    photo = text.photo[-1]  # Берем фото наивысшего качества
                    caption = text.caption if text.caption else None
                    await callback.bot.send_photo(
                        chat_id=user_id,
                        photo=photo.file_id,
                        caption=caption,
                    )

                # GIF анимация с текстом или без
                elif text.animation:
                    caption = text.caption if text.caption else None
                    await callback.bot.send_animation(
                        chat_id=user_id,
                        animation=text.animation.file_id,
                        caption=caption,
                    )

                # Видео-кружок
                elif text.video_note:
                    await callback.bot.send_video_note(
                        chat_id=user_id, video_note=text.video_note.file_id
                    )
                    # Отправляем подпись отдельным сообщением, если есть
                    if text.caption:
                        await asyncio.sleep(0.1)  # Небольшая задержка
                        await callback.bot.send_message(
                            user_id,
                            text.caption,
                        )

                else:
                    await callback.message.answer("❌ Неподдерживаемый тип сообщения.")
                    await progress_msg.delete()
                    await state.clear()
                    return

                success_count += 1
                await asyncio.sleep(0.09)  # Задержка чтобы не превысить лимиты Telegram

            except Exception:
                fail_count += 1

        await progress_msg.edit_text(
            f"📤 <b>Рассылка завершена!</b>\n\n"
            f"📊 Всего пользователей: {len(users)}\n"
            f"✅ Успешно: {success_count}\n"
            f"❌ Не удалось: {fail_count}"
        )
        await state.clear()


@admin_router.message(F.animation | F.photo | F.video)
async def message_file_id(message: Message):
    if message.from_user.id == 1186592191:
        if message.photo:
            await message.answer(message.photo[-1].file_id)
        elif message.video:
            await message.answer(message.video.file_id)
        elif message.animation:
            await message.answer(message.animation.file_id)
