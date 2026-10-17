import './public-api.css'

type Endpoint = {
  method: 'GET'
  path: string
  name: string
  summary: string
  group: 'Core' | 'Marketplace' | 'Analytics' | 'Trust'
  returns: string
  price?: string
}

const ENDPOINTS: Endpoint[] = [
  {
    method: 'GET',
    path: '/api/v1/health',
    name: 'Health',
    summary: 'Network, contract addresses and the money mode this deployment is running.',
    group: 'Core',
    returns: 'HealthOut',
  },
  {
    method: 'GET',
    path: '/api/v1/issues',
    name: 'List issues',
    summary: 'Every published issue with its price, state and acceptance criteria.',
    group: 'Marketplace',
    returns: 'IssueSummaryOut[]',
  },
  {
    method: 'GET',
    path: '/api/v1/issues/{issue_id}',
    name: 'Issue detail',
    summary: 'One issue, its escrow address, publisher and current lifecycle state.',
    group: 'Marketplace',
    returns: 'IssueOut',
  },
  {
    method: 'GET',
    path: '/api/v1/issues/{issue_id}/timeline',
    name: 'Issue timeline',
    summary: 'The public audit trail: pricing, funding, claims, reviews and settlement.',
    group: 'Marketplace',
    returns: 'TimelineEntry[]',
  },
  {
    method: 'GET',
    path: '/api/v1/publishers',
    name: 'Publisher directory',
    summary: 'Publishers with a public listing and the issues they have funded.',
    group: 'Marketplace',
    returns: 'PublisherListing[]',
  },
  {
    method: 'GET',
    path: '/api/v1/decisions',
    name: 'Public decisions',
    summary: 'Accept and reject decisions with the reviewer note attached.',
    group: 'Trust',
    returns: 'Decision[]',
  },
  {
    method: 'GET',
    path: '/api/v1/contributors',
    name: 'Contributor directory',
    summary: 'Contributors, their claimed issues and settled work.',
    group: 'Trust',
    returns: 'ContributorProfile[]',
  },
  {
    method: 'GET',
    path: '/api/v1/contributors/{id}/reputation',
    name: 'Reputation events',
    summary: 'Raw reputation events for one contributor, newest first.',
    group: 'Trust',
    returns: 'ReputationEventOut[]',
    price: '0.01',
  },
  {
    method: 'GET',
    path: '/api/v1/metrics',
    name: 'Marketplace metrics',
    summary: 'Settlement volume, take rate, time to merge and live issue counts.',
    group: 'Analytics',
    returns: 'MetricsOut',
    price: '0.01',
  },
  {
    method: 'GET',
    path: '/api/v1/issues/{issue_id}/commitment',
    name: 'Commitment plan',
    summary: 'The priced commitment for an issue before a publisher funds it.',
    group: 'Analytics',
    returns: 'CommitmentPlan',
    price: '0.002',
  },
  {
    method: 'GET',
    path: '/api/v1/issues/{issue_id}/escrow',
    name: 'Escrow readback',
    summary: 'On-chain escrow state, funded amount and release conditions.',
    group: 'Analytics',
    returns: 'EscrowReadback',
    price: '0.005',
  },
  {
    method: 'GET',
    path: '/api/v1/publishers/{publisher_id}/repositories',
    name: 'Publisher repositories',
    summary: 'Repositories a publisher has connected, with issue counts.',
    group: 'Analytics',
    returns: 'RepositoriesOut',
    price: '0.005',
  },
]

const GROUPS = ['Core', 'Marketplace', 'Analytics', 'Trust'] as const
const FREE = ENDPOINTS.filter((e) => !e.price).length
const PAID = ENDPOINTS.length - FREE

function Price({ price }: { price?: string }) {
  if (!price) return <span className="api-free">Free</span>
  return (
    <span className="api-pay">
      <span className="api-x402">x402</span>
      <b>{price}</b> USDC
    </span>
  )
}

export default function PublicApi() {
  return (
    <div className="api-index">
      <div className="api-toolbar">
        <div className="api-tabs" role="tablist" aria-label="Filter endpoints">
          <button type="button" className="api-tab active">
            All <span>{ENDPOINTS.length}</span>
          </button>
          <button type="button" className="api-tab">
            Free <span>{FREE}</span>
          </button>
          <button type="button" className="api-tab">
            x402 <span>{PAID}</span>
          </button>
        </div>
        <div className="api-base">
          <span>Version</span>
          <code>2026-10-17</code>
        </div>
      </div>

      <div className="api-layout">
        <main id="endpoints" className="api-list">
          {GROUPS.map((group) => {
            const rows = ENDPOINTS.filter((e) => e.group === group)
            if (!rows.length) return null
            return (
              <section className="api-group" key={group}>
                <div className="api-group-head">
                  <h2>{group}</h2>
                  <span>{rows.length} endpoints</span>
                </div>
                <div className="api-table">
                  {rows.map((ep) => (
                    <article className={`api-row ${ep.price ? 'paid' : ''}`} key={ep.path}>
                      <span className="api-method">{ep.method}</span>
                      <div className="api-endpoint">
                        <code>{ep.path}</code>
                        <p>
                          <b>{ep.name}</b> — {ep.summary}
                        </p>
                      </div>
                      <span className="api-returns">{ep.returns}</span>
                      <Price price={ep.price} />
                      <span className="api-arrow" aria-hidden="true">
                        →
                      </span>
                    </article>
                  ))}
                </div>
              </section>
            )
          })}
        </main>
      </div>
    </div>
  )
}
