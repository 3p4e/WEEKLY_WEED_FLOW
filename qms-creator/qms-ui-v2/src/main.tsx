import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/globals.css'
// Initialize i18n before rendering
import './i18n'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
