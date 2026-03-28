'use client';

import { useExceptions, useResolveException } from '@/hooks/use-logistics';

export default function ExceptionsPage() {
  const { data: exceptions = [] } = useExceptions();
  const resolveException = useResolveException();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Exceptions Queue</h1>
      <div className="rounded border p-4">
        <ul className="space-y-2 text-sm">
          {exceptions.length === 0 ? <li>No delivery exceptions.</li> : exceptions.map((item) => (
            <li key={item.id} className="rounded border px-3 py-2">
              <div className="font-medium">Shipment {item.shipment_id} · {item.exception_type} · {item.is_resolved ? 'Resolved' : 'Open'}</div>
              <div className="text-gray-600">{item.details}</div>
              {!item.is_resolved && (
                <button
                  className="mt-2 rounded bg-green-600 px-3 py-1 text-white"
                  onClick={() => resolveException.mutate({ exceptionId: item.id, resolution_notes: 'Resolved from exceptions queue' })}
                >
                  Resolve
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
