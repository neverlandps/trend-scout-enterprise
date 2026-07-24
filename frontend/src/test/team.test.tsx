import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { TeamPage } from '../pages/TeamPage'

const members = [
  { id: 'member-1', name: 'Alice Admin', role: 'admin', key_prefix: 'tse_a', is_active: true, created_at: '2026-07-01T00:00:00Z' },
  { id: 'member-2', name: 'Bob Analyst', role: 'analyst', key_prefix: 'tse_b', is_active: true, created_at: '2026-07-01T00:00:00Z' },
]

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>()
  return {
    ...actual,
    default: {
      get: vi.fn(),
      post: vi.fn(),
      defaults: { headers: { common: {} } },
    },
    fetchReviewAssignments: vi.fn(),
    createReviewAssignment: vi.fn(),
    deleteReviewAssignment: vi.fn(),
  }
})

import api, * as apiFns from '../services/api'

const assignment = {
  id: 'ra-1',
  workspace_id: 'ws-1',
  category: 'energy',
  reviewer_id: 'member-2',
  created_at: '2026-07-01T00:00:00Z',
}

describe('TeamPage review assignments', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.get).mockResolvedValue({ data: members })
    vi.mocked(apiFns.fetchReviewAssignments).mockResolvedValue([assignment])
  })

  it('renders the Review Assignments section with reviewer names', async () => {
    render(<TeamPage />)
    expect(screen.getByText('Review Assignments')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('energy')).toBeInTheDocument()
      // member row + assignment reviewer cell
      expect(screen.getAllByText('Bob Analyst').length).toBeGreaterThanOrEqual(2)
    })
    expect(screen.getByText('Add Assignment')).toBeInTheDocument()
    expect(screen.getByText('Delete')).toBeInTheDocument()
  })

  it('adds an assignment with the selected reviewer', async () => {
    render(<TeamPage />)
    await waitFor(() => {
      expect(screen.getByText('energy')).toBeInTheDocument()
    })
    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'battery' } })
    fireEvent.click(screen.getByLabelText('Reviewer'))
    await waitFor(() => {
      expect(screen.getAllByText('Alice Admin').length).toBeGreaterThanOrEqual(2)
    })
    // Dropdown options render in a layer; click the option (not the member row text)
    const options = screen.getAllByText('Alice Admin')
    fireEvent.click(options[options.length - 1])
    fireEvent.click(screen.getByText('Add Assignment'))
    await waitFor(() => {
      expect(apiFns.createReviewAssignment).toHaveBeenCalledWith({ category: 'battery', reviewer_id: 'member-1' })
    })
  })

  it('deletes an assignment', async () => {
    render(<TeamPage />)
    await waitFor(() => {
      expect(screen.getByText('Delete')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Delete'))
    await waitFor(() => {
      expect(apiFns.deleteReviewAssignment).toHaveBeenCalledWith('ra-1')
    })
  })
})
