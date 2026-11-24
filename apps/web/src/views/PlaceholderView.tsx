export function PlaceholderView({ title, phase }: { title: string; phase: string }) {
  return (
    <div className="view">
      <header className="view-head">
        <h1>{title}</h1>
      </header>
      <div className="placeholder">
        <p>
          <strong>{title}</strong> is planned for <strong>{phase}</strong> of the roadmap (see <code>docs/roadmap.md</code>).
        </p>
        <p className="hint">
          The data model and audit trail built in Phase 1 are designed so this view can be added without migrating your
          existing tasks or notes destructively.
        </p>
      </div>
    </div>
  );
}
