/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "media",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Semantic tokens — keep raw hex out of components.
        surface: "#f5f5f7", // Apple Settings-style canvas (light)
        accent: {
          DEFAULT: "#2563eb", // blue-600
          subtle: "#3b82f6",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Text",
          "Inter",
          "Segoe UI",
          "sans-serif",
        ],
        mono: ["SF Mono", "ui-monospace", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
