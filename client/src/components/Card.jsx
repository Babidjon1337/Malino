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
      className={`card-container ${disabled ? "disabled" : ""}`}
      onClick={!disabled ? onClick : undefined}
      whileHover={{ scale: disabled ? 1 : 1.05 }}
      whileTap={{ scale: disabled ? 1 : 0.95 }}
      style={{ width: `${width}px`, height: `${height}px` }}
    >
      <motion.div
        className={`card ${isFlipped ? "flipped" : ""}`}
        animate={{ rotateY: isFlipped ? 180 : 0 }}
        transition={{ duration: 0.6, ease: "easeInOut" }}
      >
        {/* Слой 1: Лицевая сторона карты */}

        <div className="card-front">
          <img className="card-image" src={card.image} alt={card.name} />
          <div className="card-name"></div>
        </div>

        {/* Слой 2: Черная прослойка */}
        <div className="card-middle"></div>

        {/* Слой 3: Рубашка карты */}
        <div className="card-back">
          <div className="card-back-image"></div>
        </div>
      </motion.div>
    </motion.div>
  );
};

export default Card;
