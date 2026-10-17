import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { createServer, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { fileURLToPath } from 'node:url'
import { after, before, describe, it } from 'node:test'
import { ARC_USDC, GATEWAY_WALLET } from './test-fakes.js'

const ENTRY = fileURLToPath(new URL('./index.ts', import.meta.url))
const EDGE = fileURLToPath(new URL('..', import.meta.url))
const SELLER = '0x1111111111111111111111111111111111111111'
const CIRCLE = { CIRCLE_API_KEY: 'TEST_API_KEY:x:y', CIRCLE_APP_ID: 'app-1' }

/** Start the edge as `npm run dev` does, with only `env` configured. NODE_ENV=test
 * keeps it from listening, so a start that succeeds exits 0, and one that is refused
 * exits with the reason. Nothing here reaches Circle: a refused start stops before
 * any request, and no request reaches Circle before it is needed. */
function start(env: Record<string, string>): Promise<{ code: number; stderr: string }> {
  const inherited = Object.fromEntries(
    ['PATH', 'HOME', 'TMPDIR', 'SystemRoot'].flatMap((k) =>
      process.env[k] === undefined ? [] : [[k, process.env[k] as string]],
    ),
  )
  return new Promise((resolve) => {
    execFile(
      process.execPath,
      ['--import', 'tsx', ENTRY],
      { cwd: EDGE, env: { ...inherited, NODE_ENV: 'test', ...env }, timeout: 60_000 },
      (err, _stdout, stderr) => {
        const code = err === null ? 0 : typeof err.code === 'number' ? err.code : -1
        resolve({ code, stderr })
      },
    )
  })
}

describe('starting the edge', { concurrency: true }, () => {
  it('refuses to start with nothing configured', async () => {
    const run = await start({})
    assert.notEqual(run.code, 0)
    assert.match(run.stderr, /MISTHOS_SELLER_ADDRESS/)
  })

  it('starts the gate without Circle and says the wallet routes are off', async () => {
    const run = await start({ MISTHOS_SELLER_ADDRESS: SELLER, EDGE_CORE_TOKEN: 'secret' })
    assert.equal(run.code, 0, run.stderr)
    assert.match(run.stderr, /Circle wallet routes are not mounted/)
  })

  it('starts live and names the removed switch once', async () => {
    const run = await start({
      MISTHOS_SIMULATED: 'maybe',
      MISTHOS_SELLER_ADDRESS: SELLER,
      EDGE_CORE_TOKEN: 'secret',
      ...CIRCLE,
    })
    assert.equal(run.code, 0, run.stderr)
    assert.match(run.stderr, /simulation has been removed/)
  })
})

describe('the running edge', () => {
  let facilitator: Server
  let edge: Server
  let base = ''

  before(async () => {
    // A Gateway facilitator on localhost, so nothing here reaches Circle.
    facilitator = createServer((req, res) => {
      res.setHeader('Content-Type', 'application/json')
      if (req.url === '/v1/x402/supported') {
        res.end(
          JSON.stringify({
            kinds: [
              {
                x402Version: 2,
                scheme: 'exact',
                network: 'eip155:5042002',
                extra: { verifyingContract: GATEWAY_WALLET, assets: [{ symbol: 'USDC', address: ARC_USDC }] },
              },
            ],
          }),
        )
        return
      }
      res.statusCode = 404
      res.end('{}')
    }).listen(0)
    await new Promise((resolve) => facilitator.once('listening', resolve))
    Object.assign(process.env, {
      NODE_ENV: 'test',
      MISTHOS_SELLER_ADDRESS: SELLER,
      EDGE_CORE_TOKEN: 'secret',
      CORE_API_URL: 'http://10.9.8.7:8000',
      GATEWAY_FACILITATOR_URL: `http://127.0.0.1:${(facilitator.address() as AddressInfo).port}`,
    })
    const { default: app } = await import('./index.js')
    edge = app.listen(0)
    await new Promise((resolve) => edge.once('listening', resolve))
    base = `http://127.0.0.1:${(edge.address() as AddressInfo).port}`
  })

  after(async () => {
    for (const server of [edge, facilitator]) {
      server.closeAllConnections()
      await new Promise((resolve) => server.close(resolve))
    }
  })

  it('reports its health without naming the core', async () => {
    const res = await fetch(`${base}/health`)
    const text = await res.text()
    assert.equal(res.status, 200)
    assert.doesNotMatch(text, /10\.9\.8\.7|core/)
    assert.equal(JSON.parse(text).role, 'x402-seller')
  })

  it('publishes the catalog at /paid', async () => {
    const res = await fetch(`${base}/paid`)
    const body = (await res.json()) as { protocol: string; payTo: string; accepts: { asset: string }[] }
    assert.equal(res.status, 200)
    assert.equal(body.protocol, 'x402')
    assert.equal(body.payTo, SELLER)
    assert.equal(body.accepts[0].asset, ARC_USDC)
  })

  it('no longer sells the free metrics, and sells nothing it does not list', async () => {
    for (const path of ['/paid/pricing-report', '/paid/api/v1/metrics', '/paid/anything']) {
      const res = await fetch(`${base}${path}`)
      assert.equal(res.status, 404, path)
      assert.equal(res.headers.get('payment-required'), null, path)
    }
  })
})
