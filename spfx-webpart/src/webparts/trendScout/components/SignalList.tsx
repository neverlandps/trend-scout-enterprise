
import * as React from 'react';
import { useEffect, useState } from 'react';

interface Signal {
  id: string;
  title: string | null;
  summary: string | null;
  overall_score: number | null;
  collected_at: string;
}

interface SignalListProps {
  apiBaseUrl: string;
  headers: Record<string, string>;
}

export function SignalList(props: SignalListProps): React.ReactElement<SignalListProps> {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = props.headers['X-Embed-Token'];
    if (!token) return;
    setLoading(true);
    fetch(`${props.apiBaseUrl}/signals?limit=20`, {
      headers: {
        ...props.headers,
        'Content-Type': 'application/json',
      },
    })
      .then((res) => res.json())
      .then((data) => {
        setSignals(data.signals || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [props.apiBaseUrl, props.headers]);

  if (loading) return <div>Loading signals...</div>;
  if (error) return <div style={{ color: 'red' }}>{error}</div>;

  return (
    <ul>
      {signals.map((s) => (
        <li key={s.id}>
          <strong>{s.title || 'Untitled'}</strong>
          <div>{s.summary || ''}</div>
          <div>Score: {s.overall_score ? s.overall_score.toFixed(2) : '—'}</div>
        </li>
      ))}
    </ul>
  );
}
