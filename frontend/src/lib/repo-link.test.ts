import { describe, expect, it } from 'vitest'
import { parseRepoLink } from './repo-link'

const SAME_REPOSITORY = [
  'acme/ledger',
  'acme/ledger/',
  'acme/ledger.git',
  'github.com/acme/ledger',
  'www.github.com/acme/ledger',
  'https://github.com/acme/ledger',
  'http://github.com/acme/ledger',
  'https://github.com/acme/ledger/',
  'https://github.com/acme/ledger.git',
  'https://github.com/acme/ledger/tree/main',
  'https://github.com/acme/ledger/blob/main/src/ledger.py',
  'git@github.com:acme/ledger.git',
  '  https://github.com/acme/ledger  ',
  'https://github.com/acme/ledger/issues/12',
  'https://github.com/acme/ledger/pull/7',
]

describe('parseRepoLink', () => {
  it.each(SAME_REPOSITORY)('reads %s as acme/ledger', (pasted) => {
    expect(parseRepoLink(pasted).repo).toBe('acme/ledger')
  })

  it.each([
    ['https://github.com/acme/ledger/issues/12', '12'],
    ['https://github.com/acme/ledger/pull/7', '7'],
    ['https://github.com/acme/ledger/pull/7/files', '7'],
    ['https://github.com/acme/ledger', null],
    ['https://github.com/acme/ledger/tree/main', null],
    ['acme/ledger', null],
  ])('reads the issue number out of %s', (pasted, expected) => {
    expect(parseRepoLink(pasted).number).toBe(expected)
  })

  it.each([
    '',
    '   ',
    'acme', // an owner alone names no repository
    'ledger.git',
    'https://github.com/acme', // a profile, not a repository
    'https://gist.github.com/user/1234', // right host, not a repository URL
    'https://gitlab.com/acme/ledger', // another host
    'https://github.com/acme/../etc', // a traversal, not a repository
    'acme/',
  ])('refuses %s, which names no repository', (pasted) => {
    expect(parseRepoLink(pasted)).toEqual({ repo: '', number: null })
  })

  it('keeps the case a publisher used, which is how GitHub compares it', () => {
    expect(parseRepoLink('https://github.com/Acme/Ledger').repo).toBe('Acme/Ledger')
  })
})
