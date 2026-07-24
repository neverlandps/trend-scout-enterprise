import { useEffect, useMemo, useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import {
  PrimaryButton,
  DefaultButton,
  Dropdown,
  IDropdownOption,
  Text,
  Stack,
  Spinner,
  SpinnerSize,
  Panel,
  PanelType,
  DetailsList,
  IColumn,
  DatePicker,
  MessageBar,
  MessageBarType,
  Toggle,
  mergeStyleSets,
} from '@fluentui/react'
import {
  TrendComparison,
  TrendPoint,
  TrendEvidence,
  aggregateTrends,
  fetchTrendCategories,
  fetchTrendTopics,
  fetchTrendSeries,
  fetchTrendEvidence,
} from '../services/api'

const chartColors = ['#0078d4', '#107c10', '#d83b01', '#5c2d91', '#038387', '#ffc107']

const styles = mergeStyleSets({
  container: { padding: '1rem' },
  controls: { display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem' },
  chartContainer: { width: '100%', height: 400, marginTop: '1rem' },
})

export function TrendsPage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [categories, setCategories] = useState<string[]>([])
  const [topics, setTopics] = useState<string[]>([])
  const [category, setCategory] = useState<string>('')
  const [topic, setTopic] = useState<string>('')
  const [granularity, setGranularity] = useState<'day' | 'week' | 'month'>('week')
  const [startDate, setStartDate] = useState<Date | null | undefined>(undefined)
  const [endDate, setEndDate] = useState<Date | null | undefined>(undefined)
  const [comparison, setComparison] = useState<TrendComparison | null>(null)
  const [selectedPoint, setSelectedPoint] = useState<TrendPoint | null>(null)
  const [evidence, setEvidence] = useState<TrendEvidence[]>([])
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [onlyApproved, setOnlyApproved] = useState(false)

  const granularityOptions: IDropdownOption[] = [
    { key: 'day', text: 'Day' },
    { key: 'week', text: 'Week' },
    { key: 'month', text: 'Month' },
  ]

  const categoryOptions: IDropdownOption[] = useMemo(
    () => [{ key: '', text: 'All categories' }, ...categories.map((c) => ({ key: c, text: c }))],
    [categories]
  )

  const topicOptions: IDropdownOption[] = useMemo(
    () => [{ key: '', text: 'All topics' }, ...topics.map((t) => ({ key: t, text: t }))],
    [topics]
  )

  useEffect(() => {
    fetchTrendCategories().then(setCategories).catch((err) => setError(err.message))
  }, [])

  useEffect(() => {
    fetchTrendTopics(category || undefined).then(setTopics).catch((err) => setError(err.message))
  }, [category])

  const loadSeries = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchTrendSeries(
        category || undefined,
        topic || undefined,
        startDate?.toISOString().split('T')[0],
        endDate?.toISOString().split('T')[0],
        granularity
      )
      setComparison(data)
    } catch (err: any) {
      setError(err.message || 'Failed to load trend series')
    } finally {
      setLoading(false)
    }
  }

  const runAggregation = async () => {
    setLoading(true)
    setError(null)
    try {
      await aggregateTrends({
        category: category || undefined,
        topic_key: topic || undefined,
        start_date: startDate?.toISOString().split('T')[0],
        end_date: endDate?.toISOString().split('T')[0],
        granularity,
        only_approved: onlyApproved,
      })
      await loadSeries()
    } catch (err: any) {
      setError(err.message || 'Failed to aggregate trends')
    } finally {
      setLoading(false)
    }
  }

  const chartData = useMemo(() => {
    if (!comparison) return []
    const dates = new Set<string>()
    comparison.series.forEach((s) => s.points.forEach((p) => dates.add(p.date_bucket)))
    const sortedDates = Array.from(dates).sort()
    return sortedDates.map((date) => {
      const row: Record<string, any> = { date }
      comparison.series.forEach((s) => {
        const point = s.points.find((p) => p.date_bucket === date)
        const key = s.topic_key || s.category || 'overall'
        row[key] = point ? point.avg_overall_score : null
      })
      return row
    })
  }, [comparison])

  const seriesKeys = useMemo(() => {
    if (!comparison) return []
    return comparison.series.map((s) => s.topic_key || s.category || 'overall')
  }, [comparison])

  const handleChartClick = async (state: any) => {
    if (!state || !state.activeLabel || !comparison) return
    const date = state.activeLabel as string
    // Pick the first series with a point at this date
    for (const s of comparison.series) {
      const point = s.points.find((p) => p.date_bucket === date)
      if (point) {
        setSelectedPoint(point)
        setEvidenceOpen(true)
        try {
          const ev = await fetchTrendEvidence(point.id)
          setEvidence(ev)
        } catch (err: any) {
          setError(err.message)
        }
        break
      }
    }
  }

  const evidenceColumns: IColumn[] = [
    {
      key: 'rank',
      name: 'Rank',
      fieldName: 'rank',
      minWidth: 40,
      maxWidth: 60,
    },
    {
      key: 'title',
      name: 'Evidence',
      fieldName: 'raw_item_title',
      minWidth: 150,
      maxWidth: 250,
      isResizable: true,
      onRender: (item: TrendEvidence) => (
        <a href={item.raw_item_url || '#'} target="_blank" rel="noreferrer">
          {item.raw_item_title || 'Untitled'}
        </a>
      ),
    },
    {
      key: 'source',
      name: 'Source',
      fieldName: 'source_name',
      minWidth: 100,
      maxWidth: 150,
    },
    {
      key: 'score',
      name: 'Score',
      fieldName: 'overall_score',
      minWidth: 60,
      maxWidth: 80,
      onRender: (item: TrendEvidence) => (
        <Text>{item.overall_score ? item.overall_score.toFixed(2) : '-'}</Text>
      ),
    },
    {
      key: 'rationale',
      name: 'Rationale',
      fieldName: 'rationale',
      minWidth: 200,
      maxWidth: 400,
      isResizable: true,
    },
  ]

  return (
    <div className={styles.container}>
      <Text variant="xxLarge">Trends</Text>
      <Text variant="small">
        Overlay historical trend scores for categories or topics. Click any point to trace evidence.
      </Text>

      <Stack horizontal className={styles.controls} verticalAlign="end" tokens={{ childrenGap: 12 }}>
        <Dropdown
          label="Category"
          selectedKey={category}
          options={categoryOptions}
          onChange={(_, option) => setCategory(option?.key as string)}
          styles={{ dropdown: { width: 180 } }}
        />
        <Dropdown
          label="Topic"
          selectedKey={topic}
          options={topicOptions}
          onChange={(_, option) => setTopic(option?.key as string)}
          styles={{ dropdown: { width: 180 } }}
        />
        <Dropdown
          label="Granularity"
          selectedKey={granularity}
          options={granularityOptions}
          onChange={(_, option) => setGranularity(option?.key as 'day' | 'week' | 'month')}
          styles={{ dropdown: { width: 120 } }}
        />
        <DatePicker
          label="Start"
          value={startDate || undefined}
          onSelectDate={setStartDate}
          placeholder="Select start date"
        />
        <DatePicker
          label="End"
          value={endDate || undefined}
          onSelectDate={setEndDate}
          placeholder="Select end date"
        />
        <Toggle
          label="Only approved signals"
          checked={onlyApproved}
          onChange={(_, v) => setOnlyApproved(!!v)}
          styles={{ root: { marginBottom: 4 } }}
        />
        <PrimaryButton text="Aggregate" onClick={runAggregation} disabled={loading} />
        <DefaultButton text="Load Series" onClick={loadSeries} disabled={loading} />
      </Stack>

      {error && (
        <MessageBar messageBarType={MessageBarType.error} isMultiline={true}>
          {error}
        </MessageBar>
      )}

      {loading && <Spinner size={SpinnerSize.medium} label="Loading trends..." />}

      {!loading && comparison && comparison.series.length > 0 && (
        <div className={styles.chartContainer}>
          <ResponsiveContainer>
            <LineChart data={chartData} onClick={handleChartClick}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis domain={[0, 1]} />
              <Tooltip />
              <Legend />
              {seriesKeys.map((key, idx) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={chartColors[idx % chartColors.length]}
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {!loading && comparison && comparison.series.length === 0 && (
        <Text variant="medium">No trend data found. Click Aggregate to generate trend points.</Text>
      )}

      <Panel
        isOpen={evidenceOpen}
        onDismiss={() => setEvidenceOpen(false)}
        type={PanelType.medium}
        headerText={
          selectedPoint
            ? `Evidence: ${selectedPoint.topic_key} on ${selectedPoint.date_bucket}`
            : 'Evidence'
        }
      >
        <Text variant="small">
          Category: {selectedPoint?.category} | Items: {selectedPoint?.item_count} | Avg score:{' '}
          {selectedPoint?.avg_overall_score?.toFixed(2)}
        </Text>
        <DetailsList items={evidence} columns={evidenceColumns} selectionMode={0} compact />
      </Panel>
    </div>
  )
}
