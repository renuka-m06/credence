import React, { useState } from 'react';

export default function SettingsScreen({
  theme,
  onToggleTheme,
  demoMode,
  onToggleDemoMode,
}) {
  const [reviewerId, setReviewerId] = useState(() => {
    return (typeof window !== 'undefined' && localStorage.getItem('credence_reviewer_id')) || 'reviewer-1';
  });
  const [affiliation, setAffiliation] = useState(() => {
    return (typeof window !== 'undefined' && localStorage.getItem('credence_affiliation')) || 'Institute of Empirical Science';
  });
  const [savedFeedback, setSavedFeedback] = useState(false);

  const handleSaveProfile = (e) => {
    e.preventDefault();
    if (typeof window !== 'undefined') {
      localStorage.setItem('credence_reviewer_id', reviewerId);
      localStorage.setItem('credence_affiliation', affiliation);
    }
    setSavedFeedback(true);
    setTimeout(() => setSavedFeedback(false), 2500);
  };

  return (
    <div style={{ padding: '40px 0 80px' }}>
      <div className="container" style={{ maxWidth: '860px' }}>
        {/* Header */}
        <div style={{ marginBottom: '32px' }}>
          <h1 style={{ fontSize: '32px', marginBottom: '6px' }}>Platform Preferences & Configuration</h1>
          <p style={{ fontSize: '14px' }}>
            Configure theme aesthetics, reviewer identity, retrieval gateway connections, and epistemic confidence ceilings.
          </p>
        </div>

        {savedFeedback && (
          <div style={{
            background: 'var(--supported-bg)',
            border: '1px solid var(--supported-border)',
            borderRadius: '8px',
            padding: '12px 16px',
            marginBottom: '24px',
            color: 'var(--supported-color)',
            fontSize: '13px',
            fontWeight: '600'
          }}>
            ✓ Profile preferences saved successfully.
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Section 1: Appearance & Theme */}
          <div className="panel" style={{ padding: '24px 28px' }}>
            <h3 style={{ fontSize: '17px', marginBottom: '8px' }}>Appearance & Interface Theme</h3>
            <p style={{ fontSize: '13px', marginBottom: '20px' }}>
              Choose your preferred visual presentation. Both themes share identical structure, contrast calibration, and typography.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div
                onClick={() => theme === 'light' && onToggleTheme()}
                style={{
                  padding: '16px 20px',
                  borderRadius: '10px',
                  border: theme === 'dark' ? '2px solid var(--accent-orange)' : '1px solid var(--border-line)',
                  background: 'var(--bg-surface-elevated)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  boxShadow: 'var(--shadow-sm)'
                }}
              >
                <div style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '7px',
                  background: '#0c0d11',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff'
                }}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="4"/>
                    <path d="M12 2v2"/><path d="M12 20v2"/>
                  </svg>
                </div>
                <div>
                  <div style={{ fontWeight: '600', color: 'var(--text-primary)', fontSize: '13.5px' }}>
                    Dark Mode (Obsidian)
                  </div>
                  <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)' }}>
                    Deep charcoal with ambient orange glow
                  </div>
                </div>
              </div>

              <div
                onClick={() => theme === 'dark' && onToggleTheme()}
                style={{
                  padding: '16px 20px',
                  borderRadius: '10px',
                  border: theme === 'light' ? '2px solid var(--accent-orange)' : '1px solid var(--border-line)',
                  background: 'var(--bg-surface-elevated)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  boxShadow: 'var(--shadow-sm)'
                }}
              >
                <div style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '7px',
                  background: '#f9f9f6',
                  border: '1px solid rgba(0, 0, 0, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#12141a'
                }}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>
                  </svg>
                </div>
                <div>
                  <div style={{ fontWeight: '600', color: 'var(--text-primary)', fontSize: '13.5px' }}>
                    Light Mode (Archival Paper)
                  </div>
                  <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)' }}>
                    Warm cream and clean editorial surfaces
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Section 2: Execution Mode */}
          <div className="panel" style={{ padding: '24px 28px' }}>
            <h3 style={{ fontSize: '17px', marginBottom: '8px' }}>Pipeline Execution Mode</h3>
            <p style={{ fontSize: '13px', marginBottom: '20px' }}>
              Control whether manuscript verification runs fully offline using local pre-cached evaluation data or queries live external APIs.
            </p>

            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '16px 20px',
              borderRadius: '10px',
              background: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-line)'
            }}>
              <div>
                <div style={{ fontWeight: '600', color: 'var(--text-primary)', fontSize: '13.5px' }}>
                  {demoMode ? 'Offline Demo Mode Active' : 'Live Gateway Mode Active'}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  {demoMode
                    ? 'Manuscript uploads use verified data from data/demo with zero external network dependencies.'
                    : 'Real-time HTTP retrieval active across Crossref, OpenAlex, Semantic Scholar, and Unpaywall.'}
                </div>
              </div>

              <button
                onClick={onToggleDemoMode}
                className={demoMode ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm'}
              >
                {demoMode ? 'Switch to Live Gateway' : 'Switch to Offline Demo'}
              </button>
            </div>
          </div>

          {/* Section 3: Reviewer Identity */}
          <div className="panel" style={{ padding: '24px 28px' }}>
            <h3 style={{ fontSize: '17px', marginBottom: '8px' }}>Reviewer Identity & Ledger Profile</h3>
            <p style={{ fontSize: '13px', marginBottom: '20px' }}>
              This identifier is stamped on all append-only review actions, overrides, and audit logs recorded in SQLite.
            </p>

            <form onSubmit={handleSaveProfile} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                    Reviewer Handle / ID
                  </label>
                  <input
                    type="text"
                    value={reviewerId}
                    onChange={(e) => setReviewerId(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '9px 12px',
                      borderRadius: '7px',
                      border: '1px solid var(--border-line)',
                      background: 'var(--bg-surface-elevated)',
                      color: 'var(--text-primary)',
                      fontSize: '13px',
                      outline: 'none',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                    Academic / Research Affiliation
                  </label>
                  <input
                    type="text"
                    value={affiliation}
                    onChange={(e) => setAffiliation(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '9px 12px',
                      borderRadius: '7px',
                      border: '1px solid var(--border-line)',
                      background: 'var(--bg-surface-elevated)',
                      color: 'var(--text-primary)',
                      fontSize: '13px',
                      outline: 'none',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>
              </div>

              <div>
                <button type="submit" className="btn btn-secondary btn-sm">
                  Save Reviewer Profile
                </button>
              </div>
            </form>
          </div>

          {/* Section 4: Epistemic Ceilings & Calibration Rules */}
          <div className="panel" style={{ padding: '24px 28px' }}>
            <h3 style={{ fontSize: '17px', marginBottom: '8px' }}>Epistemic Confidence Ceilings (Golden Rule 3)</h3>
            <p style={{ fontSize: '13px', marginBottom: '16px' }}>
              Mathematical parameters enforced deterministically by <code>credence/verify/verdict.py</code>:
            </p>

            <table className="data-table">
              <thead>
                <tr>
                  <th>Access Tier</th>
                  <th>Maximum Ceiling</th>
                  <th>Deterministic Deductions</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>Full Text</strong></td>
                  <td><code>0.90</code></td>
                  <td>-0.15 per unverified slot, -0.20 on pass disagreement</td>
                </tr>
                <tr>
                  <td><strong>Abstract Only</strong></td>
                  <td><code>0.60</code></td>
                  <td>-0.15 per unverified slot, -0.20 on pass disagreement</td>
                </tr>
                <tr>
                  <td><strong>Metadata Only</strong></td>
                  <td><code>0.20</code></td>
                  <td>-0.15 per unverified slot</td>
                </tr>
                <tr>
                  <td><strong>Inaccessible / Not Found</strong></td>
                  <td><code>0.00</code></td>
                  <td>Automatically triaged to "Needs review"</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
