import { motion } from "framer-motion";
import "./Loader.css";


const Loader = () => {
  return (
    <div className="cosmeya-loader">
      <motion.h1
        className="cosmeya-title"
        animate={{ opacity: [0.85, 1, 0.85] }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      >
        COSMEYA
      </motion.h1>

      <div className="cosmeya-glow" />
    </div>
  );
};

export default Loader;
