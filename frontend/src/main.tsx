import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
function App() {
  const [status, setStatus] = useState('Connecting…');
  useEffect(() => {fetch('/api/health').then(r => {if (!r.ok) throw Error(); return r.json()}).then(() => setStatus('Connected to local backend')).catch(() => setStatus('Backend unavailable. Start FastAPI on port 8000.'));}, []);
  return <main><h1>LedgerLens</h1><p>Understand every transaction. Trust every total.</p><p>{status}</p></main>;
}
createRoot(document.getElementById('root')!).render(<StrictMode><App/></StrictMode>);
