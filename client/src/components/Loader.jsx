import { motion, AnimatePresence } from "framer-motion";

const Loader = ({ isLoading }) => {
  return (
    <AnimatePresence>
      {isLoading && (
        <motion.div
          className="loader"
          initial={{ opacity: 1 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.5 } }}
          transition={{ duration: 0.3 }}
        >
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            style={{
              width: "100px",
              height: "100px",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              fontSize: "7rem",
              color: "#e6d7b8",
            }}
          >
            <span>{["🪐\uFE0E"]}</span>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default Loader;
