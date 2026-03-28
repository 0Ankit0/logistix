'use client';

import { useState } from 'react';

export default function TrackingConsolePage() {
  const [token, setToken] = useState('');

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Tracking Console</h1>
      <p className="text-sm text-gray-600">
        Track shipment checkpoints, ETA updates, and milestone events in real time via websocket notifications.
      </p>
      <div className="flex gap-2">
        <input
          className="w-full rounded border px-3 py-2"
          placeholder="Enter public tracking token"
          value={token}
          onChange={(event) => setToken(event.target.value)}
        />
        <a
          href={token ? `/track/${token}` : '#'}
          className="rounded bg-blue-600 px-4 py-2 text-white"
        >
          Open
        </a>
      </div>
    </div>
  );
}
