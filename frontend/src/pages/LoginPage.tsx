import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PrimaryButton, Stack, Text, TextField } from '@fluentui/react'
import { setApiKey } from '../services/api'

export function LoginPage() {
  const [key, setKey] = useState('')
  const navigate = useNavigate()

  const handleLogin = () => {
    if (key.trim()) {
      setApiKey(key.trim())
      navigate('/sources')
    }
  }

  return (
    <Stack horizontalAlign="center" verticalAlign="center" styles={{ root: { height: '100vh', width: '100vw' } }} tokens={{ childrenGap: 16 }}>
      <Text variant="xxLarge">Trend Scout Enterprise</Text>
      <TextField label="API Key" type="password" value={key} onChange={(_, v) => setKey(v || '')} styles={{ root: { width: 320 } }} />
      <PrimaryButton text="Enter" onClick={handleLogin} />
    </Stack>
  )
}
