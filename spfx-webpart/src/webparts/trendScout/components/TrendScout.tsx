
import * as React from 'react';
import { useEffect, useState } from 'react';
import { ITrendScoutProps } from './ITrendScoutProps';
import { SignalList } from './SignalList';
import { SourceList } from './SourceList';
import { TrendChart } from './TrendChart';
import { ReportList } from './ReportList';

export default function TrendScout(props: ITrendScoutProps): React.ReactElement<ITrendScoutProps> {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!props.embedToken) {
      setError('Embed token is required in web part settings. Generate one from Trend Scout workspace settings.');
    } else {
      setError(null);
    }
  }, [props.embedToken]);

  const headers: Record<string, string> = {
    'X-Embed-Token': props.embedToken,
    'X-Workspace-ID': props.workspaceId,
  };

  return (
    <div>
      <h2>Trend Scout</h2>
      {error && <div style={{ color: 'red' }}>{error}</div>}
      {props.view === 'signals' && <SignalList apiBaseUrl={props.apiBaseUrl} headers={headers} />}
      {props.view === 'sources' && <SourceList apiBaseUrl={props.apiBaseUrl} headers={headers} />}
      {props.view === 'trends' && <TrendChart apiBaseUrl={props.apiBaseUrl} headers={headers} />}
      {props.view === 'reports' && <ReportList apiBaseUrl={props.apiBaseUrl} headers={headers} />}
    </div>
  );
}
