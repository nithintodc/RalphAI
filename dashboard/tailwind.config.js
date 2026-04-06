/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Outfit", "system-ui", "sans-serif"],
        display: ["Outfit", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          50: "#f1fcf8",
          100: "#d5fbf1",
          200: "#b0f4e2",
          300: "#7deccf",
          400: "#41e2b8",
          500: "#05d79f",
          600: "#05c391",
          700: "#049772",
          800: "#046e54",
          900: "#04493a",
        },
        ink: {
          50: "#f6f6f6",
          100: "#e7e7e7",
          200: "#cfcfcf",
          300: "#b0b0b0",
          400: "#8a8a8a",
          500: "#6a6a6a",
          600: "#525252",
          700: "#3f3f3f",
          800: "#2f2f2f",
          900: "#252525",
        },
      },
      boxShadow: {
        soft: "0 20px 40px -24px rgb(37 37 37 / 0.18)",
        card: "0 0 0 1px rgb(37 37 37 / 0.08), 0 20px 50px -32px rgb(37 37 37 / 0.14)",
      },
    },
  },
  plugins: [],
};
