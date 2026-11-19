import React, { useState } from 'react';

export default function HomeScreen({
  onSelectDemo,
  onUploadFile,
  loading,
  loadingProgress,
  errorMessage,
  onClearError,
  onForceError,
  demoMode
}) {
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onUploadFile(e.dataTransfer.files[0]);
    }
  };

  return (
    <div style={{ padding: '60px 0 80px' }}>
      <div className="container">
        {/* HERO SECTION */}
        <div style={{ textAlign: 'center', maxWidth: '820px', margin: '0 auto 60px' }}>
          {/* Seal Badge */}
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginBottom: '22px' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              background: 'rgba(240, 106, 44, 0.12)',
              border: '1px solid rgba(240, 106, 44, 0.3)',
              color: 'var(--orange2)',
              padding: '6px 14px',
              borderRadius: '24px',
              fontSize: '12px',
              fontWeight: '600',
              letterSpacing: '0.04em',
              textTransform: 'uppercase'
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
              Scientific Citation Verifier
            </span>
          </div>

          {/* Serif Headline (Spectral) */}
          <h1 style={{
            fontSize: '52px',
            lineHeight: 1.15,
            marginBottom: '20px',
            fontWeight: 600,
            color: '#fff',
          }}>
            Every Scientific Verdict <br />
            <span style={{
              background: 'linear-gradient(135deg, #fff 30%, var(--orange2) 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}>
              Carries Deterministic Proof.
            </span>
          </h1>

          <p style={{
            fontSize: '17px',
            color: 'var(--muted)',
            lineHeight: 1.6,
            maxWidth: '680px',
            margin: '0 auto 36px'
          }}>
            Upload a PDF/DOCX manuscript to extract empirical claims and citations. 
            Credence retrieves cited evidence across academic databases and verifies whether 
            the source backs each assertion with verbatim proof.
          </p>

          {/* Decorative Wave Divider */}
          <div style={{ display: 'flex', justifyContent: 'center', margin: '0 auto 40px' }}>
            <svg width="180" height="16" viewBox="0 0 180 16" fill="none">
              <path d="M0 8 Q 45 16, 90 8 T 180 8" stroke="rgba(240, 106, 44, 0.4)" strokeWidth="2" fill="none" />
            </svg>
          </div>

          {/* Friendly Error State Banner (Never Crashes) */}
          {errorMessage && (
            <div style={{
              background: 'rgba(239, 107, 107, 0.08)',
              border: '1px solid rgba(239, 107, 107, 0.35)',
              borderRadius: '12px',
              padding: '18px 24px',
              maxWidth: '620px',
              margin: '0 auto 28px',
              textAlign: 'left',
              display: 'flex',
              gap: '14px',
              alignItems: 'flex-start',
              boxShadow: '0 4px 20px rgba(239, 107, 107, 0.12)'
            }}>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'rgba(239, 107, 107, 0.15)',
                color: 'var(--unsupported-color)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="12"/>
                  <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: '700', fontSize: '14px', color: '#fff', marginBottom: '4px' }}>
                  Document Verification Notice
                </div>
                <p style={{ fontSize: '13px', color: 'var(--ink)', margin: '0 0 14px', lineHeight: 1.5 }}>
                  {errorMessage}
                </p>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                  <button
                    className="btn btn-secondary"
                    onClick={onClearError}
                    style={{ fontSize: '11px', padding: '5px 12px' }}
                  >
                    Dismiss
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={onSelectDemo}
                    style={{ fontSize: '11px', padding: '5px 14px' }}
                  >
                    Run Demo Paper (sample_paper.pdf)
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Upload / Demo Action Box */}
          {loading ? (
            <div style={{
              background: 'var(--panel)',
              border: '2px solid rgba(240, 106, 44, 0.4)',
              borderRadius: '16px',
              padding: '44px 24px',
              maxWidth: '600px',
              margin: '0 auto',
              boxShadow: '0 8px 32px rgba(240, 106, 44, 0.18)',
              textAlign: 'center'
            }}>
              <div
                className="spinner-glow"
                style={{
                  width: '44px',
                  height: '44px',
                  border: '3px solid rgba(240, 106, 44, 0.2)',
                  borderTop: '3px solid var(--orange2)',
                  borderRadius: '50%',
                  margin: '0 auto 20px',
                }}
              />
              <h3 style={{ fontSize: '18px', color: '#fff', marginBottom: '8px' }}>
                Analyzing Academic Manuscript
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--orange2)', fontWeight: '600', marginBottom: '18px' }}>
                {loadingProgress || 'Extracting empirical claims and atomizing into slots...'}
              </p>
              <div style={{
                width: '85%',
                height: '6px',
                background: 'rgba(255,255,255,0.06)',
                borderRadius: '3px',
                margin: '0 auto 16px',
                overflow: 'hidden'
              }}>
                <div className="progress-bar-animated" style={{
                  width: '100%',
                  height: '100%',
                  background: 'linear-gradient(90deg, var(--orange), var(--orange2))',
                }} />
              </div>
              <span style={{ fontSize: '11px', color: 'var(--faint)' }}>
                Deterministic verification active · Golden rule: code confirms quotes before granting proof
              </span>
            </div>
          ) : (
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              style={{
                background: dragOver ? 'rgba(240, 106, 44, 0.08)' : 'var(--panel)',
                border: `2px dashed ${dragOver ? 'var(--orange)' : 'var(--line)'}`,
                borderRadius: '16px',
                padding: '40px 24px',
                maxWidth: '600px',
                margin: '0 auto',
                transition: 'all 0.2s ease',
                boxShadow: '0 8px 32px rgba(0,0,0,0.4)'
              }}
            >
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: 'rgba(255, 255, 255, 0.05)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px',
                color: 'var(--orange)'
              }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
              </div>

              <p style={{ fontWeight: '600', fontSize: '15px', color: '#fff', marginBottom: '6px' }}>
                Drop your PDF or DOCX manuscript here
              </p>
              <p style={{ fontSize: '12px', color: 'var(--faint)', marginBottom: '20px' }}>
                Supports academic research papers, clinical reports, and grant proposals
              </p>

              {demoMode && (
                <div style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: 'rgba(95, 207, 106, 0.1)',
                  color: 'var(--supported-color)',
                  border: '1px solid rgba(95, 207, 106, 0.3)',
                  padding: '3px 10px',
                  borderRadius: '20px',
                  fontSize: '11px',
                  fontWeight: '600',
                  marginBottom: '16px'
                }}>
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--supported-color)' }} />
                  Demo Mode Active: Serving pre-cached results from data/demo/ (0 live API calls)
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', flexWrap: 'wrap' }}>
                <label className="btn btn-secondary" style={{ cursor: 'pointer' }}>
                  <input
                    type="file"
                    accept=".pdf,.docx,.doc"
                    style={{ display: 'none' }}
                    onChange={(e) => e.target.files && onUploadFile(e.target.files[0])}
                  />
                  Browse File
                </label>

                <button
                  className="btn btn-primary"
                  onClick={onSelectDemo}
                  disabled={loading}
                >
                  Run Demo Paper (sample_paper.pdf)
                </button>
              </div>

              <div style={{ marginTop: '16px', borderTop: '1px solid var(--line)', paddingTop: '12px' }}>
                <button
                  onClick={onForceError}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--faint)',
                    fontSize: '11px',
                    cursor: 'pointer',
                    textDecoration: 'underline'
                  }}
                  title="Simulate a gateway error to test graceful error handling"
                >
                  ⚡ Simulate Verification API Error
                </button>
              </div>
            </div>
          )}
        </div>

        {/* 3 FEATURE CARDS */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '24px',
          marginBottom: '70px'
        }}>
          {/* Card 1 */}
          <div style={{
            background: 'var(--panel)',
            border: '1px solid var(--line)',
            borderRadius: '14px',
            padding: '28px',
            position: 'relative',
            overflow: 'hidden'
          }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              background: 'rgba(95, 207, 106, 0.1)',
              color: 'var(--supported-color)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '18px'
            }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
            </div>
            <h3 style={{ fontSize: '18px', marginBottom: '10px', color: '#fff' }}>Verbatim Proof Only</h3>
            <p style={{ fontSize: '13px', color: 'var(--muted)', lineHeight: 1.6 }}>
              LLM hallucinations are caught and rejected. Python code verifies that candidate quotes exist 
              normalized in the original publication before granting evidence status.
            </p>
          </div>

          {/* Card 2 */}
          <div style={{
            background: 'var(--panel)',
            border: '1px solid var(--line)',
            borderRadius: '14px',
            padding: '28px'
          }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              background: 'rgba(240, 106, 44, 0.1)',
              color: 'var(--orange)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '18px'
            }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 6 12 12 16 14"/>
              </svg>
            </div>
            <h3 style={{ fontSize: '18px', marginBottom: '10px', color: '#fff' }}>Computed Confidence</h3>
            <p style={{ fontSize: '13px', color: 'var(--muted)', lineHeight: 1.6 }}>
              Confidence is calculated deterministically from access-tier ceilings (Full text 0.9, Abstract 0.6) 
              minus unverified slots and pass disagreement. Never model self-reported numbers.
            </p>
          </div>

          {/* Card 3 */}
          <div style={{
            background: 'var(--panel)',
            border: '1px solid var(--line)',
            borderRadius: '14px',
            padding: '28px'
          }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              background: 'rgba(90, 169, 240, 0.1)',
              color: 'var(--needs-review-color)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '18px'
            }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                <circle cx="9" cy="7" r="4"/>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
              </svg>
            </div>
            <h3 style={{ fontSize: '18px', marginBottom: '10px', color: '#fff' }}>Human Review Triage</h3>
            <p style={{ fontSize: '13px', color: 'var(--muted)', lineHeight: 1.6 }}>
              Never presents silent auto-decisions. Results serve as an academic triage aid where reviewers 
              can accept, override, or annotate every fact-check decision.
            </p>
          </div>
        </div>

        {/* TRUST STRIP */}
        <div style={{
          borderTop: '1px solid var(--line)',
          paddingTop: '36px',
          textAlign: 'center'
        }}>
          <p style={{
            fontSize: '11px',
            fontWeight: '600',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--faint)',
            marginBottom: '18px'
          }}>
            Cross-Database Evidence Retrieval & Transparent Search Accounting
          </p>
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '32px',
            color: 'var(--muted)',
            fontSize: '13px',
            fontWeight: '600'
          }}>
            <span>Crossref</span>
            <span>·</span>
            <span>OpenAlex</span>
            <span>·</span>
            <span>Semantic Scholar</span>
            <span>·</span>
            <span>Unpaywall</span>
            <span>·</span>
            <span>arXiv</span>
            <span>·</span>
            <span>PubMed Central</span>
          </div>
        </div>
      </div>
    </div>
  );
}
