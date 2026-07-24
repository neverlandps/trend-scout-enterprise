import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ScansPage } from '../pages/ScansPage'
import type { Source } from '../services/api'

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>()
  return {
    ...actual,
    fetchScans: vi.fn(),
    fetchSources: vi.fn(),
    fetchSchedules: vi.fn(),
    createSchedule: vi.fn(),
    deleteSchedule: vi.fn(),
    triggerScan: vi.fn(),
  }
})

import * as api from '../services/api'

const source: Source = {
  id: 'src-1',
  name: 'Example Source',
  source_type: 'rss',
  config: {},
  category: null,
  tags: [],
  enabled: true,
  refresh_interval_minutes: 60,
  owner_id: 'owner-1',
  health_status: 'ok',
  last_scan_at: null,
  last_failure_reason: null,
  suggested_fix: null,
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
}

describe('ScansPage schedules', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.fetchScans).mockResolvedValue([])
    vi.mocked(api.fetchSources).mockResolvedValue([source])
    vi.mocked(api.fetchSchedules).mockResolvedValue([])
  })

  it('renders a Schedule button for each source', async () => {
    render(<ScansPage />)
    await waitFor(() => {
      expect(screen.getByText('Example Source')).toBeInTheDocument()
    })
    expect(screen.getByText('Schedule')).toBeInTheDocument()
  })

  it('opens the schedule panel and saves a cron schedule', async () => {
    render(<ScansPage />)
    await waitFor(() => {
      expect(screen.getByText('Schedule')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Schedule'))
    await waitFor(() => {
      expect(screen.getByText('Cron expression')).toBeInTheDocument()
      expect(screen.getByText('Timezone')).toBeInTheDocument()
    })
    const cronInput = screen.getByPlaceholderText('0 9 * * *')
    fireEvent.change(cronInput, { target: { value: '*/30 * * * *' } })
    fireEvent.click(screen.getByText('Save Schedule'))
    await waitFor(() => {
      expect(api.createSchedule).toHaveBeenCalledWith({
        source_id: 'src-1',
        cron_expression: '*/30 * * * *',
        timezone: 'UTC',
        is_enabled: true,
      })
    })
  })

  it('shows existing schedule and deletes it', async () => {
    vi.mocked(api.fetchSchedules).mockResolvedValue([
      {
        id: 'sch-1',
        source_id: 'src-1',
        cron_expression: '0 9 * * *',
        timezone: 'UTC',
        is_enabled: true,
        last_run_at: null,
        next_run_at: null,
        created_at: '2026-07-01T00:00:00Z',
        updated_at: '2026-07-01T00:00:00Z',
      },
    ])
    render(<ScansPage />)
    await waitFor(() => {
      expect(screen.getByText(/Schedule: 0 9 \* \* \*/)).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Schedule'))
    await waitFor(() => {
      expect(screen.getByText('Delete Schedule')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Delete Schedule'))
    await waitFor(() => {
      expect(api.deleteSchedule).toHaveBeenCalledWith('sch-1')
    })
  })
})
