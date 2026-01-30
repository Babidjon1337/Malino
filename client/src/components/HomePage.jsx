import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import Card from "./Card";
import Loader from "./Loader";
import tarotCardsData from "../data/tarotCards";
import AnimatedStars from "./AnimatedStars";

const cardBack = "/img/card-back/CardBack.png";

const HomePage = () => {
  const [cards, setCards] = useState([]);
  const [flippedCount, setFlippedCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isBackImageLoaded, setIsBackImageLoaded] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (window.Telegram?.WebApp) {
      const handleRestore = () => {
        setCards((prevCards) =>
          prevCards.map((card) => ({ ...card, flipped: false })),
        );
        setFlippedCount(0);
      };

      window.Telegram.WebApp.onEvent("viewportChanged", handleRestore);
      return () => {
        window.Telegram.WebApp.offEvent("viewportChanged", handleRestore);
      };
    }
  }, []);

  const calculateCardSize = () => {
    const screenWidth = window.innerWidth;
    if (screenWidth < 350) return { width: 80, height: 130 };
    if (screenWidth < 400) return { width: 90, height: 145 };
    if (screenWidth < 600) return { width: 110, height: 170 };
    return { width: 140, height: 210 };
  };

  const [cardSize, setCardSize] = useState(calculateCardSize());

  useEffect(() => {
    const handleResize = () => setCardSize(calculateCardSize());
    window.addEventListener("resize", handleResize);
    handleResize();
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const handleCardClick = (id) => {
    const clickedCard = cards.find((c) => c.id === id);
    if (flippedCount >= 3 || (clickedCard && clickedCard.flipped)) return;
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
    <div className="bg-deep-blue text-gold min-h-screen text-base font-montserrat flex flex-col items-center relative z-10 w-full max-w-full box-border overflow-hidden">
      <AnimatedStars />
      <Loader isLoading={isLoading} />

      {!isLoading && isBackImageLoaded && (
        <>
          <motion.div
            // Исправлен padding: py-5 (20px) px-2.5 (10px) - как в оригинале
            className="text-center mb-4 max-w-full py-5 px-2.5 relative z-20"
            initial={{ opacity: 0, y: -50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            {/* Добавлен font-bold и leading-tight для восстановления вида */}
            <h1 className="text-[1.8rem] font-bold leading-tight mb-2 mt-6 tracking-[2px] text-shadow-header max-[350px]:text-[1.4rem]">
              Таро Гадание
            </h1>
            <p className="text-[0.8rem] mb-[35px] opacity-90 text-center max-w-[500px] mx-auto max-[350px]:text-[0.6rem]">
              Выберите 3 карты, чтобы узнать свое будущее
            </p>
            <div className="flex justify-center gap-[15px] mt-[15px]">
              {[1, 2, 3].map((_, i) => (
                <motion.div
                  key={i}
                  className={`w-3 h-3 rounded-full border-2 border-light-purple transition-all duration-300 ${
                    flippedCount > i
                      ? "bg-gold border-light-purple shadow-[0_0_8px_var(--gold)] scale-125"
                      : "bg-medium-purple"
                  }`}
                  animate={{ scale: flippedCount === i ? [1, 1.5, 1] : 1 }}
                  transition={{ duration: 0.3 }}
                />
              ))}
            </div>
          </motion.div>

          <div
            className="grid gap-[15px] max-w-[500px] mx-auto mb-5 relative z-30 max-[350px]:items-center max-[350px]:gap-3"
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

          <div className="flex gap-[25px] mt-[25px] opacity-80 text-gold max-[350px]:gap-[15px]">
            {["✨", "🔮", "🪐\uFE0E"].map((symbol, i) => (
              <motion.div
                key={i}
                className="text-[2rem] text-shadow-symbol"
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
                <span className="font-arial text-[2rem] leading-none inline-block select-none max-[350px]:text-[1.3rem]">
                  {symbol}
                </span>
              </motion.div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default HomePage;
