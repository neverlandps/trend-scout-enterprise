import { PrimaryButton, Stack, Text, DetailsList, IColumn, TextField, Dropdown, IDropdownOption } from '@fluentui/react'
import { useEffect, useState } from 'react'
import api from '../services/api'

interface TeamMember {
  id: string
  name: string
  role: string
  key_prefix: string
  is_active: boolean
  created_at: string
}

export function TeamPage() {
  const [members, setMembers] = useState<TeamMember[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [role, setRole] = useState('analyst')
  const [invitedKey, setInvitedKey] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get('/team/members')
      setMembers(res.data)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleInvite = async () => {
    try {
      const res = await api.post('/team/members', { name, role })
      setInvitedKey(res.data.api_key)
      setName('')
      load()
    } catch (e) {
      setError(String(e))
    }
  }

  const columns: IColumn[] = [
    { key: 'name', name: 'Name', fieldName: 'name', minWidth: 120, maxWidth: 200 },
    { key: 'role', name: 'Role', fieldName: 'role', minWidth: 80, maxWidth: 100 },
    { key: 'keyPrefix', name: 'Key Prefix', fieldName: 'key_prefix', minWidth: 100, maxWidth: 150 },
    { key: 'created', name: 'Created', fieldName: 'created_at', minWidth: 150, maxWidth: 200 },
  ]

  const roleOptions: IDropdownOption[] = [
    { key: 'admin', text: 'Admin' },
    { key: 'analyst', text: 'Analyst' },
    { key: 'viewer', text: 'Viewer' },
  ]

  return (
    <Stack tokens={{ childrenGap: 16 }}>
      <Text variant="xLarge">Team Members</Text>
      {error && <Text styles={{ root: { color: 'red' } }}>{error}</Text>}
      {invitedKey && (
        <Stack styles={{ root: { background: '#e6f4ea', padding: 12, borderRadius: 8 } }}>
          <Text variant="small">New API key created. Copy it now — it won’t be shown again.</Text>
          <Text styles={{ root: { fontFamily: 'monospace', wordBreak: 'break-all' } }}>{invitedKey}</Text>
        </Stack>
      )}
      <Stack horizontal tokens={{ childrenGap: 8 }} verticalAlign="end">
        <TextField label="Name" value={name} onChange={(_, v) => setName(v || '')} />
        <Dropdown label="Role" selectedKey={role} options={roleOptions} onChange={(_, o) => o && setRole(String(o.key))} styles={{ dropdown: { width: 140 } }} />
        <PrimaryButton text="Invite Member" onClick={handleInvite} disabled={!name} />
      </Stack>
      {loading ? <Text>Loading...</Text> : <DetailsList items={members} columns={columns} />}
    </Stack>
  )
}
