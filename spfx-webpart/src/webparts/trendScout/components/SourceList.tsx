
import * as React from 'react';
import { useEffect, useState } from 'react';

interface Source {
  id: string;
  name: string;
  source_type: string;
  health_status: string;
  last_scan_at: string | null;
}

interface SourceListProps {
  apiBaseUrl: string;
  headers: Record<string, string>;
}

export function SourceList(props: SourceListProps): React.ReactElement<SourceListProps> {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const token = props.headers['X-Embed-Token'];
    if (!token) return;
    fetch(`${props.apiBaseUrl}/sources`, {
      headers: props.headers,
    })
      .then((res) => res.json())
      .then((data) => {
        setSources(data.sources || []);
        setLoading(false);
      });
  }, [props.apiBaseUrl, props.headers]);

  if (loading) return <div>Loading sources...</div>;

  return (
    <ul>
      {sources.map((s) => (
        <li key={s.id}>
          {s.name} ({s.source_type}) — {s.health_status}
        </li>
      ))}
    </ul>
  );
}
