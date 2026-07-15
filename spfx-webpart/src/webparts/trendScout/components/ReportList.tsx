
import * as React from 'react';
import { useEffect, useState } from 'react';
import { ITrendScoutProps } from './ITrendScoutProps';

interface Report {
  id: string;
  title: string | null;
  report_type: string;
  status: string;
  created_at: string;
}

export function ReportList(props: ITrendScoutProps): React.ReactElement<ITrendScoutProps> {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!props.apiKey) return;
    fetch(`${props.apiBaseUrl}/reports`, {
      headers: { 'X-API-Key': props.apiKey, 'X-Workspace-ID': props.workspaceId },
    })
      .then((res) => res.json())
      .then((data) => {
        setReports(data.reports || []);
        setLoading(false);
      });
  }, [props.apiBaseUrl, props.apiKey, props.workspaceId]);

  if (loading) return <div>Loading reports...</div>;

  return (
    <ul>
      {reports.map((r) => (
        <li key={r.id}>
          {r.title || r.report_type} — {r.status}
        </li>
      ))}
    </ul>
  );
}
