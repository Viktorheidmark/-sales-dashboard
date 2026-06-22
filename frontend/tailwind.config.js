/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef2ff',
          100: '#dce6ff',
          400: '#5b8aff',
          500: '#4d7cff',
          600: '#3d66e0',
          700: '#2f52c4',
        },
        workspace: {
          DEFAULT: '#0e1218',
          canvas: '#121820',
          surface: '#161d27',
          elevated: '#1c2531',
          border: '#2a3544',
          muted: '#131a22',
        },
        sidebar: {
          DEFAULT: '#060a0f',
          elevated: '#0c1118',
          border: '#151c26',
        },
      },
      fontFamily: {
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
