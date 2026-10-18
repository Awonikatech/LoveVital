import typography from "@tailwindcss/typography";
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ivory: { DEFAULT: "#FBF6EC", 50: "#FFFDF8", 100: "#FBF6EC", 200: "#F4EADA", 300: "#EADBC2" },
        kajal: { DEFAULT: "#2A1A1F", 700: "#3D2A30", 500: "#6B5A5E", 400: "#8C7D80", 300: "#B5AAAC" },
        gold: { DEFAULT: "#B8862B", 50: "#FBF4E4", 100: "#F5E6C3", 200: "#E9C979", 300: "#D9AE55", 500: "#B8862B", 600: "#9C7022", 700: "#8A611A", 800: "#6B4A14" },
        kumkum: { DEFAULT: "#A3202E", 50: "#FBEDEE", 100: "#F3CED2", 600: "#8C1A27" },
        blush: { DEFAULT: "#EFE0D8", 50: "#F9F1ED" },
        leaf: { DEFAULT: "#2F6B4F", 50: "#EAF3EE" },
      },
      fontFamily: {
        display: ['"Marcellus"', "Georgia", "serif"],
        sans: ['"Jost"', "system-ui", "sans-serif"],
      },
      fontSize: { "2xs": ["0.6875rem", { lineHeight: "1rem" }] },
      borderRadius: { arch: "999px 999px 0 0" },
      boxShadow: { lift: "0 18px 40px -24px rgba(74, 52, 24, 0.45)", hair: "0 0 0 1px rgba(184,134,43,.25)" },
      maxWidth: { site: "1320px" },
    },
  },
  plugins: [typography],
};
