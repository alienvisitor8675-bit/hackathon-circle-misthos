import { describe, expect, it } from 'vitest'
import type { IssueOut } from './client'
import { STATE_LABELS, STATE_TONES, reviewResult, stateLabel } from './state'

function issue(overrides: Partial<IssueOut>): IssueOut {
  return {
    state: 'IN_REVIEW',
    submission: null,
    review: null,
    ...overrides,
  } as IssueOut
}

const review = {
  verdict: 'accept' as const,
  findings: [],
  decided_at: '2026-10-18T00:00:00Z',
  head_sha: 'abc',
}

describe('the names a state is shown by', () => {
  it('gives the filter and the badge the same words', () => {
    expect(stateLabel('AWAITING_APPROVAL')).toBe('Needs price approval')
    expect(stateLabel('FUNDED')).toBe('Funded, unclaimed')
    expect(stateLabel('PAID')).toBe('Settled')
  })

  it('has no name or colour for a status the lifecycle removed', () => {
    expect(STATE_LABELS.REWORK).toBeUndefined()
    expect(STATE_LABELS.ACCEPTED).toBeUndefined()
    expect(STATE_TONES.REWORK).toBeUndefined()
    expect(STATE_TONES.ACCEPTED).toBeUndefined()
  })
})

describe('the review result on the issue page', () => {
  it('says a passing verdict is ready to merge while the issue stays in review', () => {
    const result = reviewResult(
      issue({ state: 'IN_REVIEW', submission: { head_sha: 'abc' } as never, review }),
    )
    expect(result).toEqual({ label: 'Passed review, ready to merge', tone: 'ok' })
  })

  it('says a failed verdict asked for changes', () => {
    const result = reviewResult(
      issue({
        state: 'CLAIMED',
        submission: { head_sha: 'abc' } as never,
        review: { ...review, verdict: 'rework' },
      }),
    )
    expect(result).toEqual({ label: 'Changes requested', tone: 'warn' })
  })

  it('does not carry a verdict onto a commit it never judged', () => {
    const result = reviewResult(
      issue({ state: 'IN_REVIEW', submission: { head_sha: 'def' } as never, review }),
    )
    expect(result).toEqual({ label: 'New commit, waiting for review', tone: 'info' })
  })

  it('shows the publisher declining a passing verdict as changes requested', () => {
    const result = reviewResult(
      issue({ state: 'CLAIMED', submission: { head_sha: 'abc' } as never, review }),
      true,
    )
    expect(result).toEqual({ label: 'Changes requested by the publisher', tone: 'warn' })
  })
})
