/**
 * Reading `owner/name` out of what a publisher pasted.
 *
 * A publisher has the issue open in a browser, so what they have to hand is the
 * address bar, not two fields. The link and the name carry the same fact, and the API
 * stores the second, so the link is reduced to it here as the form is filled in —
 * which also lets the field say what it understood before the request is sent.
 *
 * This mirrors `backend/src/misthos/domain/repo.py`; the API normalizes as well, so a
 * link that reaches it another way is read the same.
 */

export type RepoLink = {
  /** `owner/name`, or '' when the input names no repository on GitHub. */
  repo: string
  /** The issue or pull request number a link carries, as typed. */
  number: string | null
}

const SEGMENT = /^[A-Za-z0-9_.-]+$/
const SCP = /^git@github\.com:/i
const SCHEME = /^[A-Za-z][A-Za-z0-9+.-]*:\/\//
const HOST = /^([A-Za-z0-9.-]+)\//
const KNOWN_HOSTS = new Set(['github.com', 'www.github.com'])
const NUMBER_SEGMENTS = new Set(['issues', 'pull'])

export function parseRepoLink(value: string): RepoLink {
  let text = value.trim().replace(SCP, '').replace(SCHEME, '')
  text = text.split('#')[0].split('?')[0]

  // A host is only ever `github.com`; anything else names no repository we can hold.
  const host = HOST.exec(text)
  if (host && host[1].includes('.')) {
    if (!KNOWN_HOSTS.has(host[1].toLowerCase())) return { repo: '', number: null }
    text = text.slice(host[0].length)
  }

  const parts = text.split('/').filter(Boolean)
  if (parts.length < 2) return { repo: '', number: null }

  const owner = parts[0]
  let name = parts[1]
  if (!SEGMENT.test(owner) || !SEGMENT.test(name)) return { repo: '', number: null }
  if (name.toLowerCase().endsWith('.git')) name = name.slice(0, -'.git'.length)
  // A name of dots alone is a path artefact, not a repository.
  if (!name || !SEGMENT.test(name) || /^\.+$/.test(name)) return { repo: '', number: null }

  const number =
    parts.length >= 4 && NUMBER_SEGMENTS.has(parts[2].toLowerCase()) && /^[0-9]+$/.test(parts[3])
      ? parts[3]
      : null
  return { repo: `${owner}/${name}`, number }
}
