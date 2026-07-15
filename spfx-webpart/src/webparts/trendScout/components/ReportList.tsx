
import * as React from 'react';
import { useEffect, useState } from 'react';

interface Report {
  id: string;
  title: string | null;
  report_type: string;
  status: string;
  created_at: string;
}

interface ReportListProps {
  apiBaseUrl: string;
  headers: Record<string, string>;
}

export function ReportList(props: ReportListProps): React.ReactElement<ReportListProps> {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const token = props.headers['X-Embed-Token'];
    if (!token) return;
    fetch(`${props.apiBaseUrl}/reports`, {
      headers: props.headers,
    })
      .then((res) => res.json())
      .then((data) => {
        setReports(data.reports || []);
        setLoading(false);
      });
  }, [props.apiBaseUrl, props.headers]);

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
