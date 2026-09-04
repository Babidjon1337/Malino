import re
import html
import time
import random
import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

logger = logging.getLogger(__name__)

# Драфт — «живая» печать ответа. Телеграм держит драфт как 30-секундный
# превью, поэтому весь текст нужно успеть напечатать за это окно.
DRAFT_TICK = 0.7  # как часто обновляем драфт, сек
DRAFT_MIN_CHARS = 60  # минимум символов за тик (темп для коротких ответов)
DRAFT_TOTAL_SECONDS = 20  # за столько секунд печать должна закончиться
PLACEHOLDER_TICK = 1.5  # с каким шагом крутим анимацию сообщения-заглушки

ERROR_TEXT = "В данный момент эта функция не доступна 😢\nПожалуйста, попробуйте позже."


def typing_frames(first_line: str, second_line: str) -> list[str]:
    """
    Кадры анимации «печатает...» для сообщения-заглушки:
    к первой строке добавляются точки 0-3, вторая строка статична.
    """
    return [
        f"{first_line}{dots}\n{second_line}" for dots in ("", ".", "..", "...")
    ]


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


async def _animate_placeholder(
    bot: Bot, chat_id: int, message_id: int, frames: list[str]
):
    """Крутит кадры анимации в сообщении-заглушке, пока его не удалят."""
    i = 0
    while True:
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=frames[i % len(frames)]
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                pass  # такой же кадр — просто пропускаем
            else:
                return  # сообщение удалили или оно недоступно
        except Exception:
            return
        i += 1
        await asyncio.sleep(PLACEHOLDER_TICK)


async def stream_to_draft(
    bot: Bot,
    chat_id: int,
    agen,
    placeholder_id: int | None = None,
    placeholder_frames: list[str] | None = None,
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

    - placeholder_id — сообщение «генерирую...»; убирается на первом кусочке
    - placeholder_frames — кадры анимации для этого сообщения (typing_frames)
    - on_first_chunk — корутина, вызывается на первом кусочке (например, фото карты)
    - возвращает финальный текст ответа (или ERROR_TEXT при сбое)
    """
    draft_id = random.randint(1, 1_000_000)
    raw_text = ""  # последний накопленный ответ (с HTML-разметкой)
    stream_done = False
    stream_error = None
    animator = None

    if placeholder_frames and placeholder_id is not None:
        animator = asyncio.create_task(
            _animate_placeholder(bot, chat_id, placeholder_id, placeholder_frames)
        )

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
        nonlocal placeholder_id, animator
        if animator is not None:
            animator.cancel()
            animator = None
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
                # Первый кусочек текста: останавливаем анимацию, убираем заглушку
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
                        # parse_mode=None: драфт показывает чистый текст;
                        # в новых aiogram драфт иначе наследует HTML-дефолт бота,
                        # и незакрытые/случайные теги ломали бы обновление
                        await bot.send_message_draft(
                            chat_id=chat_id,
                            draft_id=draft_id,
                            text=plain[:shown],
                            parse_mode=None,
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
        if animator is not None:
            animator.cancel()
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
