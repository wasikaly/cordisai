/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // CordisAI brand palette — red/crimson on dark
        primary: {
          50:  '#2a0a12',
          100: '#3d1020',
          200: '#5c1a32',
          300: '#9f1239',
          400: '#e11d48',
          500: '#f43f5e',
          600: '#e11d48',
          700: '#be123c',
          800: '#9f1239',
          900: '#881337',
          950: '#4c0519',
        },
        accent: {
          500: '#3b82f6',
          600: '#2563eb',
        },
        danger: {
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
        },
        warning: {
          400: '#fbbf24',
          500: '#f59e0b',
        },
        success: {
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
        },
        sidebar: {
          DEFAULT: '#0f0f12',
          foreground: '#ffffff',
          border: '#1e1e26',
          accent: '#1a1a24',
          'accent-foreground': '#fda4af',
        },
        card: {
          DEFAULT: '#141419',
          foreground: '#e2e8f0',
        },
        muted: {
          DEFAULT: '#0a0a0e',
          foreground: '#94a3b8',
        },
        border: '#1e1e2a',
        // Dark surface levels
        surface: {
          0: '#0a0a0e',
          1: '#111116',
          2: '#141419',
          3: '#1a1a22',
          4: '#22222e',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        lg: '0.75rem',
        md: '0.5rem',
        sm: '0.375rem',
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(0 0 0 / 0.3), 0 1px 2px -1px rgb(0 0 0 / 0.3)',
        'card-hover': '0 4px 6px -1px rgb(0 0 0 / 0.4), 0 2px 4px -2px rgb(0 0 0 / 0.3)',
        panel: '0 10px 15px -3px rgb(0 0 0 / 0.2)',
        glow: '0 0 20px rgb(225 29 72 / 0.15)',
      },
    },
  },
  plugins: [],
}
