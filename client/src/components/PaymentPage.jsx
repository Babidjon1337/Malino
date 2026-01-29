import React, { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import Loader from "./Loader"; // Импортируем компонент загрузки
import "../index.css";

// ⚠️ ЗАМЕНИТЕ НА ВАШ РЕАЛЬНЫЙ ДОМЕН
const API_BASE_URL = "https://malinaezo.ru/api";
const CREATE_PAYMENT_URL = `${API_BASE_URL}/create-payment`;
const CHECK_SUBSCRIPTION_URL = `${API_BASE_URL}/check-subscription`;

const PaymentPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Состояния данных
  const [daysLeft, setDaysLeft] = useState(0);
  const [isSubscriptionActive, setIsSubscriptionActive] = useState(false);

  // Состояния загрузки
  const [isCheckingSubscription, setIsCheckingSubscription] = useState(true); // Загрузка при входе
  const [isProcessingPayment, setIsProcessingPayment] = useState(false); // Загрузка при оплате

  // Данные пользователя из URL
  const messageId = searchParams.get("message_id");
  // 1. Пытаемся получить user_id из URL, если нет — из Telegram WebApp
  const urlUserId = searchParams.get("user_id");
  const tgUserId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  const userId = urlUserId || tgUserId; // Используем любой доступный

  // Состояние формы
  const [selectedAmount, setSelectedAmount] = useState(300);
  const [email, setEmail] = useState("");
  const [isOfferAccepted, setIsOfferAccepted] = useState(false);
  const [isPrivacyAccepted, setIsPrivacyAccepted] = useState(false);
  const [emailError, setEmailError] = useState(false);

  // Инициализация Telegram WebApp
  useEffect(() => {
    if (window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp;
      tg.expand();
      tg.setHeaderColor("#0f0c29");
      tg.setBackgroundColor("#0f0c29");
    }
  }, []);

  // 2. ПРОВЕРКА ПОДПИСКИ ПРИ ЗАГРУЗКЕ
  useEffect(() => {
    const checkSubscription = async () => {
      // Если нет user_id, мы не можем проверить подписку, просто показываем форму
      if (!userId) {
        setIsCheckingSubscription(false);
        return;
      }

      try {
        // Отправляем GET запрос на ваш сервер
        const response = await fetch(
          `${CHECK_SUBSCRIPTION_URL}?user_id=${userId}`,
          {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
              "ngrok-skip-browser-warning": "true",
            },
          },
        );

        if (response.ok) {
          const data = await response.json();
          if (data.is_active) {
            setIsSubscriptionActive(true);
            setDaysLeft(data.days_left || 0);
          }
        }
      } catch (error) {
        console.error("Ошибка проверки подписки:", error);
      } finally {
        setIsCheckingSubscription(false);
      }
    };

    checkSubscription();
  }, [userId]);

  // Валидация Email
  const isValidEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const handleEmailBlur = () => {
    if (!email.trim() || !isValidEmail(email)) {
      setEmailError(true);
      triggerHaptic("error");
    } else {
      setEmailError(false);
    }
  };

  const handleEmailChange = (e) => {
    setEmail(e.target.value);
    if (emailError) setEmailError(false);
  };

  // Вибрация
  const triggerHaptic = (type) => {
    if (window.Telegram?.WebApp?.HapticFeedback) {
      if (type === "light")
        window.Telegram.WebApp.HapticFeedback.impactOccurred("light");
      if (type === "heavy")
        window.Telegram.WebApp.HapticFeedback.impactOccurred("heavy");
      if (type === "error")
        window.Telegram.WebApp.HapticFeedback.notificationOccurred("error");
      if (type === "selection")
        window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
  };

  const isButtonDisabled = () => {
    if (isProcessingPayment) return true;
    const isEmailFilled = email.trim().length > 0;
    const isEmailValid = isValidEmail(email);
    return !(
      isOfferAccepted &&
      isPrivacyAccepted &&
      isEmailFilled &&
      isEmailValid
    );
  };

  const handlePayment = async () => {
    if (isButtonDisabled()) return;

    setIsProcessingPayment(true);
    triggerHaptic("heavy");

    const tg = window.Telegram?.WebApp;

    const data = {
      initData: tg?.initData,
      amount: selectedAmount,
      email: email,
      user_id: userId,
      message_id: messageId,
      offer_accepted: true,
      privacy_accepted: true,
      recurrent_accepted: true,
    };

    try {
      const response = await fetch(CREATE_PAYMENT_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (!response.ok) throw new Error("Ошибка сети или сервера");

      const result = await response.json();

      if (result.payment_url) {
        window.location.href = result.payment_url;
      } else {
        alert("Ошибка: сервер не вернул ссылку на оплату");
        setIsProcessingPayment(false);
      }
    } catch (error) {
      console.error(error);
      tg?.showAlert(`Ошибка создания платежа: ${error.message}`);
      setIsProcessingPayment(false);
    }
  };

  const handleClose = () => {
    window.Telegram?.WebApp?.close();
  };

  // --- 1. ЭКРАН ЗАГРУЗКИ ---
  if (isCheckingSubscription) {
    return (
      <div
        className="payment-page-container"
        style={{ justifyContent: "center", alignItems: "center" }}
      >
        <Loader isLoading={true} />
      </div>
    );
  }

  // --- 2. ЭКРАН АКТИВНОЙ ПОДПИСКИ ---
  if (isSubscriptionActive) {
    return (
      <div className="payment-page-container active-state">
        <h1>Подписка Активна</h1>
        <div className="status-circle">
          <div className="days-count">{daysLeft}</div>
          <div className="days-label">Дней</div>
        </div>
        <div
          className="subtitle"
          style={{ fontSize: "16px", color: "var(--pay-gold)" }}
        >
          Ваш путь открыт
        </div>
        <div className="status-message">
          Вы уже обладаете доступом к тайным знаниям. Карты Таро доступны без
          ограничений.
        </div>
        <button className="main-button" onClick={handleClose}>
          Вернуться в бота
        </button>
      </div>
    );
  }

  // --- 3. ЭКРАН ОПЛАТЫ ---
  return (
    <div className="payment-page-container">
      <div className="content-wrapper">
        <div className="header-section">
          <h1>Мистический Доступ</h1>
          <div className="subtitle">Выбери свой путь к знаниям</div>
        </div>

        <div className="tariffs-container">
          <div
            className={`tariff-card ${selectedAmount === 99 ? "active" : ""} ${isProcessingPayment ? "disabled-card" : ""}`}
            onClick={() => {
              if (!isProcessingPayment) {
                setSelectedAmount(99);
                triggerHaptic("light");
              }
            }}
          >
            <div className="tariff-name">Пробный</div>
            <div className="tariff-price">
              99 <span>₽</span>
            </div>
            <div className="tariff-desc">
              Доступ на 24 часа
              <br />
              Далее 300 ₽/мес
            </div>
          </div>

          <div
            className={`tariff-card ${selectedAmount === 300 ? "active" : ""} ${isProcessingPayment ? "disabled-card" : ""}`}
            onClick={() => {
              if (!isProcessingPayment) {
                setSelectedAmount(300);
                triggerHaptic("light");
              }
            }}
          >
            <div className="badge">Выгодно</div>
            <div className="tariff-name">Месяц</div>
            <div className="tariff-price">
              300 <span>₽</span>
            </div>
            <div className="tariff-desc">
              Полный доступ
              <br />
              на 30 дней
            </div>
          </div>
        </div>

        <div className="input-group">
          <input
            type="email"
            placeholder="Ваш Email"
            value={email}
            onChange={handleEmailChange}
            onBlur={handleEmailBlur}
            disabled={isProcessingPayment}
            className={emailError ? "input-error" : ""}
          />
          <div className="input-hint">Обязательно для отправки чека</div>
        </div>

        <div className="checkbox-container">
          <div className="checkbox-title">Я принимаю условия:</div>
          <label className="checkbox-item">
            <input
              type="checkbox"
              checked={isOfferAccepted}
              onChange={(e) => {
                setIsOfferAccepted(e.target.checked);
                triggerHaptic("selection");
              }}
              disabled={isProcessingPayment}
            />
            <span className="checkmark"></span>
            <span>
              <a href="https://telegra.ph/Publichnaya-oferta-10-31-6">
                Публичной оферты
              </a>
            </span>
          </label>
          <label className="checkbox-item">
            <input
              type="checkbox"
              checked={isPrivacyAccepted}
              onChange={(e) => {
                setIsPrivacyAccepted(e.target.checked);
                triggerHaptic("selection");
              }}
              disabled={isProcessingPayment}
            />
            <span className="checkmark"></span>
            <span>
              <a href="https://telegra.ph/Politika-konfidencialnosti-09-14-42">
                Политики конфиденциальности
              </a>
            </span>
          </label>
        </div>

        <div className="footer-note">Безопасная оплата через ЮКасса</div>

        <button
          className="main-button"
          disabled={isButtonDisabled()}
          onClick={handlePayment}
        >
          {isProcessingPayment ? (
            <>
              Создаем платеж... <div className="spinner"></div>
            </>
          ) : (
            `Оплатить ${selectedAmount} ₽`
          )}
        </button>
      </div>
    </div>
  );
};

export default PaymentPage;
