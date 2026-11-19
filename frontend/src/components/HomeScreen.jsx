import React, { useState } from 'react';

export default function HomeScreen({ onSelectDemo, onUploadFile, loading }) {
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

          {/* Upload / Demo Action Box */}
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

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px' }}>
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
                {loading ? 'Analyzing...' : 'Run Demo Paper (sample_paper.pdf)'}
              </button>
            </div>
          </div>
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
