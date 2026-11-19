import React, { useState, useEffect, useMemo } from 'react';
import { apiUrl, getAuthHeaders } from '../api';

export default function AuditScreen({ onNavigateReport }) {
  const [auditEntries, setAuditEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  const fetchAudit = () => {
    setLoading(true);
    fetch(apiUrl('/audit?limit=200'), { headers: getAuthHeaders() })
      .then(res => res.json())
      .then(data => {
        const log = data?.audit_log || data?.reviews || [];
        setAuditEntries(Array.isArray(log) ? log : []);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchAudit();
  }, []);

  const counts = useMemo(() => {
    let accept = 0;
    let override = 0;
    let comment = 0;
    auditEntries.forEach(e => {
      const a = (e.action || '').toLowerCase();
      if (a === 'accept') accept++;
      else if (a === 'override') override++;
      else if (a === 'comment') comment++;
    });
    return { total: auditEntries.length, accept, override, comment };
  }, [auditEntries]);

  const filteredEntries = useMemo(() => {
    return auditEntries.filter(entry => {
      const a = (entry.action || '').toLowerCase();
      const matchesAction = actionFilter === 'all' || a === actionFilter;
      const q = searchQuery.toLowerCase();
      const matchesSearch =
        !q ||
        (entry.claim_id || '').toLowerCase().includes(q) ||
        (entry.comment || '').toLowerCase().includes(q) ||
        (entry.reviewer_id || '').toLowerCase().includes(q) ||
        (entry.override_verdict || '').toLowerCase().includes(q);
      return matchesAction && matchesSearch;
    });
  }, [auditEntries, actionFilter, searchQuery]);

  return (
    <div style={{ padding: '40px 0 80px' }}>
      <div className="container">
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', marginBottom: '28px' }}>
          <div>
            <h1 style={{ fontSize: '32px', marginBottom: '6px' }}>Human Review Audit Ledger</h1>
            <p style={{ fontSize: '14px' }}>
              Append-only, immutable record of expert review actions, verdict overrides, and academic commentary.
            </p>
          </div>
          <button onClick={fetchAudit} className="btn btn-secondary btn-sm" title="Refresh audit ledger from SQLite">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
            </svg>
            Refresh Ledger
          </button>
        </div>

        {/* Tally Metrics */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '18px',
          marginBottom: '28px'
        }} className="summary-strip">
          <div className="panel" style={{ padding: '16px 20px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '4px' }}>
              Total Logged Actions
            </div>
            <div style={{ fontSize: '24px', fontWeight: '700', color: 'var(--text-primary)', fontFamily: 'var(--font-serif)' }}>
              {counts.total}
            </div>
          </div>

          <div className="panel" style={{ padding: '16px 20px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '4px' }}>
              Verdict Overrides
            </div>
            <div style={{ fontSize: '24px', fontWeight: '700', color: 'var(--partial-color)', fontFamily: 'var(--font-serif)' }}>
              {counts.override}
            </div>
          </div>

          <div className="panel" style={{ padding: '16px 20px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '4px' }}>
              Accepted Triage Decisions
            </div>
            <div style={{ fontSize: '24px', fontWeight: '700', color: 'var(--supported-color)', fontFamily: 'var(--font-serif)' }}>
              {counts.accept}
            </div>
          </div>

          <div className="panel" style={{ padding: '16px 20px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '4px' }}>
              Reviewer Annotations
            </div>
            <div style={{ fontSize: '24px', fontWeight: '700', color: 'var(--needs-review-color)', fontFamily: 'var(--font-serif)' }}>
              {counts.comment}
            </div>
          </div>
        </div>

        {/* Search & Action Filters */}
        <div className="panel" style={{ padding: '14px 18px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
            {/* Action Filter Pills */}
            <div style={{ display: 'flex', gap: '6px' }}>
              {[
                { id: 'all', label: `All Actions (${counts.total})` },
                { id: 'override', label: `Overrides (${counts.override})` },
                { id: 'accept', label: `Accepts (${counts.accept})` },
                { id: 'comment', label: `Comments (${counts.comment})` },
              ].map(tab => {
                const active = actionFilter === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActionFilter(tab.id)}
                    style={{
                      background: active ? 'var(--bg-surface-elevated)' : 'transparent',
                      color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                      border: active ? '1px solid var(--border-line)' : '1px solid transparent',
                      padding: '6px 12px',
                      borderRadius: '6px',
                      fontSize: '12px',
                      fontWeight: active ? '600' : '500',
                      cursor: 'pointer'
                    }}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* Keyword Search */}
            <div style={{ minWidth: '240px' }}>
              <input
                type="text"
                placeholder="Search reviewer, claim, or notes..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  padding: '7px 12px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-line)',
                  background: 'var(--bg-surface-elevated)',
                  color: 'var(--text-primary)',
                  fontSize: '12.5px',
                  outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
            </div>
          </div>
        </div>

        {/* Ledger Timeline List */}
        <div className="panel" style={{ overflow: 'hidden' }}>
          {loading ? (
            <div style={{ padding: '48px 0', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <div style={{
                width: '36px',
                height: '36px',
                margin: '0 auto 14px',
                borderRadius: '50%',
                border: '3px solid var(--border-line)',
                borderTopColor: 'var(--accent-orange)'
              }} className="spinner-glow" />
              Loading audit trail...
            </div>
          ) : filteredEntries.length === 0 ? (
            <div style={{ padding: '56px 20px', textAlign: 'center' }}>
              <div style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '6px' }}>
                No Review Actions Recorded
              </div>
              <div style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '420px', margin: '0 auto 16px' }}>
                Human triage actions submitted in the Report Workbench will appear here in chronological order.
              </div>
              <button onClick={onNavigateReport} className="btn btn-secondary btn-sm">
                Go to Report Workbench
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {filteredEntries.map((entry, idx) => {
                const action = (entry.action || 'comment').toLowerCase();
                const badgeClass =
                  action === 'accept'
                    ? 'audit-badge-accept'
                    : action === 'override'
                    ? 'audit-badge-override'
                    : 'audit-badge-comment';

                const ts = entry.timestamp ? new Date(entry.timestamp).toLocaleString() : 'Recent action';

                return (
                  <div
                    key={entry.id || idx}
                    style={{
                      padding: '18px 22px',
                      borderBottom: idx < filteredEntries.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                      background: idx % 2 === 0 ? 'transparent' : 'var(--bg-surface-subtle)'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span className={badgeClass}>{entry.action}</span>
                        <span style={{ fontWeight: '600', color: 'var(--text-primary)', fontSize: '13px' }}>
                          Claim: <code>{entry.claim_id}</code>
                        </span>
                        {entry.override_verdict && (
                          <span style={{ fontSize: '12px', color: 'var(--partial-color)', fontWeight: '600' }}>
                            Overridden to: <strong>{entry.override_verdict}</strong>
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '11.5px', color: 'var(--text-tertiary)' }}>
                        Reviewer: <strong>{entry.reviewer_id || 'reviewer-1'}</strong> • {ts}
                      </div>
                    </div>

                    {(entry.comment || entry.explanation) && (
                      <div style={{
                        fontSize: '13px',
                        color: 'var(--text-secondary)',
                        fontStyle: 'italic',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        background: 'var(--bg-surface-elevated)',
                        border: '1px solid var(--border-line)',
                        lineHeight: 1.5
                      }}>
                        "{entry.comment || entry.explanation}"
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
