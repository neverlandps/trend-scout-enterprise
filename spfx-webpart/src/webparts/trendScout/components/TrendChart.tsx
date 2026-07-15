
import * as React from 'react';
import { useEffect, useState } from 'react';

interface TrendPoint {
  date_bucket: string;
  avg_overall_score: number | null;
  item_count: number;
}

interface TrendChartProps {
  apiBaseUrl: string;
  headers: Record<string, string>;
}

export function TrendChart(props: TrendChartProps): React.ReactElement<TrendChartProps> {
  const [points, setPoints] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const token = props.headers['X-Embed-Token'];
    if (!token) return;
    fetch(`${props.apiBaseUrl}/trends/series?granularity=week`, {
      headers: props.headers,
    })
      .then((res) => res.json())
      .then((data) => {
        const series = data.series && data.series[0] ? data.series[0].points : [];
        setPoints(series);
        setLoading(false);
      });
  }, [props.apiBaseUrl, props.headers]);

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
