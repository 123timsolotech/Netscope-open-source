import { Search } from 'lucide-react'
import { useId, useState } from 'react'
import { useNavigate } from 'react-router'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { searchPath } from '@/lib/dashboard'

/** Opens the device list with the search in its URL, where the search runs (owner decision,
 * M7). */
export function QuickSearch() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const id = useId()
  return (
    <form
      role="search"
      className="flex gap-2"
      onSubmit={(event) => {
        event.preventDefault()
        void navigate(searchPath(query))
      }}
    >
      <label htmlFor={id} className="sr-only">
        Search devices
      </label>
      <div className="relative min-w-0 flex-1">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          id={id}
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
          }}
          placeholder="Search name, IP, MAC, vendor, service, port…"
          autoComplete="off"
          dir="auto"
          className="pl-8"
        />
      </div>
      <Button type="submit">Search</Button>
    </form>
  )
}
