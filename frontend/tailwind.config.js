/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
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
          DEFAULT: 'var(--ws-bg)',
          canvas: 'var(--ws-canvas)',
          surface: 'var(--ws-surface)',
          elevated: 'var(--ws-elevated)',
          border: 'var(--ws-border)',
          muted: 'var(--ws-muted)',
        },
        sidebar: {
          DEFAULT: 'var(--sb-bg)',
          elevated: 'var(--sb-elevated)',
          border: 'var(--sb-border)',
        },
        theme: {
          heading: 'var(--color-heading)',
          strong: 'var(--color-strong)',
          body: 'var(--color-body)',
          muted: 'var(--color-muted)',
          faint: 'var(--color-faint)',
        },
      },
      fontFamily: {
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
