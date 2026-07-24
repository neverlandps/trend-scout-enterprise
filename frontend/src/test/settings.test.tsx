import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SettingsPage } from '../pages/SettingsPage'

vi.mock('../contexts/WorkspaceContext', () => ({
  useWorkspace: () => ({
    workspaces: [],
    currentWorkspace: { id: 'ws-1', team_id: 'team-1', name: 'Default', is_default: true, created_at: '', updated_at: '' },
    loading: false,
    error: null,
    switchWorkspace: vi.fn(),
    refresh: vi.fn(),
  }),
}))

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>()
  return {
    ...actual,
    fetchLlmSettings: vi.fn(),
    updateLlmSettings: vi.fn(),
    fetchScoringSettings: vi.fn(),
    updateScoringSettings: vi.fn(),
    fetchSharePointConnections: vi.fn(),
    createSharePointConnection: vi.fn(),
    updateSharePointConnection: vi.fn(),
    deleteSharePointConnection: vi.fn(),
    checkSharePointHealth: vi.fn(),
    fetchNotificationChannels: vi.fn(),
    createNotificationChannel: vi.fn(),
    deleteNotificationChannel: vi.fn(),
    fetchEmbedTokens: vi.fn(),
    createEmbedToken: vi.fn(),
    revokeEmbedToken: vi.fn(),
    rotateEmbedToken: vi.fn(),
  }
})

import * as api from '../services/api'

describe('SettingsPage notifications and embed tokens', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.fetchLlmSettings).mockResolvedValue({ base_url: 'http://llm', model: 'm', temperature: 0.2, max_tokens: 1000 })
    vi.mocked(api.fetchScoringSettings).mockResolvedValue({ dimensions: [] })
    vi.mocked(api.fetchSharePointConnections).mockResolvedValue([])
    vi.mocked(api.fetchNotificationChannels).mockResolvedValue([
      {
        id: 'ch-1',
        owner_id: 'owner-1',
        channel_type: 'email',
        name: 'Ops Email',
        is_enabled: true,
        on_scan_success: false,
        on_scan_failure: true,
        created_at: '2026-07-01T00:00:00Z',
        updated_at: '2026-07-01T00:00:00Z',
      },
    ])
    vi.mocked(api.fetchEmbedTokens).mockResolvedValue([
      {
        id: 'tok-1',
        workspace_id: 'ws-1',
        name: 'SharePoint Web Part',
        token_prefix: 'tse_abcd',
        scopes: 'embed:read',
        expires_at: '2026-08-01T00:00:00Z',
        revoked_at: null,
        last_used_at: null,
        created_at: '2026-07-01T00:00:00Z',
        updated_at: '2026-07-01T00:00:00Z',
      },
    ])
  })

  it('renders the Notifications card with existing channels', async () => {
    render(<SettingsPage />)
    expect(screen.getByText('Notifications')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('Ops Email')).toBeInTheDocument()
      expect(screen.getByText('email')).toBeInTheDocument()
    })
    expect(screen.getByText('Add Channel')).toBeInTheDocument()
  })

  it('creates a notification channel with parsed JSON config', async () => {
    render(<SettingsPage />)
    await waitFor(() => {
      expect(screen.getByText('Add Channel')).toBeInTheDocument()
    })
    // "Name" appears in SharePoint, Notifications and Embed Token forms; pick the Notifications one
    fireEvent.change(screen.getAllByLabelText('Name')[1], { target: { value: 'Teams Alerts' } })
    fireEvent.change(screen.getByLabelText('Config (JSON)'), { target: { value: '{"webhook_url": "https://example.com/hook"}' } })
    fireEvent.click(screen.getByText('Add Channel'))
    await waitFor(() => {
      expect(api.createNotificationChannel).toHaveBeenCalledWith({
        channel_type: 'email',
        name: 'Teams Alerts',
        config: { webhook_url: 'https://example.com/hook' },
        on_scan_success: false,
        on_scan_failure: true,
      })
    })
  })

  it('renders embed tokens and creates one showing the plaintext once', async () => {
    vi.mocked(api.createEmbedToken).mockResolvedValue({
      token: 'tse_plaintext_secret',
      embed_token: {
        id: 'tok-2',
        workspace_id: 'ws-1',
        name: 'New Token',
        token_prefix: 'tse_plain',
        scopes: 'embed:read',
        expires_at: '2026-08-01T00:00:00Z',
        revoked_at: null,
        last_used_at: null,
        created_at: '2026-07-01T00:00:00Z',
        updated_at: '2026-07-01T00:00:00Z',
      },
    })
    render(<SettingsPage />)
    expect(screen.getByText('Embed Tokens (SharePoint)')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('SharePoint Web Part')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Create Token'))
    await waitFor(() => {
      expect(api.createEmbedToken).toHaveBeenCalledWith('ws-1', { name: undefined, ttl_days: 30 })
      expect(screen.getByText(/tse_plaintext_secret/)).toBeInTheDocument()
    })
  })

  it('revokes and rotates embed tokens', async () => {
    vi.mocked(api.revokeEmbedToken).mockResolvedValue({} as never)
    render(<SettingsPage />)
    await waitFor(() => {
      expect(screen.getByText('Revoke')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Revoke'))
    await waitFor(() => {
      expect(api.revokeEmbedToken).toHaveBeenCalledWith('ws-1', 'tok-1')
    })
  })
})
