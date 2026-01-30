import { motion, AnimatePresence } from "framer-motion";

const Loader = ({ isLoading }) => {
  return (
    <AnimatePresence>
      {isLoading && (
        <motion.div
          className="fixed top-0 left-0 w-full h-full flex justify-center items-center bg-[rgba(10,10,20,0.95)] z-[1000]"
          initial={{ opacity: 1 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.5 } }}
          transition={{ duration: 0.3 }}
        >
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            className="w-[100px] h-[100px] flex justify-center items-center text-[7rem] text-[#e6d7b8]"
          >
            <span>{["🪐\uFE0E"]}</span>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default Loader;
