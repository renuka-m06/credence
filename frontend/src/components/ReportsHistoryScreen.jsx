import React, { useState, useEffect, useMemo } from 'react';
import { apiUrl, getAuthHeaders } from '../api';

export default function ReportsHistoryScreen({ onSelectReport, onNavigateUpload }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterTier, setFilterTier] = useState('all');
  const [sortBy, setSortBy] = useState('newest');

  useEffect(() => {
    fetch(apiUrl('/reports?limit=50'), { headers: getAuthHeaders() })
      .then(res => res.json())
      .then(data => {
        if (data?.reports && Array.isArray(data.reports)) {
          setReports(data.reports);
        }
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  // Compute activity overview KPIs
  const kpis = useMemo(() => {
    const totalManuscripts = reports.length;
    let totalClaims = 0;
    let totalOverrides = 0;
    let totalConf = 0;

    reports.forEach(r => {
      const claims = r.claims || [];
      totalClaims += claims.length;
      totalConf += (r.overall_confidence || 0);
      claims.forEach(c => {
        if (c.verdict?.override_info || (c.reviews && c.reviews.some(rev => rev.action === 'override'))) {
          totalOverrides++;
        }
      });
    });

    const avgConfidence = totalManuscripts > 0 ? (totalConf / totalManuscripts) * 100 : 0;
    return {
      totalManuscripts,
      totalClaims,
      totalOverrides,
      avgConfidence: avgConfidence.toFixed(1) + '%',
    };
  }, [reports]);

  // Filtered and sorted reports
  const displayReports = useMemo(() => {
    return reports
      .filter(r => {
        const name = (r.document_name || r.id || '').toLowerCase();
        const matchesSearch = name.includes(searchQuery.toLowerCase());
        const matchesTier = filterTier === 'all' ? true : (r.access_tier || '').toLowerCase() === filterTier;
        return matchesSearch && matchesTier;
      })
      .sort((a, b) => {
        if (sortBy === 'newest') {
          return new Date(b.created_at || 0) - new Date(a.created_at || 0);
        }
        if (sortBy === 'confidence') {
          return (b.overall_confidence || 0) - (a.overall_confidence || 0);
        }
        if (sortBy === 'claims') {
          return (b.claims?.length || 0) - (a.claims?.length || 0);
        }
        return 0;
      });
  }, [reports, searchQuery, filterTier, sortBy]);

  return (
    <div style={{ padding: '40px 0 80px' }}>
      <div className="container">
        {/* Header & Activity KPIs */}
        <div style={{ marginBottom: '36px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', marginBottom: '24px' }}>
            <div>
              <h1 style={{ fontSize: '32px', marginBottom: '6px' }}>Research Dossiers & Archive</h1>
              <p style={{ fontSize: '14px' }}>
                Chronological ledger of verified academic manuscripts, empirical extractions, and triage audits.
              </p>
            </div>
            <button onClick={onNavigateUpload} className="btn btn-primary">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19"/>
                <line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              Verify New Manuscript
            </button>
          </div>

          {/* Activity Metrics Strip */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '18px',
          }} className="summary-strip">
            <div className="panel" style={{ padding: '18px 20px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>
                Ingested Manuscripts
              </div>
              <div style={{ fontSize: '26px', fontWeight: '700', color: 'var(--text-primary)', fontFamily: 'var(--font-serif)' }}>
                {kpis.totalManuscripts}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                Stored in durable SQLite/Postgres
              </div>
            </div>

            <div className="panel" style={{ padding: '18px 20px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>
                Empirical Claims Verified
              </div>
              <div style={{ fontSize: '26px', fontWeight: '700', color: 'var(--accent-orange)', fontFamily: 'var(--font-serif)' }}>
                {kpis.totalClaims}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                Atomized into factual slots
              </div>
            </div>

            <div className="panel" style={{ padding: '18px 20px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>
                Human Overrides Recorded
              </div>
              <div style={{ fontSize: '26px', fontWeight: '700', color: 'var(--partial-color)', fontFamily: 'var(--font-serif)' }}>
                {kpis.totalOverrides}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                In append-only review ledger
              </div>
            </div>

            <div className="panel" style={{ padding: '18px 20px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>
                Average Epistemic Confidence
              </div>
              <div style={{ fontSize: '26px', fontWeight: '700', color: 'var(--supported-color)', fontFamily: 'var(--font-serif)' }}>
                {kpis.avgConfidence}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                Access-tier mathematical cap
              </div>
            </div>
          </div>
        </div>

        {/* Filter and Search Controls */}
        <div className="panel" style={{ padding: '16px 20px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
            {/* Search Input */}
            <div style={{ position: 'relative', minWidth: '280px', flex: 1 }}>
              <input
                type="text"
                placeholder="Search by manuscript title, filename or ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 14px 9px 36px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-line)',
                  background: 'var(--bg-surface-elevated)',
                  color: 'var(--text-primary)',
                  fontSize: '13px',
                  outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--text-tertiary)"
                strokeWidth="2"
                style={{ position: 'absolute', left: '12px', top: '11px' }}
              >
                <circle cx="11" cy="11" r="8"/>
                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
            </div>

            {/* Filter by Tier */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Access Tier:</span>
              <select
                value={filterTier}
                onChange={(e) => setFilterTier(e.target.value)}
                style={{
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-line)',
                  background: 'var(--bg-surface-elevated)',
                  color: 'var(--text-primary)',
                  fontSize: '12.5px',
                  outline: 'none'
                }}
              >
                <option value="all">All Access Tiers</option>
                <option value="full_text">Full Text (Cap: 0.90)</option>
                <option value="abstract_only">Abstract Only (Cap: 0.60)</option>
                <option value="metadata_only">Metadata Only (Cap: 0.20)</option>
                <option value="inaccessible">Inaccessible</option>
              </select>
            </div>

            {/* Sorting */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Sort By:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                style={{
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-line)',
                  background: 'var(--bg-surface-elevated)',
                  color: 'var(--text-primary)',
                  fontSize: '12.5px',
                  outline: 'none'
                }}
              >
                <option value="newest">Newest First</option>
                <option value="confidence">Highest Confidence</option>
                <option value="claims">Most Claims</option>
              </select>
            </div>
          </div>
        </div>

        {/* Reports Listing Table */}
        <div className="panel" style={{ overflow: 'hidden' }}>
          {loading ? (
            <div style={{ padding: '60px 0', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <div style={{
                width: '40px',
                height: '40px',
                margin: '0 auto 16px',
                borderRadius: '50%',
                border: '3px solid var(--border-line)',
                borderTopColor: 'var(--accent-orange)'
              }} className="spinner-glow" />
              Loading research dossiers...
            </div>
          ) : displayReports.length === 0 ? (
            /* Clean Empty State */
            <div style={{ padding: '64px 24px', textAlign: 'center' }}>
              <div style={{
                width: '56px',
                height: '56px',
                borderRadius: '14px',
                background: 'var(--bg-surface-elevated)',
                color: 'var(--text-tertiary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px'
              }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
              </div>
              <h3 style={{ fontSize: '18px', marginBottom: '8px' }}>No Dossiers Match Your Filter</h3>
              <p style={{ fontSize: '13px', maxWidth: '420px', margin: '0 auto 20px' }}>
                {searchQuery ? `No reports matched "${searchQuery}". Try a different search keyword.` : 'No verification dossiers have been archived yet.'}
              </p>
              <button onClick={onNavigateUpload} className="btn btn-secondary btn-sm">
                Upload a Manuscript
              </button>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Manuscript Document</th>
                    <th>Claims</th>
                    <th>Access Tier</th>
                    <th>Epistemic Confidence</th>
                    <th>Summary Tally</th>
                    <th style={{ textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {displayReports.map((rep) => {
                    const claims = rep.claims || [];
                    const supp = rep.summary?.supported ?? claims.filter(c => (c.verdict?.verdict || '').includes('support') && !(c.verdict?.verdict || '').includes('part')).length;
                    const needsRev = rep.summary?.needs_review ?? claims.filter(c => c.verdict?.needs_review).length;
                    const contra = rep.summary?.contradictory ?? claims.filter(c => (c.verdict?.verdict || '').includes('contradict')).length;
                    const confPct = ((rep.overall_confidence || 0) * 100).toFixed(0);

                    return (
                      <tr key={rep.id}>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <div style={{
                              width: '32px',
                              height: '32px',
                              borderRadius: '7px',
                              background: 'var(--bg-surface-elevated)',
                              border: '1px solid var(--border-line)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: 'var(--accent-orange)',
                              flexShrink: 0
                            }}>
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                                <polyline points="14 2 14 8 20 8"/>
                              </svg>
                            </div>
                            <div>
                              <div style={{ fontWeight: '600', color: 'var(--text-primary)', fontSize: '13.5px' }}>
                                {rep.document_name || 'unnamed_manuscript.pdf'}
                              </div>
                              <div style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                                ID: {rep.id?.slice(0, 16)}... • {rep.created_at ? new Date(rep.created_at).toLocaleDateString() : 'Active session'}
                              </div>
                            </div>
                          </div>
                        </td>

                        <td>
                          <span style={{ fontWeight: '600', fontSize: '13px' }}>{claims.length}</span>
                          <span style={{ fontSize: '11.5px', color: 'var(--text-secondary)', marginLeft: '4px' }}>claims</span>
                        </td>

                        <td>
                          <span style={{
                            fontSize: '11px',
                            fontWeight: '600',
                            textTransform: 'uppercase',
                            padding: '3px 8px',
                            borderRadius: '5px',
                            background: 'var(--bg-surface-elevated)',
                            border: '1px solid var(--border-line)',
                            color: 'var(--text-secondary)'
                          }}>
                            {rep.access_tier || 'full_text'}
                          </span>
                        </td>

                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{
                              fontSize: '13px',
                              fontWeight: '700',
                              color: Number(confPct) >= 70 ? 'var(--supported-color)' : (Number(confPct) >= 40 ? 'var(--partial-color)' : 'var(--unsupported-color)')
                            }}>
                              {confPct}%
                            </span>
                            <div style={{
                              width: '48px',
                              height: '4px',
                              background: 'var(--bg-surface-elevated)',
                              borderRadius: '2px',
                              overflow: 'hidden'
                            }}>
                              <div style={{
                                width: `${confPct}%`,
                                height: '100%',
                                background: Number(confPct) >= 70 ? 'var(--supported-color)' : (Number(confPct) >= 40 ? 'var(--partial-color)' : 'var(--unsupported-color)'),
                                borderRadius: '2px'
                              }} />
                            </div>
                          </div>
                        </td>

                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            {supp > 0 && (
                              <span className="verdict-badge verdict-supported" style={{ padding: '2px 6px', fontSize: '10.5px' }}>
                                {supp} Supp
                              </span>
                            )}
                            {needsRev > 0 && (
                              <span className="verdict-badge verdict-needs-review" style={{ padding: '2px 6px', fontSize: '10.5px' }}>
                                {needsRev} Review
                              </span>
                            )}
                            {contra > 0 && (
                              <span className="verdict-badge verdict-contradictory" style={{ padding: '2px 6px', fontSize: '10.5px' }}>
                                {contra} Contra
                              </span>
                            )}
                          </div>
                        </td>

                        <td style={{ textAlign: 'right' }}>
                          <button
                            onClick={() => onSelectReport(rep)}
                            className="btn btn-secondary btn-sm"
                          >
                            Inspect Dossier
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="9 18 15 12 9 6"/>
                            </svg>
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
