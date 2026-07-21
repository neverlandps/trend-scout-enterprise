import { useEffect, useMemo, useState } from 'react'
import {
  DefaultButton,
  DetailsList,
  Dropdown,
  FontWeights,
  IColumn,
  IDropdownOption,
  IObjectWithKey,
  Link,
  MessageBar,
  MessageBarType,
  Panel,
  PanelType,
  Pivot,
  PivotItem,
  PrimaryButton,
  Selection,
  SelectionMode,
  Spinner,
  SpinnerSize,
  Stack,
  Text,
  TextField,
} from '@fluentui/react'
import {
  bulkReviewSignals,
  BulkReviewResult,
  FeedbackType,
  fetchReviewQueue,
  fetchSignals,
  fetchSources,
  reviewSignal,
  Source,
  Signal,
  submitSignalFeedback,
} from '../services/api'

type StatusFilter = 'all' | 'pending_review' | 'approved' | 'rejected' | 'flagged'

const STATUS_COLORS: Record<string, string> = {
  pending_review: '#ca5010',
  approved: '#107c10',
  rejected: '#a80000',
  flagged: '#5c2d91',
  auto: '#605e5c',
}

const feedbackTypeOptions: IDropdownOption[] = [
  { key: 'score_too_low', text: 'Score too low' },
  { key: 'score_too_high', text: 'Score too high' },
  { key: 'irrelevant', text: 'Irrelevant' },
]

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] ?? STATUS_COLORS.auto
  return (
    <span
      style={{
        backgroundColor: color,
        color: '#ffffff',
        borderRadius: 10,
        padding: '2px 10px',
        fontSize: 12,
      }}
    >
      {status}
    </span>
  )
}

