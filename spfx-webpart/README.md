# Trend Scout SPFx Web Part

This SharePoint Framework web part embeds the Trend Scout Enterprise dashboard into SharePoint pages.

## Prerequisites

- Node.js 18.17.0+ (use `.nvmrc`)
- SPFx 1.20.0
- Valid Trend Scout API key and Workspace ID

## Build

```bash
cd spfx-webpart
npm install
npm run build
npm run package
```

The packaged `.sppkg` file is created at `sharepoint/solution/trend-scout-spfx-webpart.sppkg`.

## Configuration

After adding the web part to a SharePoint page, configure:

- **API Base URL** — URL of the Trend Scout backend (e.g. `https://api.example.com/api/v1`).
- **API Key** — Trend Scout API key.
- **Workspace ID** — Workspace to query.
- **Default View** — signals, sources, trends, or reports.
