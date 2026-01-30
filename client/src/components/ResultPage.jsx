import { useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import Card from "./Card";
import request from "../api/request";
import AnimatedStars from "./AnimatedStars";
import { postEvent } from "@telegram-apps/sdk-react";

const ResultPage = ({ launchParams }) => {
  const location = useLocation();
  const selectedCards = location.state?.selectedCards || [];
  const [cardSize] = useState({ width: 120, height: 180 });

  useEffect(() => {
    const setVh = () => {
      const vh = window.innerHeight * 0.01;
      document.documentElement.style.setProperty("--vh", `${vh}px`);
      document.body.style.overflow = "";
    };
    setVh();
    window.addEventListener("resize", setVh);
    return () => window.removeEventListener("resize", setVh);
  }, []);

  const handleLearnMore = async () => {
    try {
      console.log("=== Sending Data ===");
      let userId;
      if (launchParams?.tgWebAppData?.user) {
        userId = launchParams.tgWebAppData.user.id;
      } else if (launchParams?.initData?.user) {
        userId = launchParams.initData.user.id;
      } else {
        return;
      }

      const message_id = launchParams.message_id;
      if (!message_id) return;

      const resultData = {
        user_id: userId,
        cards: selectedCards,
        message_id: message_id,
      };

      let initDataRaw =
        launchParams?.tgWebAppData || launchParams?.initDataRaw || null;
      await request("mini-app", "post", resultData, initDataRaw);

      try {
        postEvent("web_app_close");
      } catch (closeError) {
        if (window.Telegram && window.Telegram.WebApp) {
          window.Telegram.WebApp.close();
        }
      }
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <div className="bg-deep-blue text-gold min-h-screen text-base font-montserrat flex flex-col items-center relative z-10 w-full max-w-full box-border overflow-hidden">
      <AnimatedStars />

      <motion.div
        className="text-center mb-2.5 max-w-full pt-5 px-2.5 relative z-20"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1 }}
      >
        {/* Добавлен font-bold и leading-tight */}
        <h1 className="text-[1.8rem] font-bold leading-tight mb-2 tracking-[2px] text-shadow-header">
          Ваш Расклад
        </h1>
        <p className="text-[0.8rem] mb-[45px] opacity-90 text-center max-w-[500px] mx-auto">
          Три карты, которые вы выбрали
        </p>
      </motion.div>

      <div className="flex flex-row flex-wrap justify-center gap-[25px] max-w-full w-full -mt-10 mb-5 max-md:flex-col max-md:items-center">
        {selectedCards.map((card, i) => (
          <motion.div
            key={card.id}
            className="flex flex-col items-center w-[calc(33.33%-20px)] min-w-[120px] bg-[rgba(42,31,68,0.7)] rounded-[10px] p-[10px] shadow-result-card relative z-30 border border-light-purple max-md:w-full max-md:max-w-[180px]"
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: i * 0.2 }}
          >
            <Card card={card} width={cardSize.width} height={cardSize.height} />
            <div className="mt-[10px] text-center w-full">
              <h3 className="text-[1rem] mb-[5px] text-gold font-bold border-b border-light-purple pb-[3px] text-center">
                {card.name}
              </h3>
              <p className="text-[0.7rem] leading-[1.3] opacity-90">
                {card.meaning}
              </p>
            </div>
          </motion.div>
        ))}
      </div>

      <motion.button
        className="bg-btn-gradient text-beige border-none py-3 px-[30px] text-[1rem] rounded-[25px] cursor-pointer transition-all duration-300 tracking-[1px] shadow-btn mt-[15px] font-montserrat font-semibold w-full max-w-[300px] relative z-30 hover:bg-btn-gradient-hover max-md:text-[1.1rem] max-md:px-6"
        onClick={handleLearnMore}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        Трактовка
      </motion.button>

      <motion.div
        className="mt-[30px] text-center max-w-full text-[0.8rem] opacity-80 px-[15px] relative z-30 text-beige drop-shadow-[0_0_5px_rgba(0,0,0,0.5)]"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1, duration: 1 }}
      >
        <p className="text-[0.8rem] leading-[1.2] opacity-190 pb-3">
          Карты Таро открывают тайны вселенной. Прислушайтесь к их мудрости.
        </p>
      </motion.div>
    </div>
  );
};

export default ResultPage;
