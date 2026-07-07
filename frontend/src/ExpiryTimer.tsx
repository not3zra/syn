import { useState, useEffect } from 'react';

interface ExpiryTimerProps {
  timestamp: string;
}

export function ExpiryTimer({ timestamp }: ExpiryTimerProps) {
  const [remaining, setRemaining] = useState('');

  useEffect(() => {
    function tick() {
      const created = new Date(timestamp).getTime();
      const expiry = created + 4 * 60 * 60 * 1000;
      const now = Date.now();
      const diff = expiry - now;

      if (diff <= 0) {
        setRemaining('Expired');
        return;
      }

      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const secs = Math.floor((diff % (1000 * 60)) / 1000);
      setRemaining(`${hours}h ${minutes}m ${secs}s`);
    }

    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [timestamp]);

  return (
    <div className="expiry-timer">
      <span className="expiry-label">Auto-expiry</span>
      <span className="expiry-value">{remaining}</span>
    </div>
  );
}
