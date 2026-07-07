import { useState, useEffect } from 'react';

interface ExpiryTimerProps {
  expiresAt: string;
}

export function ExpiryTimer({ expiresAt }: ExpiryTimerProps) {
  const [remaining, setRemaining] = useState('');

  useEffect(() => {
    function tick() {
      const expiry = new Date(expiresAt).getTime();
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
  }, [expiresAt]);

  return (
    <div className="expiry-timer">
      <span className="expiry-label">Auto-expiry</span>
      <span className="expiry-value">{remaining}</span>
    </div>
  );
}
