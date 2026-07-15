
import * as React from 'react';
import { useEffect, useState } from 'react';
import { ITrendScoutProps } from './ITrendScoutProps';

interface Signal {
  id: string;
  title: string | null;
  summary: string | null;
  overall_score: number | null;
  collected_at: string;
}

export function SignalList(props: ITrendScoutProps): React.ReactElement<ITrendScoutProps> {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!props.apiKey) return;
    setLoading(true);
    fetch(`${props.apiBaseUrl}/signals?limit=20`, {
      headers: {
        'X-API-Key': props.apiKey,
        'X-Workspace-ID': props.workspaceId,
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
  }, [props.apiBaseUrl, props.apiKey, props.workspaceId]);

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
