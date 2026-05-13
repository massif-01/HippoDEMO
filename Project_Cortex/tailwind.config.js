/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        // Open WebUI color scheme
        'gray': {
          50: '#fafafa',
          100: '#f5f5f5',
          200: '#e5e5e5',
          300: '#d4d4d4',
          400: '#a3a3a3',
          500: '#737373',
          600: '#525252',
          700: '#404040',
          800: '#262626',
          850: '#1f1f1f',
          900: '#171717',
          950: '#0a0a0a'
        }
      }
    }
  },
  plugins: [
    require('@tailwindcss/typography')
  ]
}
