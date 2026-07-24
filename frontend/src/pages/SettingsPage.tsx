import { DefaultButton, Dropdown, FontWeights, IDropdownOption, MessageBar, MessageBarType, PrimaryButton, Stack, Text, TextField, Toggle } from '@fluentui/react'
import { useEffect, useState } from 'react'
import { useWorkspace } from '../contexts/WorkspaceContext'
import {
  checkSharePointHealth,
  createEmbedToken,
  createNotificationChannel,
  createSharePointConnection,
  deleteNotificationChannel,
  deleteSharePointConnection,
  EmbedToken,
  fetchEmbedTokens,
  fetchLlmSettings,
  fetchNotificationChannels,
  fetchScoringSettings,
  fetchSharePointConnections,
  LlmSettings,
  NotificationChannel,
  revokeEmbedToken,
  rotateEmbedToken,
  ScoringDimension,
  ScoringSettings,
  SharePointConnection,
  updateLlmSettings,
  updateScoringSettings,
  updateSharePointConnection,
} from '../services/api'

interface SpForm {
  id?: string
  name: string
  site_id?: string
  site_url?: string
  list_id?: string
  drive_id?: string
  tenant_id: string
  client_id: string
  client_secret: string
  is_enabled?: boolean
  is_default?: boolean
}

