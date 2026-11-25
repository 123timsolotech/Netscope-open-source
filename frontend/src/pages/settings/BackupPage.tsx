import { Download } from 'lucide-react'
import { useEffect, useId, useRef, useState, type ChangeEvent, type ReactNode } from 'react'
import { toast } from 'sonner'

import type { ImportMode, ImportResult } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { FormField } from '@/components/FormField'
import { Notice } from '@/components/Notice'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useExport, useImport } from '@/hooks/useBackup'
import {
  chosenFileSize,
  importProblem,
  importSummary,
  isTooLarge,
  replaceWarning,
  TOO_LARGE_MESSAGE,
  type ImportProblem,
} from '@/lib/backup'
import { saveFile } from '@/lib/download'
import { cn } from '@/lib/utils'

/** A box that gets focus after a check or an import (programmatically, tabIndex -1). */
const FOCUS_BOX = 'outline-none focus-visible:ring-2 focus-visible:ring-ring/50'

const MODES: { value: ImportMode; label: string; description: string }[] = [
  {
    value: 'replace',
    label: 'Replace all',
    description:
      'Deletes every device, category and link (with their status history), then adds what is in the file. Your login stays.',
  },
  {
    value: 'merge',
    label: 'Merge by device name',
    description:
      'Adds what is in the file. Devices and categories with the same name are updated from the file; nothing is deleted.',
  },
]

function Card({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="grid gap-4 rounded-xl border bg-card p-4 sm:p-5">
      <h3 id={id} className="font-medium">
        {title}
      </h3>
      {children}
    </section>
  )
}

/** Settings → Backup (owner decision, M8): JSON export and import. */
export function BackupPage() {
  return (
    <div className="grid max-w-2xl gap-6">
      <div className="grid gap-1">
        <h2 className="text-lg font-semibold">Backup</h2>
        <p className="text-sm text-muted-foreground">
          Save everything you entered as one file, or bring it back from such a file.
        </p>
      </div>
      <ExportCard />
      <ImportCard />
    </div>
  )
}

function ExportCard() {
  const exporting = useExport()
  const [error, setError] = useState<string | null>(null)

  function onExport() {
    // aria-disabled, not disabled, while it runs: the button keeps focus.
    if (exporting.isPending) return
    setError(null)
    exporting.mutate(undefined, {
      onSuccess: ({ blob, fileName }) => {
        saveFile(blob, fileName)
        toast.success(`Exported ${fileName}.`)
      },
      onError: (failure) => {
        setError(failure.message)
      },
    })
  }

  return (
    <Card id="backup-export" title="Export">
      <p className="text-sm text-muted-foreground">
        One JSON file with your devices and their services, the links, the categories and the
        status-check settings you changed. It does not contain your password, sessions or status
        history.
      </p>
      {error && <Notice tone="error" title="Could not export." messages={[error]} />}
      <div>
        <Button onClick={onExport} aria-disabled={exporting.isPending || undefined}>
          <Download aria-hidden="true" />
          {exporting.isPending ? 'Preparing export…' : 'Download export'}
        </Button>
      </div>
    </Card>
  )
}

type Outcome = { kind: 'imported'; result: ImportResult } | ({ kind: 'problem' } & ImportProblem)

/**
 * Choose a file and a mode, check the file (a dry run that shows what will happen), then
 * import it; Replace all asks first. Changing the file or the mode drops the check.
 */