export function SignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [sources, setSources] = useState<Source[]>([])
  const [filter, setFilter] = useState<StatusFilter>('pending_review')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [detailSignal, setDetailSignal] = useState<Signal | null>(null)
  const [overrideScore, setOverrideScore] = useState('')
  const [overrideNotes, setOverrideNotes] = useState('')
  const [feedbackScore, setFeedbackScore] = useState('')
  const [feedbackType, setFeedbackType] = useState<FeedbackType>('score_too_low')
  const [feedbackNotes, setFeedbackNotes] = useState('')
  const [actionLoading, setActionLoading] = useState(false)

  const sourceNameById = useMemo(() => {
    const map: Record<string, string> = {}
    sources.forEach((s) => {
      map[s.id] = s.name
    })
    return map
  }, [sources])

  const selection = useMemo(
    () =>
      new Selection({
        onSelectionChanged: () => {
          setSelectedIds(selection.getSelection().map((item) => (item as Signal).id))
        },
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  )

  const load = async (status: StatusFilter = filter) => {
    setLoading(true)
    setError(null)
    try {
      let items: Signal[]
      if (status === 'pending_review') {
        items = (await fetchReviewQueue({ limit: 100 })).signals
      } else if (status === 'all') {
        items = (await fetchSignals(undefined, undefined, 100, 0)).signals
      } else {
        items = (await fetchSignals(undefined, undefined, 100, 0, status)).signals
      }
      setSignals(items)
      selection.setAllSelected(false)
      setSelectedIds([])
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter])

  useEffect(() => {
    fetchSources().then(setSources).catch(() => undefined)
  }, [])

  const handleRowAction = async (signal: Signal, action: 'approve' | 'reject' | 'flag') => {
    setActionLoading(true)
    setError(null)
    try {
      await reviewSignal(signal.id, { action })
      await load()
    } catch (e) {
      setError(String(e))
    } finally {
      setActionLoading(false)
    }
  }

  const handleBulk = async (action: 'approve' | 'reject') => {
    setActionLoading(true)
    setError(null)
    setInfo(null)
    try {
      const result: BulkReviewResult = await bulkReviewSignals({ item_ids: selectedIds, action })
      const failedText =
        result.failed.length > 0
          ? ` Failed: ${result.failed.map((f) => `${f.id} (${f.error})`).join(', ')}`
          : ''
      setInfo(`Bulk ${action}: ${result.succeeded.length} succeeded, ${result.failed.length} failed.${failedText}`)
      await load()
    } catch (e) {
      setError(String(e))
    } finally {
      setActionLoading(false)
    }
  }

  const openDetail = (signal: Signal) => {
    setDetailSignal(signal)
    setOverrideScore(signal.human_score != null ? String(signal.human_score) : '')
    setOverrideNotes('')
    setFeedbackScore('')
    setFeedbackType('score_too_low')
    setFeedbackNotes('')
  }

  const handleOverride = async () => {
    if (!detailSignal) return
    const score = Number(overrideScore)
    if (overrideScore === '' || Number.isNaN(score) || score < 0 || score > 1) {
      setError('Override score must be a number between 0 and 1')
      return
    }
    setActionLoading(true)
    setError(null)
    try {
      await reviewSignal(detailSignal.id, {
        action: 'override',
        human_score: score,
        notes: overrideNotes || undefined,
      })
      setInfo('Override submitted.')
      setDetailSignal(null)
      await load()
    } catch (e) {
      setError(String(e))
    } finally {
      setActionLoading(false)
    }
  }

  const handleFeedback = async () => {
    if (!detailSignal) return
    const score = Number(feedbackScore)
    if (feedbackScore === '' || Number.isNaN(score) || score < 0 || score > 1) {
      setError('Feedback score must be a number between 0 and 1')
      return
    }
    setActionLoading(true)
    setError(null)
    try {
      await submitSignalFeedback(detailSignal.id, {
        human_score: score,
        feedback_type: feedbackType,
        notes: feedbackNotes || undefined,
      })
      setInfo('Feedback submitted.')
      await load()
    } catch (e) {
      setError(String(e))
    } finally {
      setActionLoading(false)
    }
  }

  const columns: IColumn[] = [
    {
      key: 'title',
      name: 'Title',
      fieldName: 'title',
      minWidth: 180,
      maxWidth: 320,
      isResizable: true,
      onRender: (item: Signal) => (
        <span title={item.title ?? item.url} style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {item.title ?? item.url}
        </span>
      ),
    },
    {
      key: 'source',
      name: 'Source',
      minWidth: 100,
      maxWidth: 160,
      isResizable: true,
      onRender: (item: Signal) => <Text variant="small">{sourceNameById[item.source_id] ?? item.source_id}</Text>,
    },
    {
      key: 'score',
      name: 'Score',
      fieldName: 'overall_score',
      minWidth: 60,
      maxWidth: 80,
      onRender: (item: Signal) => <Text>{item.overall_score != null ? item.overall_score.toFixed(2) : '-'}</Text>,
    },
    {
      key: 'status',
      name: 'Status',
      minWidth: 110,
      maxWidth: 140,
      onRender: (item: Signal) => <StatusBadge status={item.review_status ?? 'auto'} />,
    },
    {
      key: 'actions',
      name: 'Actions',
      minWidth: 220,
      onRender: (item: Signal) =>
        (item.review_status ?? 'auto') === 'pending_review' ? (
          <Stack horizontal tokens={{ childrenGap: 4 }}>
            <DefaultButton text="Approve" onClick={(e) => { e.stopPropagation(); handleRowAction(item, 'approve') }} disabled={actionLoading} />
            <DefaultButton text="Reject" onClick={(e) => { e.stopPropagation(); handleRowAction(item, 'reject') }} disabled={actionLoading} />
            <DefaultButton text="Flag" onClick={(e) => { e.stopPropagation(); handleRowAction(item, 'flag') }} disabled={actionLoading} />
          </Stack>
        ) : null,
    },
  ]

  const scoreRow = (label: string, value: number | null | undefined) => (
    <Stack horizontal horizontalAlign="space-between" styles={{ root: { padding: '2px 0' } }}>
      <Text variant="small">{label}</Text>
      <Text variant="small" styles={{ root: { fontWeight: FontWeights.semibold } }}>
        {value != null ? value.toFixed(2) : 'n/a'}
      </Text>
    </Stack>
  )

  return (
    <Stack tokens={{ childrenGap: 16 }}>
      <Text variant="xLarge" styles={{ root: { fontWeight: FontWeights.semibold } }}>Signals</Text>
      {error && (
        <MessageBar messageBarType={MessageBarType.error} onDismiss={() => setError(null)}>
          {error}
        </MessageBar>
      )}
      {info && (
        <MessageBar messageBarType={MessageBarType.success} onDismiss={() => setInfo(null)}>
          {info}
        </MessageBar>
      )}
      <Pivot
        selectedKey={filter}
        onLinkClick={(item) => setFilter((item?.props.itemKey as StatusFilter) ?? 'pending_review')}
      >
        <PivotItem itemKey="all" headerText="All" />
        <PivotItem itemKey="pending_review" headerText="Pending Review" />
        <PivotItem itemKey="approved" headerText="Approved" />
        <PivotItem itemKey="rejected" headerText="Rejected" />
        <PivotItem itemKey="flagged" headerText="Flagged" />
      </Pivot>
      <Stack horizontal tokens={{ childrenGap: 8 }} verticalAlign="center">
        <PrimaryButton text={`Bulk Approve (${selectedIds.length})`} onClick={() => handleBulk('approve')} disabled={selectedIds.length === 0 || actionLoading} />
        <DefaultButton text={`Bulk Reject (${selectedIds.length})`} onClick={() => handleBulk('reject')} disabled={selectedIds.length === 0 || actionLoading} />
      </Stack>
      {loading ? (
        <Spinner size={SpinnerSize.medium} label="Loading signals..." />
      ) : signals.length === 0 ? (
        <Text>No signals found for this filter.</Text>
      ) : (
        <DetailsList
          items={signals as IObjectWithKey[]}
          columns={columns}
          selection={selection}
          selectionMode={SelectionMode.multiple}
          setKey="id"
          onItemInvoked={openDetail}
          compact
        />
      )}
      <Panel
        isOpen={detailSignal !== null}
        onDismiss={() => setDetailSignal(null)}
        type={PanelType.medium}
        headerText={detailSignal?.title ?? 'Signal Detail'}
      >
        {detailSignal && (
          <Stack tokens={{ childrenGap: 16 }}>
            <Stack tokens={{ childrenGap: 4 }}>
              <Text variant="small">
                URL:{' '}
                <Link href={detailSignal.url} target="_blank" rel="noreferrer">
                  {detailSignal.url}
                </Link>
              </Text>
              <Text variant="small">Source: {sourceNameById[detailSignal.source_id] ?? detailSignal.source_id}</Text>
              <Text variant="small">Collected: {new Date(detailSignal.collected_at).toLocaleString()}</Text>
              {detailSignal.assigned_reviewer_id && (
                <Text variant="small">Assigned reviewer: {detailSignal.assigned_reviewer_id}</Text>
              )}
              <Text variant="medium">{detailSignal.summary ?? 'No summary available.'}</Text>
            </Stack>
            <Stack tokens={{ childrenGap: 4 }}>
              <Text variant="mediumPlus" styles={{ root: { fontWeight: FontWeights.semibold } }}>Scores</Text>
              {scoreRow('Overall', detailSignal.overall_score)}
              {scoreRow('Signal strength', detailSignal.signal_strength)}
              {scoreRow('Cross-domain impact', detailSignal.cross_domain_impact)}
              {scoreRow('Investment velocity', detailSignal.investment_velocity)}
              {scoreRow('Technical feasibility', detailSignal.technical_feasibility)}
              {scoreRow('Strategic fit', detailSignal.strategic_fit)}
              {scoreRow('Human score', detailSignal.human_score)}
            </Stack>
            {detailSignal.metadata_json && Object.keys(detailSignal.metadata_json).length > 0 && (
              <Stack tokens={{ childrenGap: 4 }}>
                <Text variant="mediumPlus" styles={{ root: { fontWeight: FontWeights.semibold } }}>Metadata</Text>
                <pre style={{ background: '#f3f2f1', padding: 8, fontSize: 12, overflow: 'auto' }}>
                  {JSON.stringify(detailSignal.metadata_json, null, 2)}
                </pre>
              </Stack>
            )}
            <Stack tokens={{ childrenGap: 8 }}>
              <Text variant="mediumPlus" styles={{ root: { fontWeight: FontWeights.semibold } }}>Override Score</Text>
              <TextField
                label="Human score (0-1)"
                type="number"
                min={0}
                max={1}
                step={0.01}
                value={overrideScore}
                onChange={(_, v) => setOverrideScore(v ?? '')}
              />
              <TextField
                label="Notes"
                multiline
                rows={2}
                value={overrideNotes}
                onChange={(_, v) => setOverrideNotes(v ?? '')}
              />
              <PrimaryButton text="Submit Override" onClick={handleOverride} disabled={actionLoading} styles={{ root: { alignSelf: 'flex-start' } }} />
            </Stack>
            <Stack tokens={{ childrenGap: 8 }}>
              <Text variant="mediumPlus" styles={{ root: { fontWeight: FontWeights.semibold } }}>Feedback</Text>
              <TextField
                label="Human score (0-1)"
                type="number"
                min={0}
                max={1}
                step={0.01}
                value={feedbackScore}
                onChange={(_, v) => setFeedbackScore(v ?? '')}
              />
              <Dropdown
                label="Feedback type"
                selectedKey={feedbackType}
                options={feedbackTypeOptions}
                onChange={(_, option) => setFeedbackType(option?.key as FeedbackType)}
                styles={{ dropdown: { width: 220 } }}
              />
              <TextField
                label="Notes"
                multiline
                rows={2}
                value={feedbackNotes}
                onChange={(_, v) => setFeedbackNotes(v ?? '')}
              />
              <PrimaryButton text="Submit Feedback" onClick={handleFeedback} disabled={actionLoading} styles={{ root: { alignSelf: 'flex-start' } }} />
            </Stack>
          </Stack>
        )}
      </Panel>
    </Stack>
  )
}
