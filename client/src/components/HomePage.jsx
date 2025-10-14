import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import Card from "./Card";
import Loader from "./Loader";
import tarotCardsData from "../data/tarotCards";
import cardBack from "/img/card-back/CardBack.png";
import AnimatedStars from "./AnimatedStars";

// Удаляем импорт useInitData, так как инициализация уже происходит в App.jsx через useLaunchParams

const HomePage = () => {
  const [cards, setCards] = useState([]);
  const [flippedCount, setFlippedCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isBackImageLoaded, setIsBackImageLoaded] = useState(false);
  // cardBack должен быть импортирован или определен
  // Удаляем обработку visibilitychange, так как инициализация теперь происходит в main.jsx через init()
  const navigate = useNavigate();
  // Удаляем использование viewport хука, переходим на WebApp API
  // Запрашиваем полноэкранный режим через WebApp API
  useEffect(() => {
    if (window.Telegram?.WebApp) {
      window.Telegram.WebApp.expand();
      window.Telegram.WebApp.requestFullscreen();

      // Обработчик для восстановления состояния при возвращении в приложение
      const handleRestore = () => {
        setCards((prevCards) =>
          prevCards.map((card) => ({ ...card, flipped: false }))
        );
        setFlippedCount(0);
      };

      window.Telegram.WebApp.onEvent("viewportChanged", handleRestore);
      return () => {
        window.Telegram.WebApp.offEvent("viewportChanged", handleRestore);
      };
    }
  }, []);

  // Рассчитываем размер карточек в зависимости от ширины экрана
  const calculateCardSize = () => {
    const screenWidth =
      window.Telegram?.WebApp?.viewportWidth || window.innerWidth;
    if (screenWidth < 400) return { width: 90, height: 145 };
    if (screenWidth < 600) return { width: 110, height: 170 };
    return { width: 140, height: 210 };
  };

  const [cardSize, setCardSize] = useState(calculateCardSize());

  useEffect(() => {
    const handleResize = () => {
      setCardSize(calculateCardSize());
    };

    // Используем WebApp API для отслеживания изменений размеров
    if (window.Telegram?.WebApp) {
      window.Telegram.WebApp.onEvent("viewport_changed", handleResize);
      handleResize();
    } else {
      window.addEventListener("resize", handleResize);
      handleResize();
    }

    return () => {
      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.offEvent("viewport_changed", handleResize);
      } else {
        window.removeEventListener("resize", handleResize);
      }
    };
  }, []);

  const handleCardClick = (id) => {
    if (flippedCount >= 3) return;

    setCards(
      cards.map((card) => (card.id === id ? { ...card, flipped: true } : card))
    );

    setFlippedCount((prev) => prev + 1);
  };

  useEffect(() => {
    if (flippedCount === 3) {
      // Используем requestAnimationFrame для синхронизации с рендерингом
      const timer = setTimeout(() => {
        requestAnimationFrame(() => {
          const selectedCards = cards.filter((card) => card.flipped);
          navigate("/result", { state: { selectedCards } });
        });
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [flippedCount, cards, navigate]);

  useEffect(() => {
    const loadData = () => {
      // Генерация 6 уникальных случайных индексов
      const indices = new Set();
      while (indices.size < 6) {
        indices.add(Math.floor(Math.random() * tarotCardsData.length));
      }
      // Создание массива выбранных карт с новыми ID
      const shuffled = Array.from(indices).map((index, i) => ({
        ...tarotCardsData[index],
        id: i + 1,
      }));
      // Используем Promise.race для надежной загрузки изображения с таймаутом
      Promise.race([
        new Promise((resolve) => {
          const img = new Image();
          img.src = cardBack;
          img.onload = resolve;
          img.onerror = resolve;
        }),
        new Promise((resolve) => setTimeout(resolve, 5000)),
      ])
        .then(() => {
          setIsBackImageLoaded(true);
          setCards(shuffled);
          setIsLoading(false);
        })
        .catch(() => {
          setIsBackImageLoaded(true);
          setCards(shuffled);
          setIsLoading(false);
        });
    };

    loadData();
  }, []);

  return (
    <div className="home-page">
      <AnimatedStars />
      {/* <div className="mystic-background"></div> */}

      <Loader isLoading={isLoading} />

      {!isLoading && isBackImageLoaded && (
        <>
          <motion.div
            className="header"
            initial={{ opacity: 0, y: -50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <h1>Таро Гадание</h1>
            <p>Выберите 3 карты, чтобы узнать свое будущее</p>
            <div className="counter">
              {[1, 2, 3].map((_, i) => (
                <motion.div
                  key={i}
                  className={`dot ${flippedCount > i ? "active" : ""}`}
                  animate={{ scale: flippedCount === i ? [1, 1.5, 1] : 1 }}
                  transition={{ duration: 0.3 }}
                />
              ))}
            </div>
          </motion.div>

          <div
            className="cards-grid"
            style={{
              gridTemplateColumns: `repeat(3, ${cardSize.width}px)`,
            }}
          >
            {cards.map((card) => (
              <Card
                key={card.id}
                card={card}
                onClick={() => handleCardClick(card.id)}
                disabled={flippedCount >= 3 && !card.flipped}
                width={cardSize.width}
                height={cardSize.height}
              />
            ))}
          </div>

          <div className="mystic-symbols">
            {["✨", "🔮", "🪐\uFE0E"].map((symbol, i) => (
              <motion.div
                key={i}
                className="symbol"
                animate={{
                  y: [0, -20, 0],
                  rotate: [0, 10, 0, -10, 0],
                }}
                transition={{
                  duration: 4,
                  repeat: Infinity,
                  delay: i * 0.5,
                  ease: "easeInOut",
                }}
              >
                <span className="text-symbol">{symbol}</span>
              </motion.div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default HomePage;