export function SettingsPage() {
  const { currentWorkspace } = useWorkspace()
  const [llm, setLlm] = useState<LlmSettings | null>(null)
  const [scoring, setScoring] = useState<ScoringSettings | null>(null)
  const [spConnections, setSpConnections] = useState<SharePointConnection[]>([])
  const [spForm, setSpForm] = useState<Partial<SpForm>>({ is_enabled: true })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const [channels, setChannels] = useState<NotificationChannel[]>([])
  const [channelForm, setChannelForm] = useState({
    channel_type: 'email' as 'email' | 'teams_webhook',
    name: '',
    config: '',
    on_scan_success: false,
    on_scan_failure: true,
  })

  const [embedTokens, setEmbedTokens] = useState<EmbedToken[]>([])
  const [tokenForm, setTokenForm] = useState({ name: '', ttl_days: '30' })
  const [plaintextToken, setPlaintextToken] = useState<string | null>(null)

  const channelTypeOptions: IDropdownOption[] = [
    { key: 'email', text: 'Email' },
    { key: 'teams_webhook', text: 'Teams Webhook' },
  ]

  const configPlaceholder = (type: string) =>
    type === 'teams_webhook'
      ? '{"webhook_url": "https://outlook.office.com/webhook/..."}'
      : '{"recipients": ["user@example.com"], "smtp_host": "smtp.example.com"}'

  const load = async () => {
    setLoading(true)
    try {
      const [l, s, sp, nc] = await Promise.all([
        fetchLlmSettings(),
        fetchScoringSettings(),
        fetchSharePointConnections(),
        fetchNotificationChannels(),
      ])
      setLlm(l); setScoring(s); setSpConnections(sp); setChannels(nc)
      if (currentWorkspace) {
        try {
          setEmbedTokens(await fetchEmbedTokens(currentWorkspace.id))
        } catch {
          setEmbedTokens([])
        }
      }
    } catch (e) { setError(String(e)) } finally { setLoading(false) }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load() }, [currentWorkspace?.id])

  const saveLlm = async () => { if (!llm) return; try { await updateLlmSettings(llm); setSuccess(true); load() } catch (e) { setError(String(e)) } }
  const saveScoring = async () => { if (!scoring) return; try { await updateScoringSettings(scoring); setSuccess(true); load() } catch (e) { setError(String(e)) } }
  const updateDim = (idx: number, patch: Partial<ScoringDimension>) => { if (!scoring) return; const n = [...scoring.dimensions]; n[idx] = { ...n[idx], ...patch }; setScoring({ dimensions: n }) }

  const saveSp = async () => {
    if (!spForm.name || !spForm.tenant_id || !spForm.client_id) return
    try {
      if (spForm.id) {
        await updateSharePointConnection(spForm.id, spForm as SpForm)
      } else {
        await createSharePointConnection(spForm as SpForm)
      }
      setSuccess(true)
      setSpForm({ is_enabled: true })
      load()
    } catch (e) { setError(String(e)) }
  }

  const removeSp = async (id: string) => {
    try { await deleteSharePointConnection(id); setSuccess(true); load() } catch (e) { setError(String(e)) }
  }

  const checkSpHealth = async (id: string) => {
    try {
      const result = await checkSharePointHealth(id)
      alert(`SharePoint health: ${result.status} - ${result.message || ''}`)
    } catch (e) { setError(String(e)) }
  }

  const addChannel = async () => {
    if (!channelForm.name) { setError('Channel name is required.'); return }
    let config: Record<string, unknown>
    try {
      config = JSON.parse(channelForm.config || '{}')
    } catch {
      setError('Channel config must be valid JSON.')
      return
    }
    try {
      await createNotificationChannel({
        channel_type: channelForm.channel_type,
        name: channelForm.name,
        config,
        on_scan_success: channelForm.on_scan_success,
        on_scan_failure: channelForm.on_scan_failure,
      })
      setSuccess(true)
      setChannelForm({ channel_type: 'email', name: '', config: '', on_scan_success: false, on_scan_failure: true })
      load()
    } catch (e) { setError(String(e)) }
  }

  const removeChannel = async (id: string) => {
    try { await deleteNotificationChannel(id); setSuccess(true); load() } catch (e) { setError(String(e)) }
  }

  const addEmbedToken = async () => {
    if (!currentWorkspace) { setError('No workspace selected.'); return }
    const ttl = Number(tokenForm.ttl_days)
    if (!Number.isInteger(ttl) || ttl < 1 || ttl > 365) { setError('TTL must be between 1 and 365 days.'); return }
    try {
      const res = await createEmbedToken(currentWorkspace.id, {
        name: tokenForm.name || undefined,
        ttl_days: ttl,
      })
      setPlaintextToken(res.token)
      setTokenForm({ name: '', ttl_days: '30' })
      setSuccess(true)
      load()
    } catch (e) { setError(String(e)) }
  }

  const revokeToken = async (id: string) => {
    if (!currentWorkspace) return
    try { await revokeEmbedToken(currentWorkspace.id, id); setSuccess(true); load() } catch (e) { setError(String(e)) }
  }

  const rotateToken = async (id: string) => {
    if (!currentWorkspace) return
    try {
      const res = await rotateEmbedToken(currentWorkspace.id, id, {})
      setPlaintextToken(res.token)
      setSuccess(true)
      load()
    } catch (e) { setError(String(e)) }
  }

  return (
    <Stack tokens={{ childrenGap: 16 }}>
      <Text variant="xLarge" styles={{ root: { fontWeight: FontWeights.semibold } }}>Settings</Text>
      {error && <MessageBar messageBarType={MessageBarType.error} onDismiss={() => setError(null)}>{error}</MessageBar>}
      {success && <MessageBar messageBarType={MessageBarType.success} onDismiss={() => setSuccess(false)}>Saved.</MessageBar>}
      {loading && <Text>Loading...</Text>}
      {llm && (
        <Stack tokens={{ childrenGap: 8 }} styles={{ root: { border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 } }}>
          <Text variant="large" styles={{ root: { fontWeight: FontWeights.semibold } }}>LLM Provider</Text>
          <TextField label="Base URL" value={llm.base_url} onChange={(_, v) => setLlm({ ...llm, base_url: v || '' })} />
          <TextField label="Model" value={llm.model} onChange={(_, v) => setLlm({ ...llm, model: v || '' })} />
          <TextField label="Temperature" type="number" value={String(llm.temperature)} onChange={(_, v) => setLlm({ ...llm, temperature: Number(v || 0) })} />
          <TextField label="Max Tokens" type="number" value={String(llm.max_tokens)} onChange={(_, v) => setLlm({ ...llm, max_tokens: Number(v || 0) })} />
          <PrimaryButton text="Save LLM Settings" onClick={saveLlm} />
        </Stack>
      )}
      {scoring && (
        <Stack tokens={{ childrenGap: 8 }} styles={{ root: { border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 } }}>
          <Text variant="large" styles={{ root: { fontWeight: FontWeights.semibold } }}>Scoring Weights</Text>
          {scoring.dimensions.map((dim, idx) => (
            <Stack key={dim.name} horizontal tokens={{ childrenGap: 8 }} verticalAlign="center">
              <input type="checkbox" checked={dim.enabled} onChange={e => updateDim(idx, { enabled: e.target.checked })} />
              <Text styles={{ root: { width: 160 } }}>{dim.name}</Text>
              <TextField type="number" step={0.05} min={0} max={1} value={String(dim.weight)} onChange={(_, v) => updateDim(idx, { weight: Number(v || 0) })} />
            </Stack>
          ))}
          <DefaultButton text="Save Scoring Settings" onClick={saveScoring} />
        </Stack>
      )}
      <Stack tokens={{ childrenGap: 8 }} styles={{ root: { border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 } }}>
        <Text variant="large" styles={{ root: { fontWeight: FontWeights.semibold } }}>SharePoint Online</Text>
        <TextField label="Name" value={spForm.name || ''} onChange={(_, v) => setSpForm({ ...spForm, name: v })} />
        <TextField label="Site URL" value={spForm.site_url || ''} onChange={(_, v) => setSpForm({ ...spForm, site_url: v })} />
        <TextField label="List ID" value={spForm.list_id || ''} onChange={(_, v) => setSpForm({ ...spForm, list_id: v })} />
        <TextField label="Drive ID" value={spForm.drive_id || ''} onChange={(_, v) => setSpForm({ ...spForm, drive_id: v })} />
        <TextField label="Tenant ID" value={spForm.tenant_id || ''} onChange={(_, v) => setSpForm({ ...spForm, tenant_id: v })} />
        <TextField label="Client ID" value={spForm.client_id || ''} onChange={(_, v) => setSpForm({ ...spForm, client_id: v })} />
        <TextField label="Client Secret" type="password" value={spForm.client_secret || ''} onChange={(_, v) => setSpForm({ ...spForm, client_secret: v })} />
        <Stack horizontal tokens={{ childrenGap: 8 }}>
          <PrimaryButton text={spForm.id ? 'Update Connection' : 'Add Connection'} onClick={saveSp} />
          {spForm.id && <DefaultButton text="Cancel" onClick={() => setSpForm({ is_enabled: true })} />}
        </Stack>
        {spConnections.map(conn => (
          <Stack key={conn.id} horizontal tokens={{ childrenGap: 8 }} verticalAlign="center">
            <Text styles={{ root: { width: 200 } }}>{conn.name}</Text>
            <DefaultButton text="Edit" onClick={() => setSpForm({
              id: conn.id,
              name: conn.name,
              site_id: conn.site_id || undefined,
              site_url: conn.site_url || undefined,
              list_id: conn.list_id || undefined,
              drive_id: conn.drive_id || undefined,
              tenant_id: conn.tenant_id,
              client_id: conn.client_id,
              client_secret: '',
              is_enabled: conn.is_enabled,
              is_default: conn.is_default,
            })} />
            <DefaultButton text="Health" onClick={() => checkSpHealth(conn.id)} />
            <DefaultButton text="Delete" onClick={() => removeSp(conn.id)} />
          </Stack>
        ))}
      </Stack>
      <Stack tokens={{ childrenGap: 8 }} styles={{ root: { border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 } }}>
        <Text variant="large" styles={{ root: { fontWeight: FontWeights.semibold } }}>Notifications</Text>
        {channels.map(ch => (
          <Stack key={ch.id} horizontal tokens={{ childrenGap: 8 }} verticalAlign="center">
            <Text styles={{ root: { width: 140 } }}>{ch.name}</Text>
            <Text variant="small" styles={{ root: { width: 120, color: 'gray' } }}>{ch.channel_type}</Text>
            <Text variant="small" styles={{ root: { width: 100, color: ch.is_enabled ? 'green' : 'gray' } }}>
              {ch.is_enabled ? 'enabled' : 'disabled'}
            </Text>
            <Text variant="small" styles={{ root: { color: 'gray' } }}>
              success: {ch.on_scan_success ? 'on' : 'off'} | failure: {ch.on_scan_failure ? 'on' : 'off'}
            </Text>
            <DefaultButton text="Delete" onClick={() => removeChannel(ch.id)} />
          </Stack>
        ))}
        {channels.length === 0 && <Text variant="small" styles={{ root: { color: 'gray' } }}>No notification channels yet.</Text>}
        <Dropdown
          label="Type"
          selectedKey={channelForm.channel_type}
          options={channelTypeOptions}
          onChange={(_, o) => setChannelForm({ ...channelForm, channel_type: o?.key as 'email' | 'teams_webhook' })}
          styles={{ dropdown: { width: 220 } }}
        />
        <TextField label="Name" value={channelForm.name} onChange={(_, v) => setChannelForm({ ...channelForm, name: v || '' })} />
        <TextField
          label="Config (JSON)"
          multiline
          rows={3}
          value={channelForm.config}
          onChange={(_, v) => setChannelForm({ ...channelForm, config: v || '' })}
          placeholder={configPlaceholder(channelForm.channel_type)}
          description={`Example: ${configPlaceholder(channelForm.channel_type)}`}
        />
        <Stack horizontal tokens={{ childrenGap: 16 }}>
          <Toggle
            label="On scan success"
            checked={channelForm.on_scan_success}
            onChange={(_, v) => setChannelForm({ ...channelForm, on_scan_success: !!v })}
          />
          <Toggle
            label="On scan failure"
            checked={channelForm.on_scan_failure}
            onChange={(_, v) => setChannelForm({ ...channelForm, on_scan_failure: !!v })}
          />
        </Stack>
        <PrimaryButton text="Add Channel" onClick={addChannel} styles={{ root: { alignSelf: 'flex-start' } }} />
      </Stack>
      <Stack tokens={{ childrenGap: 8 }} styles={{ root: { border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 } }}>
        <Text variant="large" styles={{ root: { fontWeight: FontWeights.semibold } }}>Embed Tokens (SharePoint)</Text>
        {plaintextToken && (
          <MessageBar messageBarType={MessageBarType.warning} onDismiss={() => setPlaintextToken(null)}>
            Token created. Copy it now - it will not be shown again: <code>{plaintextToken}</code>
          </MessageBar>
        )}
        {embedTokens.map(t => (
          <Stack key={t.id} horizontal tokens={{ childrenGap: 8 }} verticalAlign="center">
            <Text styles={{ root: { width: 160 } }}>{t.name}</Text>
            <Text variant="small" styles={{ root: { width: 100, color: 'gray' } }}>{t.token_prefix}...</Text>
            <Text variant="small" styles={{ root: { width: 170, color: 'gray' } }}>
              expires: {new Date(t.expires_at).toLocaleDateString()}
            </Text>
            <Text variant="small" styles={{ root: { width: 90, color: t.revoked_at ? 'red' : 'green' } }}>
              {t.revoked_at ? 'revoked' : 'active'}
            </Text>
            {!t.revoked_at && (
              <>
                <DefaultButton text="Revoke" onClick={() => revokeToken(t.id)} />
                <DefaultButton text="Rotate" onClick={() => rotateToken(t.id)} />
              </>
            )}
          </Stack>
        ))}
        {embedTokens.length === 0 && <Text variant="small" styles={{ root: { color: 'gray' } }}>No embed tokens yet.</Text>}
        <Stack horizontal tokens={{ childrenGap: 8 }} verticalAlign="end">
          <TextField label="Name" value={tokenForm.name} onChange={(_, v) => setTokenForm({ ...tokenForm, name: v || '' })} placeholder="SharePoint Web Part" />
          <TextField label="TTL (days)" type="number" min={1} max={365} value={tokenForm.ttl_days} onChange={(_, v) => setTokenForm({ ...tokenForm, ttl_days: v || '30' })} />
          <PrimaryButton text="Create Token" onClick={addEmbedToken} />
        </Stack>
      </Stack>
    </Stack>
  )
}
