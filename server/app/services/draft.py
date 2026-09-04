import re
import html
import time
import random
import asyncio
import logging
import contextlib

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

logger = logging.getLogger(__name__)

# Драфт — «живая» печать ответа. Телеграм держит драфт как 30-секундный
# превью, поэтому весь текст нужно успеть напечатать за это окно.
DRAFT_TICK = 0.6  # как часто обновляем драфт, сек
DRAFT_MIN_CHARS = 60  # минимум символов за тик (темп для коротких ответов)
DRAFT_TOTAL_SECONDS = 20  # за столько секунд печать должна закончиться
# Печать кадров ожидания: буквы добавляются мелкими шагами, потом кадр
# «держится» и начинается следующий.
WAIT_TYPE_TICK = 0.35  # шаг печати букв в кадре ожидания, сек
WAIT_TYPE_CHARS = 8  # сколько символов добавляем за шаг
WAIT_HOLD = 1  # держим допечатанный кадр перед следующим

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


async def _animate_wait_draft(bot: Bot, chat_id: int, draft_id: int, frames: list[str]):
    """
    Печатает кадры ожидания по буквам (мелкими шагами), держит готовый кадр
    и переходит к следующему. Тот же draft_id, что и для ответа — переход
    «ждём → печатаем» остаётся плавным, без лишних сообщений.
    """
    i = 0
    while True:
        frame = frames[i % len(frames)]
        # печать кадра маленькими кусочками
        pos = 0
        while pos < len(frame):
            pos = min(len(frame), pos + WAIT_TYPE_CHARS)
            try:
                await bot.send_message_draft(
                    chat_id=chat_id,
                    draft_id=draft_id,
                    text=frame[:pos],
                    parse_mode=None,
                )
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
            except Exception:
                return
            await asyncio.sleep(WAIT_TYPE_TICK)
        # держим допечатанный кадр перед следующим
        await asyncio.sleep(WAIT_HOLD)
        i += 1


async def stream_to_draft(
    bot: Bot,
    chat_id: int,
    agen,
    wait_frames: list[str] | None = None,
    on_first_chunk=None,
    new_draft_after_first: bool = False,
) -> str:
    """
    Показывает ответ AI «вживую» одним драфтом:
    1) пока ждем первый токен — драфт крутит кадры ожидания (wait_frames);
    2) как только текст пошел — в тот же драфт ровно печатается ответ;
    3) в конце приходит обычное сообщение с полным ответом — оно убирает драфт.

    Модель генерирует в разы быстрее, чем человек читает, поэтому темп
    показа задают тики, а не скорость провайдера: на каждом тике остаток
    делится на число оставшихся тиков до DRAFT_TOTAL_SECONDS. Так печать
    идет плавно и всегда успевает закончиться внутри 30-секундного окна.

    - wait_frames — кадры ожидания (sleep_wait_frames / tarot_wait_frames /
      card_day_wait_frames из text_message.py)
    - on_first_chunk — корутина, вызывается на первом кусочке (например, фото карты)
    - возвращает финальный текст ответа (или ERROR_TEXT при сбое)
    """
    draft_id = random.randint(1, 1_000_000)
    raw_text = ""  # последний накопленный ответ (с HTML-разметкой)
    stream_done = False
    stream_error = None
    animator = None

    if wait_frames:
        animator = asyncio.create_task(
            _animate_wait_draft(bot, chat_id, draft_id, wait_frames)
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

    async def stop_animator():
        nonlocal animator
        if animator is not None:
            animator.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await animator
            animator = None

    reader_task = asyncio.create_task(reader())
    shown = 0
    started = None

    try:
        while True:
            plain = _plain(raw_text).strip()

            if plain and started is None:
                # Первый кусочек: останавливаем ожидание и забираем драфт себе
                started = time.monotonic()
                await stop_animator()
                if on_first_chunk is not None:
                    try:
                        await on_first_chunk()
                    except Exception:
                        logger.exception("⚠️ on_first_chunk упал (не критично)")
                    on_first_chunk = None
                    # on_first_chunk (например, фото карты) отправил сообщение —
                    # оно сбросило драфт ожидания. Берём новый draft_id, чтобы
                    # ответ печатался уже ПОД фото, а не над ним.
                    if new_draft_after_first:
                        draft_id = random.randint(1, 1_000_000)

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
                        # иначе драфт наследует HTML-дефолт бота, и
                        # незакрытые/случайные теги ломали бы обновление
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
        await stop_animator()
        # Дочитываем остаток потока, чтобы отправить полный ответ
        try:
            await reader_task
        except Exception as e:
            logger.error(f"🔴 Ошибка чтения стрима: {e}")

    if stream_error:
        logger.error(f"🔴 Стрим завершился с ошибкой: {stream_error}")

    if not raw_text.strip():
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
