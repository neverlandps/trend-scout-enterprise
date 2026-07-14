import { DefaultButton, FontWeights, MessageBar, MessageBarType, PrimaryButton, Stack, Text, TextField } from '@fluentui/react'
import { useEffect, useState } from 'react'
import { createReport, fetchReports, fetchSignals, Report, Signal } from '../services/api'

export function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([])
  const [signals, setSignals] = useState<Signal[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [reportType, setReportType] = useState<'pdf' | 'pptx' | 'card'>('pdf')

  const load = async () => {
    setLoading(true)
    try {
      const [rd, sd] = await Promise.all([fetchReports(), fetchSignals(undefined, 0, 100, 0)])
      setReports(rd); setSignals(sd.signals)
    } catch (e) { setError(String(e)) } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const toggle = (id: string) => {
    const n = new Set(selected)
    if (n.has(id)) n.delete(id); else n.add(id)
    setSelected(n)
  }

  const handleCreate = async () => {
    try { await createReport({ title: title || undefined, item_ids: Array.from(selected), report_type: reportType }); setTitle(''); setSelected(new Set()); load() } catch (e) { setError(String(e)) }
  }

  const typeButton = (type: 'pdf' | 'pptx' | 'card', label: string) => (
    <DefaultButton
      text={label}
      primary={reportType === type}
      onClick={() => setReportType(type)}
    />
  )

  const downloadLabel = (type: string) => {
    if (type === 'pptx') return 'Download PPTX'
    if (type === 'card') return 'Open Card'
    return 'Download PDF'
  }

  return (
    <Stack tokens={{ childrenGap: 16 }}>
      <Text variant="xLarge" styles={{ root: { fontWeight: FontWeights.semibold } }}>Reports</Text>
      {error && <MessageBar messageBarType={MessageBarType.error} onDismiss={() => setError(null)}>{error}</MessageBar>}
      <Text variant="mediumPlus" styles={{ root: { fontWeight: FontWeights.semibold } }}>Select Signals</Text>
      <Stack tokens={{ childrenGap: 8 }}>
        {signals.map(s => (
          <Stack key={s.id} horizontal tokens={{ childrenGap: 8 }} verticalAlign="center" styles={{ root: { padding: 8, border: '1px solid #e5e7eb', borderRadius: 4 } }}>
            <input type="checkbox" checked={selected.has(s.id)} onChange={() => toggle(s.id)} />
            <Stack tokens={{ childrenGap: 2 }}>
              <Text variant="small">{s.title || s.url}</Text>
              <Text variant="small" styles={{ root: { color: 'gray' } }}>Score: {s.overall_score?.toFixed(2) ?? 'n/a'}</Text>
            </Stack>
          </Stack>
        ))}
        {signals.length === 0 && <Text>No signals to report on.</Text>}
      </Stack>
      <Stack horizontal tokens={{ childrenGap: 8 }} verticalAlign="end">
        <TextField label="Report Title" value={title} onChange={(_, v) => setTitle(v || '')} />
        <Stack horizontal tokens={{ childrenGap: 8 }} verticalAlign="end">
          {typeButton('pdf', 'PDF')}
          {typeButton('pptx', 'PPTX')}
          {typeButton('card', 'Card')}
        </Stack>
        <PrimaryButton text={`Generate ${reportType.toUpperCase()} Report`} onClick={handleCreate} disabled={selected.size === 0} />
      </Stack>
      <Text variant="large" styles={{ root: { fontWeight: FontWeights.semibold } }}>Generated Reports</Text>
      {loading ? <Text>Loading...</Text> : (
        <Stack tokens={{ childrenGap: 8 }}>
          {reports.map(r => (
            <Stack key={r.id} horizontal horizontalAlign="space-between" verticalAlign="center" styles={{ root: { border: '1px solid #e5e7eb', borderRadius: 8, padding: 12 } }}>
              <Stack tokens={{ childrenGap: 4 }}>
                <Text variant="mediumPlus">{r.title || 'Untitled Report'} ({r.report_type})</Text>
                <Text variant="small" styles={{ root: { color: 'gray' } }}>Status: {r.status} | Created: {new Date(r.created_at).toLocaleString()}</Text>
              </Stack>
              {r.status === 'completed' && <DefaultButton text={downloadLabel(r.report_type)} href={`/api/v1/reports/${r.id}/download`} target="_blank" />}
            </Stack>
          ))}
          {reports.length === 0 && <Text>No reports yet.</Text>}
        </Stack>
      )}
    </Stack>
  )
}
