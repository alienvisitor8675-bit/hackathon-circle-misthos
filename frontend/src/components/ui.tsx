/** Shared presentational pieces. Small enough not to need a component library. */

import { checksChip } from '../lib/client'
import { STATE_TONES, stateLabel } from '../lib/state'

export function StateBadge({ state }: { state: string }) {
  const tone = STATE_TONES[state] ?? ''
  return <span className={`chip ${tone}`}>{stateLabel(state)}</span>
}

export function ChecksChip({ passed }: { passed: boolean | null }) {
  const { label, tone } = checksChip(passed)
  return <span className={`chip ${tone}`}>{label}</span>
}

export function Stat({
  label,
  value,
  hint,
}: {
  label: string
  value: React.ReactNode
  hint?: string
}) {
  return (
    <div className="panel">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
}

export function Bar({
  label,
  value,
  max,
  cool,
}: {
  label: string
  value: number
  max: number
  cool?: boolean
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="bar-row">
      <span className="dim">{label.replace(/_/g, ' ')}</span>
      <span className="bar-track">
        <span className={`bar-fill ${cool ? 'cool' : ''}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="mono-num muted">{value.toFixed(1)}</span>
    </div>
  )
}

export function Panel({
  title,
  children,
  flush,
}: {
  title?: string
  children: React.ReactNode
  flush?: boolean
}) {
  return (
    <section className={`panel ${flush ? 'flush' : ''}`}>
      {title && <h2 className="panel-title">{title}</h2>}
      {children}
    </section>
  )
}

/** The lifecycle as a horizontal read-out. Branches are shown as extra chips. */
const MAIN_LINE = [
  'PRICED',
  'AWAITING_APPROVAL',
  'FUNDED',
  'CLAIMED',
  'IN_REVIEW',
  'PAID',
]

const BRANCHES = ['REJECTED', 'REFUNDED']

export function Stepper({ state }: { state: string }) {
  const inBranch = BRANCHES.includes(state)
  const currentIndex = MAIN_LINE.indexOf(state)

  return (
    <div className="stepper">
      {MAIN_LINE.map((step, i) => {
        const done = !inBranch && currentIndex > i
        const current = !inBranch && currentIndex === i
        return (
          <span className="step" key={step}>
            {i > 0 && <span className="step-line" />}
            <span className={`step-node ${done ? 'done' : ''} ${current ? 'current' : ''}`}>
              <i className="marker" />
              {stateLabel(step)}
            </span>
          </span>
        )
      })}
      {inBranch && (
        <span className="step">
          <span className="step-line" />
          <span className="step-node current">
            <i className="marker" />
            {stateLabel(state)}
          </span>
        </span>
      )}
    </div>
  )
}
