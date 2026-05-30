'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

interface TrackingEvent {
  id: number;
  status: string;
  message: string;
  created_at: string;
}

interface TrackingPayload {
  shipment: {
    reference: string;
    current_status: string;
  };
  timeline: TrackingEvent[];
}

async function getTracking(token: string) {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';
  const response = await fetch(`${baseUrl}/tracking/${token}`);
  if (!response.ok) return null;
  return (await response.json()) as TrackingPayload;
}

export default function PublicTrackingPage() {
  const { token = '' } = useParams<{ token: string }>();
  const [data, setData] = useState<TrackingPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadData() {
      setIsLoading(true);
      const response = await getTracking(token);
      if (isMounted) {
        setData(response);
        setIsLoading(false);
      }
    }

    if (token) {
      loadData();
    } else {
      setData(null);
      setIsLoading(false);
    }

    return () => {
      isMounted = false;
    };
  }, [token]);

  if (isLoading) {
    return <div className="mx-auto max-w-2xl p-10">Loading tracking details...</div>;
  }

  if (!data) {
    return <div className="mx-auto max-w-2xl p-10">Tracking reference not found.</div>;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-10">
      <h1 className="text-2xl font-semibold">Track Shipment {data.shipment.reference}</h1>
      <p className="text-sm text-gray-600">Current status: {data.shipment.current_status}</p>
      <ol className="space-y-2 rounded border p-4 text-sm">
        {data.timeline.map((event) => (
          <li key={event.id} className="rounded border px-3 py-2">
            <div className="font-medium">{event.status}</div>
            <div>{event.message}</div>
            <div className="text-xs text-gray-500">{new Date(event.created_at).toLocaleString()}</div>
          </li>
        ))}
      </ol>
    </div>
  );
}
