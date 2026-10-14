# Changelog

Notable changes to Misthos, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Changed

- **The web app opens on a landing page** (#140, #167). `/` is now the public front page
  from the `landing-page-for-misthos` prototype: what Misthos is, how an issue goes from
  funded to paid, and the way in.
  - Its community snapshot reads `/api/v1/metrics` and names the network and the money
    from `/api/v1/health`.
  - Its "Current issues" table lists `/api/v1/issues`, with the prototype's filters, and
    each row opens the issue in the app.
  - Signing in stays the API's own. The prototype's wallet sign-in, database and profile
    pages were not ported.
- **The overview moved from `/` to `/overview`.** The nav follows it, and the app's brand
  now carries the landing's `m.` mark and links home. The favicon is the same mark.