function ImportCard() {
  const checking = useImport()
  const importing = useImport()
  const [file, setFile] = useState<File | null>(null)
  const [inputKey, setInputKey] = useState(0) // a new key empties the file input
  const [mode, setMode] = useState<ImportMode>('replace')
  const [check, setCheck] = useState<ImportResult | null>(null)
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [confirmError, setConfirmError] = useState<string | null>(null)
  // Focus moves to what a check or an import found: the summary or the result box (the
  // buttons that started them change or disappear).
  const outcomeRef = useRef<HTMLDivElement | null>(null)
  const checkRef = useRef<HTMLDivElement | null>(null)
  const focusNext = useRef<'check' | 'outcome' | null>(null)
  const modeId = useId()

  const busy = checking.isPending || importing.isPending
  const tooLarge = file !== null && isTooLarge(file.size)

  // After every render: move focus once the box it should go to is shown (and the
  // confirmation is closed, so its focus trap does not take it back).
  useEffect(() => {
    if (focusNext.current === null || confirming) return
    const target = focusNext.current === 'check' ? checkRef.current : outcomeRef.current
    focusNext.current = null
    target?.focus()
  })

  function startOver() {
    setCheck(null)
    setOutcome(null)
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null)
    startOver()
  }

  function onModeChange(next: ImportMode) {
    setMode(next)
    startOver()
  }

  function onCheck() {
    if (file === null || tooLarge || busy) return
    startOver()
    checking.mutate(
      { file, mode, dryRun: true },
      {
        onSuccess: (result) => {
          setCheck(result)
          focusNext.current = 'check'
        },
        onError: (error) => {
          setOutcome({ kind: 'problem', ...importProblem(error, 'check') })
          focusNext.current = 'outcome'
        },
      },
    )
  }

  function runImport() {
    if (file === null) return
    setConfirmError(null)
    const fromDialog = confirming
    importing.mutate(
      { file, mode, dryRun: false },
      {
        onSuccess: (result) => {
          // No toast: the result box says it, and a toast covered its last line on a phone.
          setConfirming(false)
          setCheck(null)
          setFile(null)
          setInputKey((key) => key + 1)
          setOutcome({ kind: 'imported', result })
          focusNext.current = 'outcome'
        },
        onError: (error) => {
          const problem = importProblem(error, 'import')
          if (problem.keepDialog && fromDialog) {
            // NetScope could not be reached at all: nothing happened, so try again from here.
            setConfirmError(problem.lines.join(' '))
            return
          }
          setConfirming(false)
          if (problem.checkAgain) setCheck(null)
          setOutcome({ kind: 'problem', ...problem })
          focusNext.current = 'outcome'
        },
      },
    )
  }

  function onImport() {
    if (busy) return
    if (mode === 'replace') {
      setConfirmError(null)
      setConfirming(true)
    } else {
      runImport()
    }
  }

  return (
    <Card id="backup-import" title="Import">
      <p className="text-sm text-muted-foreground">
        Brings back an export file. NetScope checks the whole file first and changes nothing if
        something in it is wrong.
      </p>

      <FormField
        label="Export file"
        hint="A .json file made with Download export, at most 10 MiB."
        error={tooLarge ? TOO_LARGE_MESSAGE : undefined}
      >
        {(control) => (
          <div className="grid gap-1.5">
            <Input
              {...control}
              key={inputKey}
              type="file"
              accept=".json,application/json"
              disabled={busy}
              onChange={onFileChange}
              className="cursor-pointer"
            />
            {file && (
              <p className="text-sm">
                <span dir="auto" className="font-medium [overflow-wrap:anywhere]">
                  {file.name}
                </span>
                <span className="text-muted-foreground"> · {chosenFileSize(file.size)}</span>
              </p>
            )}
          </div>
        )}
      </FormField>

      <fieldset className="grid gap-2" disabled={busy}>
        <legend className="mb-2 text-sm font-medium">How to import</legend>
        {MODES.map((option) => {
          const id = `${modeId}-${option.value}`
          return (
            <div key={option.value} className="flex gap-3 rounded-lg border p-3">
              <input
                id={id}
                type="radio"
                name={`${modeId}-mode`}
                value={option.value}
                checked={mode === option.value}
                onChange={() => {
                  onModeChange(option.value)
                }}
                aria-describedby={`${id}-description`}
                className="mt-0.5 size-4 shrink-0 cursor-pointer accent-primary"
              />
              <div className="grid gap-0.5">
                <label htmlFor={id} className="cursor-pointer text-sm font-medium">
                  {option.label}
                </label>
                <p id={`${id}-description`} className="text-sm text-muted-foreground">
                  {option.description}
                </p>
              </div>
            </div>
          )
        })}
      </fieldset>

      <div>
        <Button
          variant={check ? 'outline' : 'default'}
          disabled={file === null || tooLarge}
          aria-disabled={busy || undefined}
          onClick={onCheck}
        >
          {checking.isPending ? 'Checking…' : 'Check file'}
        </Button>
      </div>

      {check && (
        <div
          ref={checkRef}
          tabIndex={-1}
          className={cn('grid gap-3 rounded-lg border bg-muted/40 p-3', FOCUS_BOX)}
        >
          <div role="status" className="grid gap-1 text-sm">
            <p className="font-medium">The file can be imported. This will happen:</p>
            <ul className="grid list-disc gap-0.5 pl-4">
              {importSummary(check).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
          <div>
            <Button
              variant={mode === 'replace' ? 'destructive' : 'default'}
              aria-disabled={busy || undefined}
              onClick={onImport}
            >
              {importing.isPending && !confirming
                ? 'Importing…'
                : mode === 'replace'
                  ? 'Replace everything'
                  : 'Import'}
            </Button>
          </div>
        </div>
      )}

      <div ref={outcomeRef} tabIndex={-1} className={cn('rounded-lg empty:hidden', FOCUS_BOX)}>
        {outcome?.kind === 'imported' && (
          <Notice
            tone="success"
            title="The file was imported."
            messages={[
              ...importSummary(outcome.result),
              ...(outcome.result.backup_file
                ? [`NetScope saved a copy of the database first: ${outcome.result.backup_file}`]
                : []),
            ]}
          />
        )}
        {outcome?.kind === 'problem' && (
          <Notice tone="error" title={outcome.title} messages={outcome.lines} note={outcome.hint} />
        )}
      </div>

      {check && (
        <ConfirmDialog
          open={confirming}
          onOpenChange={(open) => {
            setConfirming(open)
            if (!open) setConfirmError(null)
          }}
          title="Replace everything?"
          description={replaceWarning(check)}
          confirmLabel="Replace everything"
          onConfirm={runImport}
          pending={importing.isPending}
          error={confirmError}
          returnFocus={() => outcomeRef.current}
        />
      )}
    </Card>
  )
}
