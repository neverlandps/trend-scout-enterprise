import { DefaultButton, FontWeights, MessageBar, MessageBarType, PrimaryButton, Stack, Text, TextField } from '@fluentui/react'
import { useEffect, useState } from 'react'
import {
  checkSharePointHealth,
  createSharePointConnection,
  deleteSharePointConnection,
  fetchLlmSettings,
  fetchScoringSettings,
  fetchSharePointConnections,
  LlmSettings,
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
  const [llm, setLlm] = useState<LlmSettings | null>(null)
  const [scoring, setScoring] = useState<ScoringSettings | null>(null)
  const [spConnections, setSpConnections] = useState<SharePointConnection[]>([])
  const [spForm, setSpForm] = useState<Partial<SpForm>>({ is_enabled: true })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [l, s, sp] = await Promise.all([
        fetchLlmSettings(),
        fetchScoringSettings(),
        fetchSharePointConnections(),
      ])
      setLlm(l); setScoring(s); setSpConnections(sp)
    } catch (e) { setError(String(e)) } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

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
    </Stack>
  )
}
