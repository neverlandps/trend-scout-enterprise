
export interface ITrendScoutWebPartProps {
  apiBaseUrl: string;
  apiKey: string;
  workspaceId: string;
  view: 'signals' | 'sources' | 'trends' | 'reports';
}
