import { DefaultButton, FontWeights, MessageBar, MessageBarType, Stack, Text } from '@fluentui/react'
import { useEffect, useState } from 'react'
import { fetchScans, fetchSources, ScanRun, Source, triggerScan } from '../services/api'

export function ScansPage() {
  const [scans, setScans] = useState<ScanRun[]>([])
  const [sources, setSources] = useState<Source[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [sd, sc] = await Promise.all([fetchScans(), fetchSources()])
      setScans(sd); setSources(sc)
    } catch (e) { setError(String(e)) } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleScan = async (id: string) => { try { await triggerScan(id); load() } catch (e) { setError(String(e)) } }
  const smap = new Map(sources.map(s => [s.id, s]))
  const statusColor = (s: string) => s === 'completed' ? 'green' : s === 'failed' ? 'red' : 'orange'

  return (
    <Stack tokens={{ childrenGap: 16 }}>
      <Text variant="xLarge" styles={{ root: { fontWeight: FontWeights.semibold } }}>Scans</Text>
      {error && <MessageBar messageBarType={MessageBarType.error} onDismiss={() => setError(null)}>{error}</MessageBar>}
      <Stack tokens={{ childrenGap: 8 }}>
        {sources.map(s => (
          <Stack key={s.id} horizontal horizontalAlign="space-between" verticalAlign="center" styles={{ root: { border: '1px solid #e5e7eb', borderRadius: 8, padding: 12 } }}>
            <Stack tokens={{ childrenGap: 4 }}>
              <Text variant="mediumPlus">{s.name}</Text>
              <Text variant="small" styles={{ root: { color: 'gray' } }}>{s.source_type} | Health: {s.health_status}</Text>
            </Stack>
            <DefaultButton text="Scan Now" onClick={() => handleScan(s.id)} />
          </Stack>
        ))}
      </Stack>
      <Text variant="large" styles={{ root: { fontWeight: FontWeights.semibold } }}>Recent Scan Runs</Text>
      {loading ? <Text>Loading...</Text> : (
        <Stack tokens={{ childrenGap: 8 }}>
          {scans.map(scan => (
            <Stack key={scan.id} styles={{ root: { border: '1px solid #e5e7eb', borderRadius: 8, padding: 12 } }}>
              <Stack horizontal horizontalAlign="space-between" verticalAlign="center">
                <Text variant="mediumPlus">{smap.get(scan.source_id)?.name || scan.source_id}</Text>
                <Text variant="small" styles={{ root: { fontWeight: FontWeights.semibold, color: statusColor(scan.status) } }}>{scan.status}</Text>
              </Stack>
              <Text variant="small" styles={{ root: { color: 'gray' } }}>Collected: {scan.items_collected} | New: {scan.items_new} | Analyzed: {scan.items_analyzed} | Failed: {scan.items_failed}</Text>
              {scan.error_log.length > 0 && <Text variant="small" styles={{ root: { color: 'red' } }}>{scan.error_log.join('; ')}</Text>}
              {scan.suggested_fix && <Text variant="small" styles={{ root: { color: 'blue' } }}>Fix: {scan.suggested_fix}</Text>}
            </Stack>
          ))}
          {scans.length === 0 && <Text>No scans yet.</Text>}
        </Stack>
      )}
    </Stack>
  )
}
