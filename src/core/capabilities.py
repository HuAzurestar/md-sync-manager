"""Single source of truth for the confirmed PIRC-14 P0 surface."""

P0_CAPABILITIES = (
    "sync.providers",
    "sync.list",
    "sync.open",
    "sync.pull",
    "sync.push",
    "sync.upload",
    "document.catalog",
    "document.focus.read",
    "document.focus.apply",
    "workbench.single-file",
)


DEFERRED_CAPABILITIES = frozenset(
    {
        "review",
        "review-view",
        "review-record",
        "document.audit",
        "document.full",
        "document.template",
        "document.pair-check",
    }
)


assert not (set(P0_CAPABILITIES) & DEFERRED_CAPABILITIES)
