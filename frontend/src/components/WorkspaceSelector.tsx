import { Dropdown, IDropdownOption, MessageBar, MessageBarType, Stack } from '@fluentui/react'
import { useWorkspace } from '../contexts/WorkspaceContext'

export function WorkspaceSelector() {
  const { workspaces, currentWorkspace, loading, error, switchWorkspace } = useWorkspace()

  const options: IDropdownOption[] = workspaces.map(w => ({
    key: w.id,
    text: `${w.name}${w.is_default ? ' (default)' : ''}`,
  }))

  return (
    <Stack horizontal tokens={{ childrenGap: 8 }} verticalAlign="center" styles={{ root: { minWidth: 200 } }}>
      {error && <MessageBar messageBarType={MessageBarType.error}>{error}</MessageBar>}
      <Dropdown
        label="Workspace"
        selectedKey={currentWorkspace?.id}
        options={options}
        disabled={loading}
        onChange={(_, option) => option && switchWorkspace(String(option.key))}
      />
    </Stack>
  )
}
