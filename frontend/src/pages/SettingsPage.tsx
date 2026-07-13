import { DefaultButton, FontWeights, MessageBar, MessageBarType, PrimaryButton, Stack, Text, TextField } from '@fluentui/react'
import { useEffect, useState } from 'react'
import { fetchLlmSettings, fetchScoringSettings, LlmSettings, ScoringDimension, ScoringSettings, updateLlmSettings, updateScoringSettings } from '../services/api'

export function SettingsPage() {
  const [llm, setLlm] = useState<LlmSettings | null>(null)
  const [scoring, setScoring] = useState<ScoringSettings | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [l, s] = await Promise.all([fetchLlmSettings(), fetchScoringSettings()])
      setLlm(l); setScoring(s)
    } catch (e) { setError(String(e)) } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const saveLlm = async () => { if (!llm) return; try { await updateLlmSettings(llm); setSuccess(true); load() } catch (e) { setError(String(e)) } }
  const saveScoring = async () => { if (!scoring) return; try { await updateScoringSettings(scoring); setSuccess(true); load() } catch (e) { setError(String(e)) } }
  const updateDim = (idx: number, patch: Partial<ScoringDimension>) => { if (!scoring) return; const n = [...scoring.dimensions]; n[idx] = { ...n[idx], ...patch }; setScoring({ dimensions: n }) }

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
    </Stack>
  )
}
