import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DefaultButton, PrimaryButton, Stack, Text, TextField } from '@fluentui/react'
import { setApiKey } from '../services/api'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export function LoginPage() {
  const [key, setKey] = useState('')
  const navigate = useNavigate()

  const handleApiKeyLogin = () => {
    if (key.trim()) {
      setApiKey(key.trim())
      navigate('/sources')
    }
  }

  const handleMicrosoftLogin = () => {
    const returnUrl = encodeURIComponent(window.location.origin + '/auth/callback')
    window.location.href = `${API_BASE_URL}/api/v1/auth/microsoft/login?state=${returnUrl}`
  }

  return (
    <Stack horizontalAlign="center" verticalAlign="center" styles={{ root: { height: '100vh', width: '100vw' } }} tokens={{ childrenGap: 16 }}>
      <Text variant="xxLarge">Trend Scout Enterprise</Text>
      <TextField label="API Key" type="password" value={key} onChange={(_, v) => setKey(v || '')} styles={{ root: { width: 320 } }} />
      <PrimaryButton text="Enter with API Key" onClick={handleApiKeyLogin} />
      <Text>or</Text>
      <DefaultButton text="Login with Microsoft" onClick={handleMicrosoftLogin} />
    </Stack>
  )
}
