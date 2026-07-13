import {
  FontWeights,
  IconButton,
  MessageBar,
  MessageBarType,
  Panel,
  PanelType,
  PrimaryButton,
  Stack,
  Text,
  TextField,
} from '@fluentui/react'
import { useEffect, useState } from 'react'
import {
  createSource,
  deleteSource,
  fetchSources,
  Source,
  SourceCreate,
  updateSource,
} from '../services/api'

export function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const [editing, setEditing] = useState<Source | null>(null)
  const [name, setName] = useState('')
  const [sourceType, setSourceType] = useState('rss')
  const [configJson, setConfigJson] = useState('')
  const [category, setCategory] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      setSources(await fetchSources())
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    if (editing) {
      setName(editing.name)
      setSourceType(editing.source_type)
      setConfigJson(JSON.stringify(editing.config, null, 2))
      setCategory(editing.category || '')
    } else {
      setName('')
      setSourceType('rss')
      setConfigJson(JSON.stringify({ url: '' }, null, 2))
      setCategory('')
    }
  }, [editing, panelOpen])

  const handleSubmit = async () => {
    try {
      const payload: SourceCreate = {
        name,
        source_type: sourceType,
        config: JSON.parse(configJson),
        category,
      }
      if (editing) await updateSource(editing.id, payload)
      else await createSource(payload)
      setPanelOpen(false)
      load()
    } catch (e) {
      setError(String(e))
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this source?')) return
    try { await deleteSource(id); load() } catch (e) { setError(String(e)) }
  }

  const statusColor = (h: string) => h === 'healthy' ? 'green' : h === 'unhealthy' ? 'red' : 'gray'

  return (
    <Stack tokens={{ childrenGap: 16 }}>
      <Stack horizontal horizontalAlign="space-between" verticalAlign="center">
        <Text variant="xLarge" styles={{ root: { fontWeight: FontWeights.semibold } }}>Sources</Text>
        <PrimaryButton text="Add Source" onClick={() => { setEditing(null); setPanelOpen(true) }} />
      </Stack>
      {error && <MessageBar messageBarType={MessageBarType.error} onDismiss={() => setError(null)}>{error}</MessageBar>}
      {loading ? <Text>Loading...</Text> : (
        <Stack tokens={{ childrenGap: 8 }}>
          {sources.map(s => (
            <Stack key={s.id} styles={{ root: { border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 } }}>
              <Stack horizontal horizontalAlign="space-between" verticalAlign="center">
                <Stack tokens={{ childrenGap: 4 }}>
                  <Text variant="large" styles={{ root: { fontWeight: FontWeights.semibold } }}>{s.name}</Text>
                  <Text variant="small" styles={{ root: { color: 'gray' } }}>{s.source_type} | {s.category || 'no category'}</Text>
                  <Text variant="small" styles={{ root: { color: statusColor(s.health_status), fontWeight: FontWeights.semibold } }}>Health: {s.health_status}</Text>
                  {s.last_failure_reason && <Text variant="small" styles={{ root: { color: 'red' } }}>{s.last_failure_reason}</Text>}
                  {s.suggested_fix && <Text variant="small" styles={{ root: { color: 'blue' } }}>Fix: {s.suggested_fix}</Text>}
                </Stack>
                <Stack horizontal tokens={{ childrenGap: 8 }}>
                  <IconButton iconProps={{ iconName: 'Edit' }} onClick={() => { setEditing(s); setPanelOpen(true) }} />
                  <IconButton iconProps={{ iconName: 'Delete' }} onClick={() => handleDelete(s.id)} />
                </Stack>
              </Stack>
            </Stack>
          ))}
          {sources.length === 0 && <Text>No sources yet.</Text>}
        </Stack>
      )}
      <Panel isOpen={panelOpen} onDismiss={() => setPanelOpen(false)} type={PanelType.smallFixedNear} headerText={editing ? 'Edit Source' : 'New Source'}>
        <Stack tokens={{ childrenGap: 8 }}>
          <TextField label="Name" value={name} onChange={(_, v) => setName(v || '')} />
          <TextField label="Type" value={sourceType} onChange={(_, v) => setSourceType(v || 'rss')} />
          <TextField label="Config (JSON)" multiline rows={8} value={configJson} onChange={(_, v) => setConfigJson(v || '')} />
          <TextField label="Category" value={category} onChange={(_, v) => setCategory(v || '')} />
          <PrimaryButton text="Save" onClick={handleSubmit} />
        </Stack>
      </Panel>
    </Stack>
  )
}
