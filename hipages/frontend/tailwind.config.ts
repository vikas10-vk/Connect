import type { Config } from 'tailwindcss'

const config: Config = {
 content: [
 './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
 './src/components/**/*.{js,ts,jsx,tsx,mdx}',
 './src/app/**/*.{js,ts,jsx,tsx,mdx}',
 ],
 theme: {
 extend: {
 colors: {
 brand: {
 terracotta: '#071D36',
 cream: '#FFF8E7',
 navy: '#071D36',
 gold: '#D4AA3A',
 ivory: '#FFF8E7',
 sand: '#F5EDD0',
 iconblue: '#5BB3FF',
 },
 },
 fontSize: {
 '6xl': '3.75rem',
 '7xl': '4.5rem',
 },
 spacing: {
 '18': '4.5rem',
 },
 borderRadius: {
 'xl': '0.75rem',
 '2xl': '1rem',
 '2.5rem': '2.5rem',
 },
 boxShadow: {
 'sm': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
 'lg': '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
 'xl': '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
 },
 animation: {
 'fade-in': 'fadeIn 0.5s ease-in',
 },
 keyframes: {
 fadeIn: {
 '0%': { opacity: '0' },
 '100%': { opacity: '1' },
 },
 },
 },
 },
 plugins: [],
}
export default config
