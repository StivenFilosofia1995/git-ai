/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'teatro': '#DC2626',
        'hip-hop': '#F59E0B',
        'jazz': '#7C3AED',
        'electronica': '#06B6D4',
        'galeria': '#EC4899',
        'libreria': '#10B981',
        'casa-cultura': '#3B82F6',
        'festival': '#F97316',
        'poesia': '#8B5CF6',
        'underground': '#1F2937'
      },
      fontFamily: {
        'heading': ['Sora', 'sans-serif'],
        'sans': ['DM Sans', 'sans-serif'],
        'mono': ['JetBrains Mono', 'monospace'],
      }
    },
  },
  plugins: [],
}