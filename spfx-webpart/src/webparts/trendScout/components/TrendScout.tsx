
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
    if (!props.apiKey) {
      setError('API Key is required in web part settings.');
    } else {
      setError(null);
    }
  }, [props.apiKey]);

  return (
    <div>
      <h2>Trend Scout</h2>
      {error && <div style={{ color: 'red' }}>{error}</div>}
      {props.view === 'signals' && <SignalList {...props} />}
      {props.view === 'sources' && <SourceList {...props} />}
      {props.view === 'trends' && <TrendChart {...props} />}
      {props.view === 'reports' && <ReportList {...props} />}
    </div>
  );
}
