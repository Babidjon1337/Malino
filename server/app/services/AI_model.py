import re
import logging
from openai import *
import asyncio
import httpx

from config import AI_TOKEN, PROXY_URL
from app.others.text_message import prompt_data


class ChineseInResponseError(Exception):
    """Модель вернула китайские иероглифы — запрос нужно повторить."""


# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=AI_TOKEN,
    http_client=httpx.AsyncClient(proxy=PROXY_URL),
)


def contains_chinese(text: str) -> bool:
    """
    Проверяет, содержит ли строка хотя бы один китайский иероглиф.

    Охватывает:
    - Основной блок: U+4E00–U+9FFF
    - Расширение A: U+3400–U+4DBF
    - Расширения B–G: U+20000–U+2EBEF (включая Supplementary Ideographic Plane)

    Возвращает:
        True — если найден хотя бы один китайский символ,
        False — иначе.
    """
    if not isinstance(text, str):
        return False

    # Регулярное выражение для всех известных китайских иероглифов
    chinese_pattern = re.compile(
        r"[\u4e00-\u9fff"  # Основной блок
        r"\u3400-\u4dbf"  # Расширение A
        r"\U00020000-\U0002a6df"  # Расширение B
        r"\U0002a700-\U0002b73f"  # Расширение C
        r"\U0002b740-\U0002b81f"  # Расширение D
        r"\U0002b820-\U0002ceaf"  # Расширение E, F, G (частично)
        r"]"
    )
    return bool(chinese_pattern.search(text))


def message_prompt(text: str, prompt: str, args_list: list) -> dict:
    system_prompt = prompt_data[prompt]

    if len(args_list) == 0:
        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": text,
            },
        ]

    elif len(args_list) == 2:
        messages = [
            {
                "role": "user",
                "content": args_list[0],
            },
            {
                "role": "assistant",
                "content": args_list[1],
            },
            {
                "role": "user",
                "content": f"{system_prompt}\n\n{text}",
            },
        ]
    return messages


_THINK_OPEN = "<think>"


def _visible_text(raw: str) -> str:
    """
    Убирает из сырого текста стрима блоки размышлений <think>...</think>
    и заменяет <br> на переносы строк. Человек не должен увидеть ни сами
    размышления, ни огрызки тега, который приходит из стрима по частям
    (например "<th" или "<think" — пока закрывающий ">" еще не доехал).
    """
    # 1. Убираем полностью закрытые блоки размышлений
    txt = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE)

    # 2. Незакрытый <think> — модель еще размышляет, прячем всё после него
    idx = txt.lower().rfind(_THINK_OPEN)
    if idx != -1:
        txt = txt[:idx]

    # 3. Висячий закрывающий тег без открывающего (бывает у некоторых провайдеров)
    txt = re.sub(r"</think>", "", txt, flags=re.IGNORECASE)

    # 4. Частичный открывающий тег в конце потока ("<th", "<think" и т.п.)
    #    прячем до тех пор, пока тег не соберется целиком (или не окажется
    #    обычным текстом — тогда он вернется в следующем обновлении)
    for k in range(min(len(txt), len(_THINK_OPEN)), 0, -1):
        if _THINK_OPEN.startswith(txt[-k:].lower()):
            txt = txt[:-k]
            break

    return txt.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")


async def generate_response_stream(text, prompt, *args):
    """
    Асинхронный генератор: по мере генерации отдает накопленный чистый
    текст ответа (без <think> и <br>).

    - OpenRouter сам выбирает лучший провайдер по скорости (без modal/fp8)
      и переключается на другой при ошибке (allow_fallbacks=True)
    - ретраи только до первого кусочка текста (иначе текст задвоится)
    - китайские иероглифы проверяются до первого показа: при находке запрос
      повторяется; если стрим уже пошел — генерация просто обрывается
    """
    args_list = list(args)

    max_retries = 4  # Всего 4 попытки

    # Провайдеры, которые нельзя использовать
    ignored_providers = ["modal/fp8"]

    for attempt in range(max_retries):
        yielded = False  # Уже отдали кусочек текста наружу?
        raw_parts: list[str] = []

        try:
            stream = await client.chat.completions.create(
                model="z-ai/glm-5.3-flash",
                messages=message_prompt(text, prompt, args_list),
                extra_body={
                    "provider": {
                        "ignore": ignored_providers,
                        "sort": "throughput",
                        "allow_fallbacks": True,
                    },
                    # Модель может думать, но размышления не попадают в ответ
                    "reasoning": {
                        "exclude": True,
                    },
                },
                extra_headers={
                    "HTTP-Referer": "https://malinaezo.ru/",
                    "X-Title": "Malina bot",
                },
                temperature=0.5,
                stream=True,
            )

            async for chunk in stream:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                if not content:
                    continue
                raw_parts.append(content)

                visible = _visible_text("".join(raw_parts)).strip()
                if not visible:
                    continue  # Модель пока только размышляет (<think>)

                # Проверка на китайские иероглифы до первого показа
                if contains_chinese(visible):
                    if yielded:
                        logger.warning("⚠️ Стрим: китайский иероглиф в середине ответа — обрываю")
                        return
                    raise ChineseInResponseError()

                yielded = True
                yield visible

            if not yielded:
                logger.warning("⚠️ Стрим: пустой ответ от API")
            return

        except ChineseInResponseError:
            if attempt < max_retries - 1:
                wait_time = 2 ** (attempt + 2)  # 4, 8, 16 секунды
                logger.warning(
                    f"⚠️ Стрим: китайский иероглиф. 北京是中国的首都\nЖдем {wait_time} сек и перезапрашиваем"
                )
                await asyncio.sleep(wait_time)
                continue
            logger.error("🔴 Стрим: китайский иероглиф после всех попыток. 北京是中国的首都")
            return

        except AuthenticationError as e:
            # 401: ключ недействителен — повторять бессмысленно
            logger.error(
                f"🔴 OpenRouter: неверный API-ключ (401). Проверьте AI_TOKEN в .env: {e}"
            )
            return

        except RateLimitError as e:
            if yielded:
                logger.error(f"🔴 Стрим прерван лимитом запросов: {e}")
                return
            if attempt < max_retries - 1:
                wait_time = 2 ** (attempt + 3)  # 8, 16, 32 секунды
                logger.warning(
                    f"⚠️ Лимит запросов. Ждем {wait_time} секунд перед повторной попыткой..."
                )
                await asyncio.sleep(wait_time)
                continue
            logger.error("🔴 Лимит запросов после всех попыток")
            return

        except Exception as e:
            if yielded:
                # Часть текста уже отдана — перезапрос задвоил бы его
                logger.error(f"🔴 Стрим прервался после начала генерации: {e}")
                return
            if attempt < max_retries - 1:
                wait_time = 2 ** (attempt + 1)
                logger.warning(
                    f"⚠️ Ошибка стрима. Ждем {wait_time} секунд... {e}"
                )
                await asyncio.sleep(wait_time)
                continue
            logger.error(f"🔴 Стрим не удался после всех попыток: {e}")
            return
