import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { TrendsPage } from '../pages/TrendsPage'

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>()
  return {
    ...actual,
    aggregateTrends: vi.fn(),
    fetchTrendCategories: vi.fn(),
    fetchTrendTopics: vi.fn(),
    fetchTrendSeries: vi.fn(),
    fetchTrendEvidence: vi.fn(),
  }
})

import * as api from '../services/api'

describe('TrendsPage only_approved', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.fetchTrendCategories).mockResolvedValue([])
    vi.mocked(api.fetchTrendTopics).mockResolvedValue([])
    vi.mocked(api.fetchTrendSeries).mockResolvedValue({ series: [] })
    vi.mocked(api.aggregateTrends).mockResolvedValue([])
  })

  it('renders the Only approved signals toggle and aggregates with only_approved false by default', async () => {
    render(<TrendsPage />)
    expect(screen.getByText('Only approved signals')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Aggregate'))
    await waitFor(() => {
      expect(api.aggregateTrends).toHaveBeenCalledWith(
        expect.objectContaining({ only_approved: false })
      )
    })
  })

  it('passes only_approved true when the toggle is switched on', async () => {
    render(<TrendsPage />)
    // Fluent v8 Toggle: click the button referenced by the label's htmlFor
    const label = screen.getByText('Only approved signals').closest('label') as HTMLLabelElement
    const toggleButton = document.getElementById(label.htmlFor) as HTMLElement
    fireEvent.click(toggleButton)
    fireEvent.click(screen.getByText('Aggregate'))
    await waitFor(() => {
      expect(api.aggregateTrends).toHaveBeenCalledWith(
        expect.objectContaining({ only_approved: true })
      )
    })
  })
})
