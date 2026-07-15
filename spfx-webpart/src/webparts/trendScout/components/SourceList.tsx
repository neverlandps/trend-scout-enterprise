
import * as React from 'react';
import { useEffect, useState } from 'react';
import { ITrendScoutProps } from './ITrendScoutProps';

interface Source {
  id: string;
  name: string;
  source_type: string;
  health_status: string;
  last_scan_at: string | null;
}

export function SourceList(props: ITrendScoutProps): React.ReactElement<ITrendScoutProps> {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!props.apiKey) return;
    fetch(`${props.apiBaseUrl}/sources`, {
      headers: { 'X-API-Key': props.apiKey, 'X-Workspace-ID': props.workspaceId },
    })
      .then((res) => res.json())
      .then((data) => {
        setSources(data.sources || []);
        setLoading(false);
      });
  }, [props.apiBaseUrl, props.apiKey, props.workspaceId]);

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
