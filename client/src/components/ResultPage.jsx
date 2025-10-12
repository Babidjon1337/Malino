import { useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import Card from "./Card";
import request from "../api/request";
import AnimatedStars from "./AnimatedStars";

// Импортируем postEvent из Telegram SDK для закрытия Mini App
import { postEvent } from "@telegram-apps/sdk-react";

const ResultPage = ({ launchParams }) => {
  const location = useLocation();
  const selectedCards = location.state?.selectedCards || [];

  // Рассчитываем размер карточек для страницы результатов

  const [cardSize] = useState({ width: 120, height: 180 });
  useEffect(() => {
    // Функция для установки точной высоты
    const setVh = () => {
      const vh = window.innerHeight * 0.01;
      document.documentElement.style.setProperty("--vh", `${vh}px`);

      // Разрешаем прокрутку на этой странице
      document.body.style.overflow = "";
    };

    setVh();
    window.addEventListener("resize", setVh);

    return () => {
      window.removeEventListener("resize", setVh);
    };
  }, []);

  const handleLearnMore = async () => {
    try {
      console.log("=== Отправка данных ===");
      console.log("Launch params:", launchParams);

      // Проверяем, есть ли данные пользователя в launchParams
      let userId;
      if (
        launchParams &&
        launchParams.tgWebAppData &&
        launchParams.tgWebAppData.user
      ) {
        userId = launchParams.tgWebAppData.user.id;
      } else if (
        launchParams &&
        launchParams.initData &&
        launchParams.initData.user
      ) {
        userId = launchParams.initData.user.id;
      } else {
        console.error(
          "Не удалось получить данные о пользователе из launchParams"
        );
        console.log("Доступные данные в launchParams:", launchParams);
        return;
      }
      console.log("User ID:", launchParams.tgWebAppData.user.id);
      console.log("question", launchParams.question);
      console.log("question", launchParams.message_id);

      const question = launchParams.question;
      const message_id = launchParams.message_id;
      if (!question || !message_id) {
        console.error("Не удалось извлечь вопрос из URL");
        return;
      }

      // Формируем данные для передачи в Telegram бота
      const resultData = {
        user_id: userId,
        cards: selectedCards,
        question: question,
        message_id: message_id,
      };

      console.log("Отправка данных на сервер:", resultData);

      // Добавляем initDataRaw в заголовки для аутентификации
      console.log("LaunchParams целиком:", launchParams);
      let initDataRaw = null;
      if (launchParams && launchParams.tgWebAppData) {
        initDataRaw = launchParams.tgWebAppData;
      } else if (launchParams && launchParams.initDataRaw) {
        initDataRaw = launchParams.initDataRaw;
      }
      console.log("InitDataRaw для отправки:", initDataRaw);
      await request("mini-app", "post", resultData, initDataRaw);
      // Закрываем Mini App после успешной отправки данных
      console.log("Попытка закрытия Mini App...");
      try {
        console.log("Используем postEvent для закрытия");
        postEvent("web_app_close");
        console.log("postEvent выполнен успешно");
      } catch (closeError) {
        console.error(
          "Ошибка при закрытии Mini App через postEvent:",
          closeError
        );
        // Альтернативный способ закрытия
        console.log(
          "Попытка альтернативного закрытия через window.Telegram.WebApp.close()"
        );
        if (window.Telegram && window.Telegram.WebApp) {
          try {
            window.Telegram.WebApp.close();
            console.log(
              "Закрытие через window.Telegram.WebApp.close() выполнено успешно"
            );
          } catch (altCloseError) {
            console.error("Ошибка при альтернативном закрытии:", altCloseError);
          }
        } else {
          console.error("window.Telegram.WebApp не доступен");
        }
      }
    } catch (error) {
      console.error("Ошибка при отправке данных:", error);
    }
  };

  return (
    <div className="result-page">
      <AnimatedStars />
      {/* <div className="mystic-background"></div> */}

      <motion.div
        className="header"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1 }}
      >
        <h1>Ваш Расклад</h1>
        <p>Три карты, которые вы выбрали</p>
      </motion.div>

      <div className="selected-cards">
        {selectedCards.map((card, i) => (
          <motion.div
            key={card.id}
            className="result-card-container"
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.7,
              delay: i * 0.2,
            }}
          >
            <Card card={card} width={cardSize.width} height={cardSize.height} />
            <div className="card-meaning">
              <h3>{card.name}</h3>
              <p>{card.meaning}</p>
            </div>
          </motion.div>
        ))}
      </div>

      <motion.button
        className="learn-more-btn"
        onClick={handleLearnMore}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        Трактовка
      </motion.button>

      <motion.div
        className="mystic-footer"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1, duration: 1 }}
      >
        <p>
          Карты Таро открывают тайны вселенной. Прислушайтесь к их мудрости.
        </p>
      </motion.div>
    </div>
  );
};

export default ResultPage;
