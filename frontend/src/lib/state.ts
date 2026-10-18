import type { IssueOut } from './client'

/** The names a state is shown by, in filters and badges alike. */
export const STATE_LABELS: Record<string, string> = {
  DRAFT: 'Draft',
  PRICED: 'Priced',
  AWAITING_APPROVAL: 'Needs price approval',
  FUNDED: 'Funded, unclaimed',
  CLAIMED: 'Claimed',
  IN_REVIEW: 'In review',
  PAID: 'Settled',
  REJECTED: 'Rejected',
  REFUNDED: 'Refunded',
}

/** The colour a state's badge wears. */
export const STATE_TONES: Record<string, string> = {
  DRAFT: '',
  PRICED: 'info',
  AWAITING_APPROVAL: 'warn',
  FUNDED: 'accent',
  CLAIMED: 'info',
  IN_REVIEW: 'accent',
  PAID: 'ok',
  REJECTED: 'bad',
  REFUNDED: '',
}

export function stateLabel(state: string): string {
  return STATE_LABELS[state] ?? state.replace(/_/g, ' ')
}

/**
 * What the review says about the work, in the issue page's words.
 *
 * A passing verdict leaves the issue in review until the publisher merges, so the
 * state alone cannot say whether the work is ready; the verdict and the commit it
 * judged can. A verdict is about one commit, so a later push is waiting for its own
 * review rather than carrying the old one.
 */
export function reviewResult(
  issue: IssueOut,
  declinedAfterReview = false,
): { label: string; tone: string } | null {
  const review = issue.review
  if (!review) return null

  if (issue.state === 'PAID') return { label: 'Passed review', tone: 'ok' }
  if (review.verdict === 'reject') return { label: 'Rejected', tone: 'bad' }

  const current = Boolean(issue.submission) && review.head_sha === issue.submission?.head_sha
  if (!current) return { label: 'New commit, waiting for review', tone: 'info' }
  if (review.verdict === 'rework') return { label: 'Changes requested', tone: 'warn' }
  if (declinedAfterReview) {
    return { label: 'Changes requested by the publisher', tone: 'warn' }
  }
  return { label: 'Passed review, ready to merge', tone: 'ok' }
}
