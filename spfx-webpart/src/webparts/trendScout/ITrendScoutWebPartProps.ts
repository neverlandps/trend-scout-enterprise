export interface ITrendScoutWebPartProps {
  apiBaseUrl: string;
  embedToken: string;
  workspaceId: string;
  view: 'signals' | 'sources' | 'trends' | 'reports';
}
