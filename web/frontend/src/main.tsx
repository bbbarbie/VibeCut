import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import { Polish } from './components/Polish.tsx'
import './index.css'

// #polish is its own page: a finished video and the creator pointing at it.
// It shares nothing with the storyboard editor but the server.
function Root() {
  const [polish, setPolish] = useState(window.location.hash === '#polish')
  useEffect(() => {
    const change = () => setPolish(window.location.hash === '#polish')
    window.addEventListener('hashchange', change)
    return () => window.removeEventListener('hashchange', change)
  }, [])
  return polish ? <Polish /> : <App />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
