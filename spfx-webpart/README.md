# Trend Scout SPFx Web Part

This SharePoint Framework web part embeds read-only Trend Scout Enterprise views into SharePoint pages.

## Prerequisites

- Node.js 18.17.0+ (use `.nvmrc`)
- SPFx 1.20.0
- Trend Scout backend URL
- Valid Trend Scout **embed token** and **Workspace ID**

> **Security note:** do not use a full API key in the web part. Create a read-only embed token in the Trend Scout admin panel and paste that token here.

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
- **Embed Token** — Read-only embed token generated from Trend Scout.
- **Workspace ID** — Workspace to query.
- **Default View** — signals, sources, trends, or reports.

## Deployment

1. Upload `sharepoint/solution/*.sppkg` to your tenant **App Catalog**.
2. Approve the package for the site collection.
3. Add the **Trend Scout** web part to a modern page.
4. Configure the properties in the web part pane.
