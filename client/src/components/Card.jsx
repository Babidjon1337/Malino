import { motion } from "framer-motion";

const Card = ({
  card,
  onClick,
  disabled,
  width = 100,
  height = 150,
  forceCardBack = false,
}) => {
  const isFlipped = forceCardBack ? false : card.flipped;

  return (
    <motion.div
      className={`perspective-100 w-full h-full ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
      onClick={!disabled ? onClick : undefined}
      whileHover={{ scale: disabled ? 1 : 1.05 }}
      whileTap={{ scale: disabled ? 1 : 0.95 }}
      style={{ width: `${width}px`, height: `${height}px` }}
    >
      <motion.div
        className={`relative w-full h-full preserve-3d transition-transform duration-800 ease-flip-bezier ${isFlipped ? "rotate-y-180" : ""}`}
        animate={{ rotateY: isFlipped ? 180 : 0 }}
        transition={{ duration: 0.6, ease: "easeInOut" }}
      >
        {/* Слой 1: Лицевая сторона карты */}
        <div className="absolute w-full h-full backface-hidden rounded-lg shadow-card flex flex-col justify-between p-[5px] border border-light-purple z-10 bg-card-front rotate-y-180">
          <img
            className="w-full h-full object-cover object-center rounded-md block"
            src={card.image}
            alt={card.name}
          />
          <div className="text-[0.65rem] text-center mt-[3px] font-bold text-medium-purple leading-[1.2] text-shadow-card"></div>
        </div>

        {/* Слой 2: Черная прослойка (чтобы не просвечивало) */}
        <div className="absolute w-full h-full backface-hidden rounded-lg shadow-card flex justify-center items-center bg-black z-20"></div>

        {/* Слой 3: Рубашка карты */}
        <div className="absolute w-full h-full backface-hidden rounded-lg shadow-card flex justify-center items-center border border-light-purple z-30">
          <div className="w-full h-full bg-[url('/img/card-back/CardBack.png')] bg-cover bg-center rounded-lg"></div>
        </div>
      </motion.div>
    </motion.div>
  );
};

export default Card;
