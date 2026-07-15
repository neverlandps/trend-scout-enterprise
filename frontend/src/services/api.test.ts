import { describe, it, expect } from 'vitest'
import { setApiKey, getApiKey } from '../services/api'

describe('api service', () => {
  it('sets and reads the API key header', () => {
    setApiKey('tse_test_key')
    expect(getApiKey()).toBe('tse_test_key')
  })

  it('clears the API key header', () => {
    setApiKey('tse_test_key')
    expect(getApiKey()).toBe('tse_test_key')
    setApiKey('')
    expect(getApiKey()).toBe('')
  })
})
