import { DefaultButton, FontWeights, MessageBar, MessageBarType, Panel, PanelType, PrimaryButton, Stack, Text, TextField, Toggle } from '@fluentui/react'
import { useEffect, useState } from 'react'
import {
  createSchedule,
  deleteSchedule,
  fetchScans,
  fetchSchedules,
  fetchSources,
  ScanRun,
  ScanSchedule,
  Source,
  triggerScan,
} from '../services/api'

interface ScheduleForm {
  source: Source
  scheduleId?: string
  cron: string
  timezone: string
  enabled: boolean
}

export function ScansPage() {
  const [scans, setScans] = useState<ScanRun[]>([])
  const [sources, setSources] = useState<Source[]>([])
  const [schedules, setSchedules] = useState<ScanSchedule[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [scheduleForm, setScheduleForm] = useState<ScheduleForm | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [sd, sc, sch] = await Promise.all([fetchScans(), fetchSources(), fetchSchedules()])
      setScans(sd); setSources(sc); setSchedules(sch)
    } catch (e) { setError(String(e)) } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleScan = async (id: string) => { try { await triggerScan(id); load() } catch (e) { setError(String(e)) } }

  const openSchedule = (source: Source) => {
    const existing = schedules.find(s => s.source_id === source.id)
    setScheduleForm({
      source,
      scheduleId: existing?.id,
      cron: existing?.cron_expression ?? '0 9 * * *',
      timezone: existing?.timezone ?? 'UTC',
      enabled: existing?.is_enabled ?? true,
    })
  }

  const saveSchedule = async () => {
    if (!scheduleForm) return
    try {
      await createSchedule({
        source_id: scheduleForm.source.id,
        cron_expression: scheduleForm.cron,
        timezone: scheduleForm.timezone,
        is_enabled: scheduleForm.enabled,
      })
      setSuccess('Schedule saved.')
      setScheduleForm(null)
      load()
    } catch (e) { setError(String(e)) }
  }

  const removeSchedule = async () => {
    if (!scheduleForm?.scheduleId) return
    try {
      await deleteSchedule(scheduleForm.scheduleId)
      setSuccess('Schedule deleted.')
      setScheduleForm(null)
      load()
    } catch (e) { setError(String(e)) }
  }

  const smap = new Map(sources.map(s => [s.id, s]))
  const scheduleBySource = new Map(schedules.map(s => [s.source_id, s]))
  const statusColor = (s: string) => s === 'completed' ? 'green' : s === 'failed' ? 'red' : 'orange'

  return (
    <Stack tokens={{ childrenGap: 16 }}>
      <Text variant="xLarge" styles={{ root: { fontWeight: FontWeights.semibold } }}>Scans</Text>
      {error && <MessageBar messageBarType={MessageBarType.error} onDismiss={() => setError(null)}>{error}</MessageBar>}
      {success && <MessageBar messageBarType={MessageBarType.success} onDismiss={() => setSuccess(null)}>{success}</MessageBar>}
      <Stack tokens={{ childrenGap: 8 }}>
        {sources.map(s => {
          const sch = scheduleBySource.get(s.id)
          return (
            <Stack key={s.id} horizontal horizontalAlign="space-between" verticalAlign="center" styles={{ root: { border: '1px solid #e5e7eb', borderRadius: 8, padding: 12 } }}>
              <Stack tokens={{ childrenGap: 4 }}>
                <Text variant="mediumPlus">{s.name}</Text>
                <Text variant="small" styles={{ root: { color: 'gray' } }}>{s.source_type} | Health: {s.health_status}</Text>
                {sch && (
                  <Text variant="small" styles={{ root: { color: sch.is_enabled ? 'green' : 'gray' } }}>
                    Schedule: {sch.cron_expression} ({sch.timezone}){sch.is_enabled ? '' : ' - disabled'}
                  </Text>
                )}
              </Stack>
              <Stack horizontal tokens={{ childrenGap: 8 }}>
                <DefaultButton text="Schedule" onClick={() => openSchedule(s)} />
                <DefaultButton text="Scan Now" onClick={() => handleScan(s.id)} />
              </Stack>
            </Stack>
          )
        })}
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
      <Panel
        isOpen={scheduleForm !== null}
        onDismiss={() => setScheduleForm(null)}
        type={PanelType.medium}
        headerText={scheduleForm ? `Schedule: ${scheduleForm.source.name}` : 'Schedule'}
      >
        {scheduleForm && (
          <Stack tokens={{ childrenGap: 16 }}>
            <TextField
              label="Cron expression"
              value={scheduleForm.cron}
              onChange={(_, v) => setScheduleForm({ ...scheduleForm, cron: v || '' })}
              placeholder="0 9 * * *"
              description='Standard 5-field cron, e.g. "0 9 * * *" runs daily at 09:00.'
            />
            <TextField
              label="Timezone"
              value={scheduleForm.timezone}
              onChange={(_, v) => setScheduleForm({ ...scheduleForm, timezone: v || 'UTC' })}
              placeholder="UTC"
              description='IANA timezone name, e.g. "UTC" or "Asia/Shanghai".'
            />
            <Toggle
              label="Enabled"
              checked={scheduleForm.enabled}
              onChange={(_, v) => setScheduleForm({ ...scheduleForm, enabled: !!v })}
              onText="On"
              offText="Off"
            />
            <Stack horizontal tokens={{ childrenGap: 8 }}>
              <PrimaryButton text="Save Schedule" onClick={saveSchedule} />
              {scheduleForm.scheduleId && <DefaultButton text="Delete Schedule" onClick={removeSchedule} />}
            </Stack>
          </Stack>
        )}
      </Panel>
    </Stack>
  )
}
