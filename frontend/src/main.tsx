import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ChampionPreloader } from './components/ChampionPreloader'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ChampionPreloader>
      <App />
    </ChampionPreloader>
  </StrictMode>,
)
