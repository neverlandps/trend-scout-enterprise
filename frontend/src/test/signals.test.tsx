import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { SignalsPage } from '../pages/SignalsPage'
import type { Signal } from '../services/api'

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>()
  return {
    ...actual,
    fetchReviewQueue: vi.fn(),
    fetchSignals: vi.fn(),
    fetchSources: vi.fn(),
    reviewSignal: vi.fn(),
    bulkReviewSignals: vi.fn(),
    submitSignalFeedback: vi.fn(),
  }
})

import * as api from '../services/api'

const pendingSignal: Signal = {
  id: 'sig-1',
  source_id: 'src-1',
  url: 'https://example.com/article',
  title: 'Test signal title',
  summary: 'A test summary',
  published_at: null,
  collected_at: '2026-07-01T00:00:00Z',
  overall_score: 0.75,
  signal_strength: 0.7,
  cross_domain_impact: 0.6,
  investment_velocity: 0.5,
  technical_feasibility: 0.8,
  strategic_fit: 0.65,
  review_status: 'pending_review',
  human_score: null,
  assigned_reviewer_id: null,
}

describe('SignalsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.fetchReviewQueue).mockResolvedValue({ signals: [pendingSignal], total: 1 })
    vi.mocked(api.fetchSignals).mockResolvedValue({ signals: [pendingSignal], total: 1 })
    vi.mocked(api.fetchSources).mockResolvedValue([
      {
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
      },
    ])
  })

  it('renders without crashing and shows the review queue', async () => {
    render(<SignalsPage />)
    expect(screen.getByText('Signals')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('Test signal title')).toBeInTheDocument()
    })
    expect(api.fetchReviewQueue).toHaveBeenCalled()
    expect(screen.getByText('pending_review')).toBeInTheDocument()
  })

  it('shows bulk action buttons and status filter pivots', async () => {
    render(<SignalsPage />)
    expect(screen.getByText(/Bulk Approve/)).toBeInTheDocument()
    expect(screen.getByText(/Bulk Reject/)).toBeInTheDocument()
    expect(screen.getByText('Pending Review')).toBeInTheDocument()
    expect(screen.getByText('Approved')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument()
      expect(screen.getByText('Reject')).toBeInTheDocument()
      expect(screen.getByText('Flag')).toBeInTheDocument()
    })
  })

  it('shows an error message when loading fails', async () => {
    vi.mocked(api.fetchReviewQueue).mockRejectedValue(new Error('boom'))
    render(<SignalsPage />)
    await waitFor(() => {
      expect(screen.getByText(/boom/)).toBeInTheDocument()
    })
  })
})
