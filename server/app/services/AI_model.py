import re
import logging
from openai import *
import asyncio

from config import AI_TOKEN
from app.others.text_message import prompt_data


# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

client = AsyncClient(
    base_url="https://openrouter.ai/api/v1",
    api_key=AI_TOKEN,
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
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": text,
            },
        ]
    return messages


async def generate_response(text, prompt, *args):
    args_list = list(args)

    max_retries = 4  # Всего 3 попытки

    providers = [
        "baseten",
        "fireworks",
        "friendli",
        "together",
        "nebius",
        "parasail",
    ]
    for attempt in range(max_retries):
        try:

            completion = await client.chat.completions.create(
                model="qwen/qwen3-235b-a22b-2507",
                # model="deepseek/deepseek-chat-v3-0324",
                # model="deepseek/deepseek-chat-v3-0324:free",
                messages=message_prompt(text, prompt, args_list),
                extra_body={
                    "provider": {
                        "only": providers,
                        "sort": "throughput",
                        "allow_fallbacks": False,
                    },
                },
                extra_headers={
                    "HTTP-Referer": "https://malinaezo.ru/",
                    "X-Title": "Malina bot",
                },
                temperature=0.5,  # Минимум креативности
                # frequency_penalty=0.2,  # Штрафует модель за повторение одних и тех же слов
                # presence_penalty=0.3,  # Поощряет модель вводить новые темы и идеи
            )
            if completion is None:
                logger.error("OpenRouter API вернул None")
                if attempt < max_retries - 1:
                    continue
                return "В данный момент эта функция не доступна 😢\nПожалуйста, попробуйте позже."

            if not completion.choices:
                logger.error("Список choices пуст в ответе API")
                if attempt < max_retries - 1:
                    continue
                return "В данный момент эта функция не доступна 😢\nПожалуйста, попробуйте позже."

            response = completion.choices[0].message.content

            response = (
                response.replace("<br>", "\n")
                .replace("<br/>", "\n")
                .replace("<br />", "\n")
            )

            # Проверка на символы <think>...</think>
            if "<think>" in response:
                return re.sub(
                    r"<think>.*?</think>", "", response, flags=re.DOTALL | re.IGNORECASE
                ).strip()

            # Проверяем, что completion не None и содержит ожидаемую структуру
            # fmt: off
            if not response or not isinstance(response, str) or len(response.strip()) == 0:
            # fmt: on
                logger.error("OpenRouter API возвращенная структура неожиданного ответа")
                continue
            
            # Проверяет, содержит ли строка хотя бы один китайский иероглиф. 北京是中国的首都
            if contains_chinese(response):
                if attempt < max_retries - 1:  # Не ждем после последней попытки
                    wait_time = 2 ** (attempt + 2)  # 2, 4, 8, 16 секунды
                    logger.warning(
                        "Найдены китайский иероглиф. 北京是中国的首都\nПовторная попытка"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error("Найдены китайский иероглиф. 北京是中国的首都")
                    return "В данный момент эта функция не доступна 😢\nПожалуйста, попробуйте позже."

            return response

        except RateLimitError as e:
            if attempt < max_retries - 1:  # Не ждем после последней попытки
                wait_time = 2 ** (attempt + 3)  # 8, 16, 32, 64 секунды
                logger.warning(
                    f"Лимит запросов. Ждем {wait_time} секунд перед повторной попыткой..."
                )
                await asyncio.sleep(wait_time)
                continue
            else:
                print(
                    "Слишком много запросов. Пожалуйста, попробуйте через несколько минут."
                )
                return "В данный момент эта функция не доступна 😢\nПожалуйста, попробуйте позже."

        except APITimeoutError as e:
            # Обработка таймаута
            if attempt < max_retries - 1:
                wait_time = 2 ** (attempt + 1)
                logger.warning(f"Таймаут запроса. Ждем {wait_time} секунд...")
                await asyncio.sleep(wait_time)
                continue
            else:
                logger.error("Таймаут после всех попыток")
                return "В данный момент эта функция не доступна 😢\nПожалуйста, попробуйте позже."

        except APIError as e:
            error_message = str(e).lower()

            # Проверяем, связана ли ошибка с конкретным провайдером
            for provider in providers[:]:  # Используем копию для безопасного удаления
                if provider.lower() in error_message:
                    logger.warning(
                        f"Обнаружена проблема с провайдером {provider}, удаляем из списка"
                    )
                    providers.remove(provider)
                    continue

            # Если провайдеры закончились, сразу возвращаем ошибку
            if not providers:
                logger.error("Все провайдеры исключены из-за ошибок")
                return "В данный момент эта функция не доступна 😢\nПожалуйста, попробуйте позже."

            if attempt < max_retries - 1:
                wait_time = 2 ** (attempt + 1)
                logger.warning(
                    f"Ошибка API. Ждем {wait_time} секунд... Доступно провайдеров: {len(providers)}"
                )
                await asyncio.sleep(wait_time)
                continue
            else:
                logger.error(f"Ошибка API после всех попыток: {str(e)}")
                return "В данный момент эта функция не доступна 😢\nПожалуйста, попробуйте позже."
        except AttributeError as e:
            if "'NoneType' object" in str(e):
                logger.error(
                    f"Обнаружена ошибка NoneType на попытке {attempt + 1}: {e}"
                )
                if attempt < max_retries - 1:
                    continue
                return "В данный момент эта функция не доступна 😢\nПожалуйста, попробуйте позже."
            else:
                raise e

        except Exception as e:
            # Обработка всех остальных исключений
            logger.error(f"Неожиданная ошибка на попытке {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = 2 ** (attempt + 1)
                await asyncio.sleep(wait_time)
                continue
            return "В данный момент эта функция не доступна 😢\nПожалуйста, попробуйте позже."
