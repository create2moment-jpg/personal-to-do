"""Personal Productivity & AI Operating System (PPOS).

Layering (dependencies point inward only):

    presentation (apps/api, apps/web)
        -> application (use cases, ports)
            -> domain (entities, rules; no I/O)
    infrastructure implements application ports (SQLite, filesystem, backups).
    ai (Phase 5+) is a dedicated layer that only *proposes*; application owns state.
"""

__version__ = "0.1.0"
