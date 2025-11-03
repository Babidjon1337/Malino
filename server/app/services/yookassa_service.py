import logging
import uuid
from yookassa import Configuration, Payment
from yookassa.domain.exceptions import BadRequestError

from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, AMOUNT_1, AMOUNT_2

logger = logging.getLogger(__name__)


class YooKassaService:
    """
    Сервис для взаимодействия с YooKassa API.
    Реализует функциональность регулярных платежей и автоматического выставления счетов.
    """

    def __init__(self):
        """
        Инициализация с учетными данными ЮKassa.

        Args:
            account_id: ID магазина в ЮKassa
            secret_key: Секретный ключ
        """
        Configuration.account_id = YOOKASSA_SHOP_ID
        Configuration.secret_key = YOOKASSA_SECRET_KEY
        logger.info("PaymentProcessor инициализирован")

    # Изменино
    async def create_payment_link(
        self,
        user_id: int,
        message_id: int,
        amount: str,
        email: str,
    ):
        """
        Создает платеж с сохранением способа оплаты для будущих автосписаний.

        Args:
            user_id: ID пользователя
            message_id: ID сообщения для возврата после оплаты


        Returns:
            dict: Данные платежа с confirmation_url
        """
        try:

            payment_data = {
                "amount": {
                    "value": amount,  # ЗАМЕНИТЬ
                    "currency": "RUB",
                },
                "payment_method_data": {
                    "type": "bank_card",
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://t.me/malina_ezo_bot",
                },
                "capture": True,
                "description": "🔮 Подписка на безлимит Malina",
                "save_payment_method": True,  # Сохраняем способ оплаты
                "metadata": {
                    "user_id": user_id,
                    "message_id": message_id,
                    "email": email,
                },
                "receipt": {
                    "customer": {
                        "email": email,
                    },
                    "items": [
                        {
                            "description": "🔮 Подписка на безлимит Malina",
                            "quantity": 1.000,
                            "amount": {
                                "value": amount,
                                "currency": "RUB",
                            },
                            "vat_code": 1,
                        },
                    ],
                },
            }

            payment = Payment.create(payment_data, idempotency_key=str(uuid.uuid4()))

            logger.info(f"Платеж с сохранением способа оплаты создан: {payment.id}")
            return payment

        except BadRequestError as e:
            logger.error(
                f"Ошибка при создании платежа с сохранением способа оплаты: {e}"
            )
            raise Exception(f"Ошибка создания платежа: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            raise

    async def create_recurring_payment(
        self,
        user_id: int,
        payment_method_id: str,
        email: str,
        amount: str,
    ):
        """
        Создает регулярный платеж с использованием сохраненного способа оплаты.

        Args:
            user_id: ID пользователя
            payment_method_id: ID сохраненного способа оплаты

        Returns:
            dict: Данные созданного платежа
        """
        try:
            payment_data = {
                "amount": {
                    "value": "799.00",
                    "currency": "RUB",
                },
                "capture": True,
                "payment_method_id": payment_method_id,
                "description": "🔮 Подписка на безлимит Malina",
                "metadata": {
                    "user_id": user_id,
                    "email": email,
                },
                "receipt": {
                    "customer": {
                        "email": email,
                    },
                    "items": [
                        {
                            "description": "🔮 Подписка на безлимит Malina",
                            "quantity": 1.000,
                            "amount": {
                                "value": "799.00",
                                "currency": "RUB",
                            },
                            "vat_code": 1,
                        },
                    ],
                },
            }

            payment = Payment.create(payment_data, idempotency_key=str(uuid.uuid4()))

            logger.info(f"Регулярный платеж создан: {payment.id}")
            return payment

        except BadRequestError as e:
            logger.error(f"Ошибка при создании регулярного платежа: {e}")
            raise Exception(f"Ошибка создания регулярного платежа: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            raise


yookassa_service = YooKassaService()
