/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        montserrat: ['"Montserrat"', "sans-serif"],
        cinzel: ['"Cinzel"', "serif"],
        arial: ["Arial", "sans-serif"],
      },
      colors: {
        "dark-purple": "#0f0c1d",
        "medium-purple": "#2a1f44",
        "light-purple": "#6d5b8e",
        gold: "#d4af37",
        beige: "#f5f0e1",
        "deep-blue": "#1a1a2e",
        "mystic-teal": "#0d7a80",
        // Payment Page colors
        "bg-deep": "#0f0c29",
        "bg-purple": "#302b63",
        "bg-black": "#24243e",
        "pay-gold": "#ffd700",
        "error-red": "#ff4b4b",
      },
      boxShadow: {
        "gold-glow": "0 0 15px rgba(212, 175, 55, 0.8)",
        // Усиленное свечение для активной карты (как в Malina)
        "gold-glow-strong":
          "0 0 25px rgba(255, 215, 0, 0.6), inset 0 0 10px rgba(255, 215, 0, 0.2)",
        card: "0 3px 10px rgba(0, 0, 0, 0.5)",
        "result-card": "0 5px 15px rgba(0, 0, 0, 0.5)",
        btn: "0 4px 15px rgba(109, 91, 142, 0.4)",
        "pay-btn": "0 4px 15px rgba(255, 215, 0, 0.3)",
      },
      // Усиленные тени для текста
      textShadow: {
        header:
          "0 0 10px rgba(255, 215, 0, 0.8), 0 0 20px rgba(255, 215, 0, 0.4)",
        card: "0 0 3px rgba(255, 255, 255, 0.5)",
        symbol: "0 0 10px rgba(212, 175, 55, 0.5)",
        pay: "0 0 10px rgba(255, 215, 0, 0.5)",
      },
      backgroundImage: {
        "mystic-radial":
          "radial-gradient(circle at center, #0f0c1d 0%, #1a1a2e 70%)",
        "payment-gradient":
          "linear-gradient(135deg, #0f0c29, #302b63, #24243e)",
        "card-front": "linear-gradient(to bottom, #f5f0e1, #d4af37)",
        "btn-gradient": "linear-gradient(to right, #6d5b8e, #2a1f44)",
        "btn-gradient-hover": "linear-gradient(to right, #8a7eb6, #4a3a7a)",
        "pay-btn-gradient": "linear-gradient(45deg, #ffd700, #fdb931)",
      },
      transitionTimingFunction: {
        "flip-bezier": "cubic-bezier(0.175, 0.885, 0.32, 1.275)",
      },
      transitionDuration: {
        800: "800ms",
      },
      animation: {
        "spin-slow": "spin 60s linear infinite",
        "spin-medium": "spin 10s linear infinite",
        "pulse-glow": "pulseGlow 3s infinite",
        "stars-move": "starsMove 100s linear infinite",
        shake: "shake 0.4s ease-in-out",
      },
      keyframes: {
        pulseGlow: {
          "0%, 100%": {
            opacity: 0.8,
            boxShadow: "0 0 25px rgba(255, 215, 0, 0.6)",
          },
          "50%": { opacity: 1, boxShadow: "0 0 35px rgba(255, 215, 0, 0.8)" },
        },
        starsMove: {
          from: { backgroundPosition: "0 0, 40px 60px, 130px 270px" },
          to: { backgroundPosition: "550px 550px, 390px 410px, 380px 520px" },
        },
        shake: {
          "0%, 100%": { transform: "translateX(0)" },
          "25%": { transform: "translateX(-5px)" },
          "75%": { transform: "translateX(5px)" },
        },
      },
    },
  },
  plugins: [
    function ({ matchUtilities, theme }) {
      matchUtilities(
        {
          "text-shadow": (value) => ({
            textShadow: value,
          }),
        },
        { values: theme("textShadow") },
      );
    },
  ],
};
