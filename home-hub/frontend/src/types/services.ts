export interface ServiceHealth {
  status: 'up' | 'down' | 'unknown'
  type?: string
  url?: string
  detail?: string
}

export interface ServiceItem {
  id: string
  name: string
  description?: string
  local_url?: string
  dev_url?: string
  public_url?: string
  internal_url?: string
  public_note?: string
  health_note?: string
  doc?: string
  compose_dir?: string | null
  docker_container?: string
  docker_running?: boolean
  credentials: Record<string, string>
  health?: ServiceHealth
}

export interface ServiceCategory {
  id: string
  name: string
  items: ServiceItem[]
}

export interface ServicesCatalog {
  domains: Record<string, unknown>
  categories: ServiceCategory[]
  docker_containers_running: string[]
}

export interface JellyfinLibrary {
  library: string
  list_file: string
  staging_prefix: string
  count: number
  items: Array<{
    source: string
    staging: string
    title: string
    season: string
  }>
}

export interface JellyfinMappings {
  stack_dir: string
  libraries: JellyfinLibrary[]
  total_items: number
}
