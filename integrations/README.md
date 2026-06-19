# Integrations (Phase 5 — not built yet)

Scaffold only. The `integrations` table and `IntegrationAdapter` interface exist
so that lighting up a project later is purely additive — **do not implement
adapters now** (handoff Section 9, Phase 5).

## Adding an adapter later

1. Create `integrations/<name>.py` subclassing `IntegrationAdapter`.
2. Implement `listen()` to poll or receive webhooks, yielding `IntegrationEvent`s.
3. Insert a row in `integrations` (`name`, `type`, `config_json`, `channel_id`,
   `active=true`) and create the `#<project>` channel.
4. A future runner reads active integrations, instantiates each adapter, and
   posts `adapter.format(event)` to `channel_id`.

## Planned first adapters (templates)

- **Bulk-card eBay** → `#bulk-card-ebay`: notify when an item sells.
- **Binders** → `#binders`: notify when a binder sells or a preorder quota is hit.

## Inbound networking

Prefer polling on a timer (no inbound holes). If a source must push, route it
through a Cloudflare Tunnel rather than opening a port (architecture Section 9).
