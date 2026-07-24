import { PrimaryButton, DefaultButton, Stack, Text, DetailsList, IColumn, TextField, Dropdown, IDropdownOption, MessageBar, MessageBarType, FontWeights } from '@fluentui/react'
import { useEffect, useState } from 'react'
import axios from 'axios'
import api, {
  createReviewAssignment,
  deleteReviewAssignment,
  fetchReviewAssignments,
  ReviewAssignment,
} from '../services/api'

interface TeamMember {
  id: string
  name: string
  role: string
  key_prefix: string
  is_active: boolean
  created_at: string
}

function errorMessage(e: unknown, fallback: string): string {
  if (axios.isAxiosError(e)) {
    const detail = e.response?.data?.detail
    const status = e.response?.status
    if (typeof detail === 'string') return status ? `${status}: ${detail}` : detail
  }
  return e instanceof Error ? `${fallback} (${e.message})` : fallback
}

export function TeamPage() {
  const [members, setMembers] = useState<TeamMember[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [role, setRole] = useState('analyst')
  const [invitedKey, setInvitedKey] = useState<string | null>(null)

  const [assignments, setAssignments] = useState<ReviewAssignment[]>([])
  const [assignmentCategory, setAssignmentCategory] = useState('')
  const [assignmentReviewer, setAssignmentReviewer] = useState<string | undefined>(undefined)
  const [assignmentError, setAssignmentError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const [res, ra] = await Promise.all([api.get('/team/members'), fetchReviewAssignments()])
      setMembers(res.data)
      setAssignments(ra)
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

  const memberNameById = new Map(members.map(m => [m.id, m.name]))

  const reviewerOptions: IDropdownOption[] = members.map(m => ({ key: m.id, text: m.name }))

  const handleAddAssignment = async () => {
    if (!assignmentCategory || !assignmentReviewer) return
    setAssignmentError(null)
    try {
      await createReviewAssignment({ category: assignmentCategory, reviewer_id: assignmentReviewer })
      setAssignmentCategory('')
      setAssignmentReviewer(undefined)
      load()
    } catch (e) {
      setAssignmentError(errorMessage(e, 'Failed to save review assignment'))
    }
  }

  const handleDeleteAssignment = async (id: string) => {
    setAssignmentError(null)
    try {
      await deleteReviewAssignment(id)
      load()
    } catch (e) {
      setAssignmentError(errorMessage(e, 'Failed to delete review assignment'))
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

      <Stack tokens={{ childrenGap: 8 }} styles={{ root: { border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 } }}>
        <Text variant="large" styles={{ root: { fontWeight: FontWeights.semibold } }}>Review Assignments</Text>
        {assignmentError && (
          <MessageBar messageBarType={MessageBarType.error} onDismiss={() => setAssignmentError(null)}>
            {assignmentError}
          </MessageBar>
        )}
        {assignments.map(a => (
          <Stack key={a.id} horizontal tokens={{ childrenGap: 8 }} verticalAlign="center">
            <Text styles={{ root: { width: 160 } }}>{a.category}</Text>
            <Text variant="small" styles={{ root: { width: 160, color: 'gray' } }}>
              {memberNameById.get(a.reviewer_id) ?? a.reviewer_id}
            </Text>
            <Text variant="small" styles={{ root: { width: 170, color: 'gray' } }}>
              {new Date(a.created_at).toLocaleDateString()}
            </Text>
            <DefaultButton text="Delete" onClick={() => handleDeleteAssignment(a.id)} />
          </Stack>
        ))}
        {assignments.length === 0 && <Text variant="small" styles={{ root: { color: 'gray' } }}>No review assignments yet.</Text>}
        <Stack horizontal tokens={{ childrenGap: 8 }} verticalAlign="end">
          <TextField
            label="Category"
            value={assignmentCategory}
            onChange={(_, v) => setAssignmentCategory(v || '')}
            placeholder="e.g. energy"
          />
          <Dropdown
            label="Reviewer"
            selectedKey={assignmentReviewer}
            options={reviewerOptions}
            onChange={(_, o) => setAssignmentReviewer(o ? String(o.key) : undefined)}
            placeholder="Select reviewer"
            styles={{ dropdown: { width: 200 } }}
          />
          <PrimaryButton text="Add Assignment" onClick={handleAddAssignment} disabled={!assignmentCategory || !assignmentReviewer} />
        </Stack>
      </Stack>
    </Stack>
  )
}
