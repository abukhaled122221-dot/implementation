/**
 * إعدادات Tailwind المشتركة لكل صفحات ثقة (ألوان الهوية + الخط).
 * يجب تحميل هذا الملف مباشرة بعد سكربت Tailwind CDN.
 */
tailwind.config = {
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eefdf4",
          100: "#d7fbe4",
          500: "#10b981",
          600: "#059669",
          700: "#047857",
          900: "#064e3b",
        },
        navy: {
          800: "#0f172a",
          900: "#020617",
        },
      },
      fontFamily: {
        sans: ["Tajawal", "sans-serif"],
      },
    },
  },
};
