import React, { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";

// === ЗАМЕНИТЕ НА ВАШИ РЕАЛЬНЫЕ ДАННЫЕ ===
const API_BASE_URL = "https://malinaezo.ru/api";
const CREATE_PAYMENT_URL = `${API_BASE_URL}/create-payment`;
const CHECK_SUBSCRIPTION_URL = `${API_BASE_URL}/check-subscription`;

// Внутренний компонент Loader
const Loader = () => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0a0a14]/95">
    <div className="w-12 h-12 border-4 border-white/20 border-t-[#ffd700] rounded-full animate-spin"></div>
  </div>
);

const PaymentPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Состояния
  const [daysLeft, setDaysLeft] = useState(0);
  const [isSubscriptionActive, setIsSubscriptionActive] = useState(false);
  const [isCheckingSubscription, setIsCheckingSubscription] = useState(true);
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);

  // Данные пользователя
  const messageId = searchParams.get("message_id");
  const urlUserId = searchParams.get("user_id");
  const tgUserId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  const userId = urlUserId || tgUserId;

  // Форма
  const [selectedAmount, setSelectedAmount] = useState(300);
  const [email, setEmail] = useState("");
  const [isOfferAccepted, setIsOfferAccepted] = useState(false);
  const [isPrivacyAccepted, setIsPrivacyAccepted] = useState(false);
  const [emailError, setEmailError] = useState(false);

  // Инициализация Telegram
  useEffect(() => {
    if (window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp;
      tg.expand();
      tg.setHeaderColor("#0f0c29");
      tg.setBackgroundColor("#0f0c29");
    }
  }, []);

  // Проверка подписки
  useEffect(() => {
    const checkSubscription = async () => {
      if (!userId) {
        setIsCheckingSubscription(false);
        return;
      }
      try {
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
        console.error("Ошибка проверки:", error);
      } finally {
        setIsCheckingSubscription(false);
      }
    };
    checkSubscription();
  }, [userId]);

  // Валидация
  const isValidEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const handleEmailBlur = () => {
    if (!email.trim() || !isValidEmail(email)) {
      setEmailError(true);
      triggerHaptic("error");
    } else {
      setEmailError(false);
    }
  };

  const triggerHaptic = (type) => {
    const haptic = window.Telegram?.WebApp?.HapticFeedback;
    if (!haptic) return;
    if (type === "light") haptic.impactOccurred("light");
    if (type === "heavy") haptic.impactOccurred("heavy");
    if (type === "error") haptic.notificationOccurred("error");
    if (type === "selection") haptic.selectionChanged();
  };

  const isButtonDisabled = () => {
    if (isProcessingPayment) return true;
    return !(
      isOfferAccepted &&
      isPrivacyAccepted &&
      email.trim().length > 0 &&
      isValidEmail(email)
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

      if (!response.ok) throw new Error("Ошибка сети");
      const result = await response.json();

      if (result.payment_url) {
        window.location.href = result.payment_url;
      } else {
        alert("Ошибка получения ссылки");
        setIsProcessingPayment(false);
      }
    } catch (error) {
      console.error(error);
      tg?.showAlert(`Ошибка: ${error.message}`);
      setIsProcessingPayment(false);
    }
  };

  const handleClose = () => window.Telegram?.WebApp?.close();

  // === Стили ===
  const styles = `
    @import url("https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Montserrat:wght@400;500;600;700&display=swap");
    
    @keyframes starsMove {
      from { background-position: 0 0, 40px 60px, 130px 270px; }
      to { background-position: 550px 550px, 390px 410px, 380px 520px; }
    }
    
    @keyframes pulseGlow {
      0%, 100% { opacity: 0.5; transform: scale(1); }
      50% { opacity: 0.8; transform: scale(1.05); }
    }
    
    .star-bg {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: 0;
    }
    
    .star-bg::before {
      content: "";
      position: absolute; inset: 0; width: 100%; height: 100%;
      background-image:
        radial-gradient(white, rgba(255, 255, 255, 0.2) 2px, transparent 3px),
        radial-gradient(white, rgba(255, 255, 255, 0.15) 1px, transparent 2px),
        radial-gradient(white, rgba(255, 255, 255, 0.1) 2px, transparent 3px);
      background-size: 550px 550px, 350px 350px, 250px 250px;
      opacity: 0.3;
      animation: starsMove 100s linear infinite;
    }

    .active-card-glow::before {
      content: ""; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
      background: radial-gradient(circle, rgba(255, 215, 0, 0.15) 0%, transparent 70%);
      animation: pulseGlow 3s infinite; pointer-events: none;
    }
    
    .shake { animation: shake 0.4s ease-in-out; }
    @keyframes shake {
      0%, 100% { transform: translateX(0); }
      25% { transform: translateX(-5px); }
      75% { transform: translateX(5px); }
    }
  `;

  if (isCheckingSubscription) return <Loader />;

  // === ЭКРАН АКТИВНОЙ ПОДПИСКИ ===
  if (isSubscriptionActive) {
    return (
      <div className="fixed inset-0 w-full h-[100dvh] overflow-hidden bg-gradient-to-br from-[#0f0c29] via-[#302b63] to-[#24243e] text-[#e0e0e0] font-['Montserrat']">
        <style>{styles}</style>
        <div className="star-bg"></div>

        <div className="h-full w-full flex flex-col items-center justify-center p-5 relative z-10">
          <h1 className="font-['Cinzel'] text-[#ffd700] text-3xl drop-shadow-[0_0_10px_rgba(255,215,0,0.4)] mb-8 text-center">
            Подписка Активна
          </h1>

          <div className="relative w-[120px] h-[120px] rounded-full border-2 border-[#ffd700] flex flex-col items-center justify-center shadow-[0_0_30px_rgba(255,215,0,0.4)] bg-black/20 backdrop-blur-sm mb-8">
            <div className="absolute -inset-2 rounded-full border border-dashed border-[#ffd700]/30 animate-[spin_10s_linear_infinite]"></div>
            <div className="font-['Cinzel'] text-4xl text-white font-bold">
              {daysLeft}
            </div>
            <div className="text-xs text-[#ffd700] uppercase tracking-widest mt-1">
              Дней
            </div>
          </div>

          <div className="text-[#ffd700] text-lg mb-4 font-medium drop-shadow-sm">
            Ваш путь открыт
          </div>
          <div className="text-center text-gray-300 text-sm max-w-xs leading-relaxed mb-10 opacity-90">
            Вы уже обладаете доступом к тайным знаниям. Карты Таро доступны без
            ограничений.
          </div>

          <button
            onClick={handleClose}
            className="w-full max-w-[300px] py-4 rounded-xl bg-gradient-to-r from-[#ffd700] to-[#fdb931] text-[#0f0c29] font-bold text-base uppercase tracking-wider shadow-[0_4px_15px_rgba(255,215,0,0.2)] hover:shadow-[0_8px_25px_rgba(255,215,0,0.4)] transition-all active:scale-95"
          >
            Вернуться в бота
          </button>
        </div>
      </div>
    );
  }

  // === ЭКРАН ОПЛАТЫ ===
  return (
    // ВЕРНУЛИ overflow-hidden, ЧТОБЫ УБРАТЬ СКРОЛЛ
    <div className="fixed inset-0 w-full h-[100dvh] overflow-hidden bg-gradient-to-br from-[#0f0c29] via-[#302b63] to-[#24243e] text-[#e0e0e0] font-['Montserrat']">
      <style>{styles}</style>
      <div className="star-bg"></div>

      {/* Используем h-full и justify-center для идеального центрирования без прокрутки */}
      <div className="h-full w-full flex flex-col items-center justify-center p-4 relative z-10">
        <div className="w-full max-w-[400px] flex flex-col items-center">
          {/* Заголовок */}
          <div className="text-center mb-5">
            <h1 className="font-['Cinzel'] text-[#ffd700] font-bold text-3xl drop-shadow-[0_0_10px_rgba(255,215,0,0.3)] py-1 tracking-wide">
              Мистический Доступ
            </h1>
            <div className="text-[#a0a0a0] text-[13px] opacity-90">
              Выбери свой путь к знаниям
            </div>
          </div>

          {/* Карточки Тарифов */}
          <div className="flex gap-4 w-full mb-3 mt-4">
            {/* Тариф 99 */}
            <div
              onClick={() => {
                if (!isProcessingPayment) {
                  setSelectedAmount(99);
                  triggerHaptic("light");
                }
              }}
              className={`flex-1 relative overflow-hidden cursor-pointer rounded-2xl p-4 flex flex-col items-center justify-center transition-all duration-300 border backdrop-blur-md
                ${
                  selectedAmount === 99
                    ? "bg-[#ffd700]/10 border-[#ffd700] shadow-[0_0_20px_rgba(255,215,0,0.4)] transform scale-[1.02] active-card-glow"
                    : "bg-white/5 border-white/10 hover:-translate-y-0.5"
                } ${isProcessingPayment ? "opacity-60 cursor-not-allowed" : ""}`}
            >
              <div className="text-[13px] pt-1 uppercase tracking-widest text-gray-400 mb-1">
                Пробный
              </div>
              <div className="font-['Cinzel'] text-[26px] font-bold text-white mb-1">
                99 <span className="text-[#ffd700] text-lg">₽</span>
              </div>
              <div className="text-[10.5px] text-gray-300 text-center leading-tight opacity-80">
                Доступ на 24 часа
                <br />
                Далее 300 ₽/мес
              </div>
            </div>

            {/* Тариф 300 */}
            <div
              onClick={() => {
                if (!isProcessingPayment) {
                  setSelectedAmount(300);
                  triggerHaptic("light");
                }
              }}
              className={`flex-1 relative overflow-hidden cursor-pointer rounded-2xl p-4 flex flex-col items-center justify-center transition-all duration-300 border backdrop-blur-md
                ${
                  selectedAmount === 300
                    ? "bg-[#ffd700]/10 border-[#ffd700] shadow-[0_0_20px_rgba(255,215,0,0.4)] transform scale-[1.02] active-card-glow"
                    : "bg-white/5 border-white/10 hover:-translate-y-0.5"
                } ${isProcessingPayment ? "opacity-60 cursor-not-allowed" : ""}`}
            >
              <div className="absolute top-0 right-0 bg-[#ffd700] text-[#0f0c29] text-[9.5px] font-bold px-2 py-[2px] rounded-bl-lg uppercase shadow-sm">
                Выгодно
              </div>
              <div className="text-[13px] uppercase tracking-widest text-gray-400 mb-1">
                Месяц
              </div>
              <div className="font-['Cinzel'] text-[26px] font-bold text-white mb-1">
                300 <span className="text-[#ffd700] text-lg">₽</span>
              </div>
              <div className="text-[10.5px] text-gray-300 text-center leading-tight opacity-80">
                Полный доступ
                <br />
                на 30 дней
              </div>
            </div>
          </div>

          {/* Поле Email */}
          <div className="w-full relative mt-2">
            <input
              type="email"
              placeholder="Ваш Email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (emailError) setEmailError(false);
              }}
              onBlur={handleEmailBlur}
              disabled={isProcessingPayment}
              className={`w-full p-[13px] bg-black/30 border rounded-xl text-white outline-none transition-all duration-300
                ${
                  emailError
                    ? "border-red-500 shadow-[0_0_10px_rgba(255,75,75,0.4)] shake"
                    : "border-white/10 focus:border-[#ffd700] focus:shadow-[0_0_15px_rgba(255,215,0,0.3)]"
                } disabled:opacity-50 disabled:cursor-not-allowed placeholder:text-gray-500`}
            />
            <div className="text-[10px] text-gray-400 mt-2 ml-1 mb-6">
              Обязательно для отправки чека
            </div>
          </div>

          {/* Чекбоксы */}
          <div className="w-full bg-black/25 backdrop-blur-sm rounded-xl p-4 flex flex-col gap-3 border border-white/5 mb-4">
            <div className="text-[14px] font-semibold text-gray-200 mb-1">
              Я принимаю условия:
            </div>

            {/* Чекбокс Оферты */}
            <label
              className={`flex items-start gap-3 cursor-pointer group select-none ${isProcessingPayment ? "pointer-events-none opacity-60" : ""}`}
            >
              <div className="relative pt-0.5">
                <input
                  type="checkbox"
                  className="peer sr-only"
                  checked={isOfferAccepted}
                  onChange={(e) => {
                    setIsOfferAccepted(e.target.checked);
                    triggerHaptic("selection");
                  }}
                />
                <div className="w-5 h-5 border border-gray-400 rounded transition-all duration-300 peer-checked:bg-[#ffd700] peer-checked:border-[#ffd700] peer-checked:shadow-[0_0_10px_rgba(255,215,0,0.5)] flex items-center justify-center">
                  {isOfferAccepted && (
                    <svg
                      className="w-3 h-3 text-[#0f0c29]"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth="3"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  )}
                </div>
              </div>
              <div className="text-[14px] mt-1 text-gray-400 leading-tight group-hover:text-gray-300 transition-colors">
                <a
                  href="https://telegra.ph/Publichnaya-oferta-10-31-6"
                  className="text-[#ffd700] border-b border-dashed border-[#ffd700]/50 hover:border-[#ffd700] transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  Публичной оферты
                </a>
              </div>
            </label>

            {/* Чекбокс Политики */}
            <label
              className={`flex items-start gap-3 cursor-pointer group select-none ${isProcessingPayment ? "pointer-events-none opacity-60" : ""}`}
            >
              <div className="relative pt-0.5">
                <input
                  type="checkbox"
                  className="peer sr-only"
                  checked={isPrivacyAccepted}
                  onChange={(e) => {
                    setIsPrivacyAccepted(e.target.checked);
                    triggerHaptic("selection");
                  }}
                />
                <div className="w-5 h-5 border border-gray-400 rounded transition-all duration-300 peer-checked:bg-[#ffd700] peer-checked:border-[#ffd700] peer-checked:shadow-[0_0_10px_rgba(255,215,0,0.5)] flex items-center justify-center">
                  {isPrivacyAccepted && (
                    <svg
                      className="w-3 h-3 text-[#0f0c29]"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth="3"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  )}
                </div>
              </div>
              <div className="text-[14px] mt-1 text-gray-400 leading-tight group-hover:text-gray-300 transition-colors">
                <a
                  href="https://telegra.ph/Politika-konfidencialnosti-09-14-42"
                  className="text-[#ffd700] border-b border-dashed border-[#ffd700]/50 hover:border-[#ffd700] transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  Политики конфиденциальности
                </a>
              </div>
            </label>
          </div>

          {/* Футер */}
          <div className="text-[10px] text-gray-300 mb-2 opacity-60 text-center w-full">
            Безопасная оплата через ЮКасса
          </div>

          {/* Кнопка Оплаты */}
          <button
            onClick={handlePayment}
            disabled={isButtonDisabled()}
            className={`w-full py-4 rounded-xl font-bold text-base uppercase tracking-wider transition-all flex items-center justify-center gap-2
              ${
                isButtonDisabled()
                  ? "bg-[#2c2c2c] text-[#555550] cursor-not-allowed shadow-none"
                  : "bg-gradient-to-r from-[#ffd700] to-[#fdb931] text-[#0f0c29] shadow-[0_4px_15px_rgba(255,215,0,0.2)] hover:shadow-[0_8px_25px_rgba(255,215,0,0.4)] hover:-translate-y-0.5 active:scale-95"
              }`}
          >
            {isProcessingPayment ? (
              <>
                Создаем платеж
                <div className="w-4 h-4 border-2 border-[#0f0c29]/30 border-t-[#0f0c29] rounded-full animate-spin"></div>
              </>
            ) : (
              `Оплатить ${selectedAmount} ₽`
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PaymentPage;
