
import * as React from 'react';
import { useEffect, useState } from 'react';
import { ITrendScoutProps } from './ITrendScoutProps';

interface TrendPoint {
  date_bucket: string;
  avg_overall_score: number | null;
  item_count: number;
}

export function TrendChart(props: ITrendScoutProps): React.ReactElement<ITrendScoutProps> {
  const [points, setPoints] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!props.apiKey) return;
    fetch(`${props.apiBaseUrl}/trends/series?granularity=week`, {
      headers: { 'X-API-Key': props.apiKey, 'X-Workspace-ID': props.workspaceId },
    })
      .then((res) => res.json())
      .then((data) => {
        const series = data.series && data.series[0] ? data.series[0].points : [];
        setPoints(series);
        setLoading(false);
      });
  }, [props.apiBaseUrl, props.apiKey, props.workspaceId]);

  if (loading) return <div>Loading trends...</div>;

  return (
    <div>
      {points.map((p) => (
        <div key={p.date_bucket}>
          {p.date_bucket}: avg score {p.avg_overall_score ? p.avg_overall_score.toFixed(2) : '—'} ({p.item_count} items)
        </div>
      ))}
    </div>
  );
}
