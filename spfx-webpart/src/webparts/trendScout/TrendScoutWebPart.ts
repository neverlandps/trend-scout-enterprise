
import * as React from 'react';
import * as ReactDOM from 'react-dom';
import { Version } from '@microsoft/sp-core-library';
import {
  IPropertyPaneConfiguration,
  PropertyPaneTextField,
  PropertyPaneChoiceGroup,
} from '@microsoft/sp-property-pane';
import { BaseClientSideWebPart } from '@microsoft/sp-webpart-base';
import { ITrendScoutWebPartProps } from './ITrendScoutWebPartProps';
import TrendScout from './components/TrendScout';

export default class TrendScoutWebPart extends BaseClientSideWebPart<ITrendScoutWebPartProps> {
  public render(): void {
    const element = React.createElement(
      TrendScout,
      {
        apiBaseUrl: this.properties.apiBaseUrl || 'https://your-trend-scout-api.example.com/api/v1',
        apiKey: this.properties.apiKey || '',
        workspaceId: this.properties.workspaceId || '',
        view: this.properties.view || 'signals',
      }
    );
    ReactDOM.render(element, this.domElement);
  }

  protected onDispose(): void {
    ReactDOM.unmountComponentAtNode(this.domElement);
  }

  protected get dataVersion(): Version {
    return Version.parse('1.0');
  }

  protected getPropertyPaneConfiguration(): IPropertyPaneConfiguration {
    return {
      pages: [
        {
          header: {
            description: 'Trend Scout API Settings',
          },
          groups: [
            {
              groupName: 'Connection',
              groupFields: [
                PropertyPaneTextField('apiBaseUrl', {
                  label: 'API Base URL',
                  value: 'https://your-trend-scout-api.example.com/api/v1',
                }),
                PropertyPaneTextField('apiKey', {
                  label: 'API Key',
                }),
                PropertyPaneTextField('workspaceId', {
                  label: 'Workspace ID',
                }),
              ],
            },
            {
              groupName: 'View',
              groupFields: [
                PropertyPaneChoiceGroup('view', {
                  label: 'Default View',
                  options: [
                    { key: 'signals', text: 'Signals' },
                    { key: 'sources', text: 'Sources' },
                    { key: 'trends', text: 'Trends' },
                    { key: 'reports', text: 'Reports' },
                  ],
                }),
              ],
            },
          ],
        },
      ],
    };
  }
}
