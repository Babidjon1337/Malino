import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import Card from "./Card";
import Loader from "./Loader";
import tarotCardsData from "../data/tarotCards";
import AnimatedStars from "./AnimatedStars";

// --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
// Мы удалили "import cardBack from ...", который вызывал ошибку.
// Теперь мы просто указываем путь к файлу в папке public (начинается со слэша /)
const cardBack = "/img/card-back/CardBack.png";
// -----------------------

const HomePage = () => {
  const [cards, setCards] = useState([]);
  const [flippedCount, setFlippedCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isBackImageLoaded, setIsBackImageLoaded] = useState(false);
  const navigate = useNavigate();

  // Логика восстановления состояния при возврате (expand() убрали, как договаривались)
  useEffect(() => {
    if (window.Telegram?.WebApp) {
      const handleRestore = () => {
        setCards((prevCards) =>
          prevCards.map((card) => ({ ...card, flipped: false })),
        );
        setFlippedCount(0);
      };

      window.Telegram.WebApp.enableClosingConfirmation();
      window.Telegram.WebApp.onEvent("viewportChanged", handleRestore);
      return () => {
        window.Telegram.WebApp.offEvent("viewportChanged", handleRestore);
      };
    }
  }, []);

  // Расчет размеров карт
  const calculateCardSize = () => {
    const screenWidth = window.innerWidth;

    if (screenWidth < 350) return { width: 80, height: 130 };
    if (screenWidth < 400) return { width: 90, height: 145 };
    if (screenWidth < 600) return { width: 110, height: 170 };
    return { width: 140, height: 210 };
  };

  const [cardSize, setCardSize] = useState(calculateCardSize());

  useEffect(() => {
    const handleResize = () => {
      setCardSize(calculateCardSize());
    };

    window.addEventListener("resize", handleResize);
    handleResize();

    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  const handleCardClick = (id) => {
    if (flippedCount >= 3) return;

    setCards(
      cards.map((card) => (card.id === id ? { ...card, flipped: true } : card)),
    );

    setFlippedCount((prev) => prev + 1);
  };

  useEffect(() => {
    if (flippedCount === 3) {
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
      const indices = new Set();
      while (indices.size < 6) {
        indices.add(Math.floor(Math.random() * tarotCardsData.length));
      }
      const shuffled = Array.from(indices).map((index, i) => ({
        ...tarotCardsData[index],
        id: i + 1,
      }));

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
              justifyContent: "center",
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
