import React, { useState, useEffect, useRef } from 'react';

export default function HomeScreen({
  onSelectDemo,
  onUploadFile,
  loading,
  loadingProgress,
  errorMessage,
  onClearError,
  onForceError,
  demoMode,
}) {
  const [dragOver, setDragOver] = useState(false);
  const [heroImageSrc, setHeroImageSrc] = useState(null);
  const [imageChecked, setImageChecked] = useState(false);
  const fileInputRef = useRef(null);
  const heroImageInputRef = useRef(null);

  // Probe public/assets for the user-supplied photograph
  useEffect(() => {
    const candidatePaths = [
      '/assets/hero-research.jpg',
      '/assets/hero-research.png',
      '/assets/research-book.jpg',
      '/assets/research-book.png',
      '/assets/hero.jpg',
      '/assets/hero.png',
    ];

    let found = false;
    let idx = 0;

    const testNext = () => {
      if (idx >= candidatePaths.length) {
        setImageChecked(true);
        return;
      }
      const img = new Image();
      const currentPath = candidatePaths[idx];
      img.onload = () => {
        if (!found) {
          found = true;
          setHeroImageSrc(currentPath);
          setImageChecked(true);
        }
      };
      img.onerror = () => {
        idx++;
        testNext();
      };
      img.src = currentPath;
    };

    testNext();
  }, []);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onUploadFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      onUploadFile(e.target.files[0]);
    }
  };

  const handleManualHeroImagePick = (e) => {
    if (e.target.files && e.target.files[0]) {
      const url = URL.createObjectURL(e.target.files[0]);
      setHeroImageSrc(url);
    }
  };

  const scrollToUpload = () => {
    const el = document.getElementById('manuscript-upload-section');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div style={{ padding: '48px 0 96px' }}>
      <div className="container">
        {/* ==================================================================
            1. SPLIT-SCREEN HERO SECTION
            ================================================================== */}
        <section style={{ marginBottom: '80px' }}>
          <div className="split-hero-grid">
            {/* Left Column: Heading, Value Proposition & Actions */}
            <div>
              {/* Scholarly Badge */}
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
                <span style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '7px',
                  background: 'var(--accent-orange-subtle)',
                  border: '1px solid var(--accent-orange-border)',
                  color: 'var(--accent-orange)',
                  padding: '5px 14px',
                  borderRadius: '24px',
                  fontSize: '11.5px',
                  fontWeight: '700',
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase'
                }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                  </svg>
                  Epistemic Verification Engine
                </span>
              </div>

              {/* Main Headline (Spectral Serif) */}
              <h1 style={{
                fontSize: '46px',
                lineHeight: 1.15,
                marginBottom: '20px',
                fontWeight: 600,
                color: 'var(--text-primary)',
              }}>
                Scientific Claims Demand <br />
                <span style={{
                  background: 'linear-gradient(135deg, var(--text-primary) 30%, var(--accent-orange) 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }}>
                  Deterministic Proof.
                </span>
              </h1>

              {/* Description */}
              <p style={{
                fontSize: '16px',
                color: 'var(--text-secondary)',
                lineHeight: 1.65,
                marginBottom: '32px',
                maxWidth: '580px'
              }}>
                Academic manuscripts frequently cite literature out of context, strip hedges, or rely on outdated findings. 
                Credence retrieves the cited source paper and verifies whether the text genuinely backs each empirical assertion with 
                verbatim proof.
              </p>

              {/* Action Buttons */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap', marginBottom: '40px' }}>
                <button
                  onClick={scrollToUpload}
                  className="btn btn-primary btn-lg"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>
                  Verify Manuscript
                </button>

                <button
                  onClick={onSelectDemo}
                  className="btn btn-secondary btn-lg"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"/>
                    <polygon points="10 8 16 12 10 16 10 8"/>
                  </svg>
                  Explore Worked Demo
                </button>
              </div>

              {/* Trust & Proof Strip */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: '16px',
                paddingTop: '24px',
                borderTop: '1px solid var(--border-line)',
              }}>
                <div>
                  <div style={{ fontSize: '20px', fontWeight: '700', color: 'var(--text-primary)', fontFamily: 'var(--font-serif)' }}>100%</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Quotes Proven</div>
                </div>
                <div>
                  <div style={{ fontSize: '20px', fontWeight: '700', color: 'var(--text-primary)', fontFamily: 'var(--font-serif)' }}>95.0%</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Gold Accuracy</div>
                </div>
                <div>
                  <div style={{ fontSize: '20px', fontWeight: '700', color: 'var(--text-primary)', fontFamily: 'var(--font-serif)' }}>6</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Databases</div>
                </div>
                <div>
                  <div style={{ fontSize: '20px', fontWeight: '700', color: 'var(--text-primary)', fontFamily: 'var(--font-serif)' }}>0</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Black-Box Labels</div>
                </div>
              </div>
            </div>

            {/* Right Column: Original Photograph Container */}
            <div>
              <div className="hero-image-frame">
                {heroImageSrc ? (
                  /* STRICT: Exact photograph, unaltered appearance, no filters, preserved aspect ratio */
                  <img
                    src={heroImageSrc}
                    alt="Research literature with magnifying glass and open volume"
                    style={{
                      width: '100%',
                      height: 'auto',
                      maxHeight: '460px',
                      objectFit: 'contain',
                      display: 'block',
                      borderRadius: '12px'
                    }}
                  />
                ) : (
                  /* STRICT: When asset is missing, report that it is missing rather than substituting another image */
                  <div className="missing-asset-notice">
                    <div style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '12px',
                      background: 'var(--accent-orange-subtle)',
                      color: 'var(--accent-orange)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      margin: '0 auto 16px'
                    }}>
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="11" cy="11" r="8"/>
                        <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                      </svg>
                    </div>
                    <div style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '6px' }}>
                      Hero Photograph Container
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '340px', margin: '0 auto 16px', lineHeight: 1.5 }}>
                      The supplied research photograph (magnifying glass and research book) is currently missing from <code>public/assets/</code>.
                    </div>
                    <div style={{ display: 'inline-flex', gap: '8px' }}>
                      <input
                        type="file"
                        ref={heroImageInputRef}
                        accept="image/*"
                        style={{ display: 'none' }}
                        onChange={handleManualHeroImagePick}
                      />
                      <button
                        onClick={() => heroImageInputRef.current?.click()}
                        className="btn btn-outline btn-sm"
                      >
                        Choose Image File
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* ==================================================================
            2. INTERACTIVE UPLOAD & INGESTION BAY
            ================================================================== */}
        <section id="manuscript-upload-section" style={{ marginBottom: '88px' }}>
          <div style={{ textAlign: 'center', maxWidth: '640px', margin: '0 auto 28px' }}>
            <h2 style={{ fontSize: '28px', marginBottom: '8px' }}>Manuscript Ingestion Bay</h2>
            <p style={{ fontSize: '14px' }}>
              Upload an academic paper to extract claims, map citations, and verify evidence.
            </p>
          </div>

          {/* Friendly Error State Banner (Never Crashes) */}
          {errorMessage && (
            <div style={{
              background: 'var(--unsupported-bg)',
              border: '1px solid var(--unsupported-border)',
              borderRadius: '12px',
              padding: '18px 24px',
              maxWidth: '680px',
              margin: '0 auto 28px',
              textAlign: 'left',
              display: 'flex',
              gap: '14px',
              alignItems: 'flex-start',
              animation: 'fadeIn 0.2s ease-out'
            }}>
              <div style={{ color: 'var(--unsupported-color)', flexShrink: 0, marginTop: '2px' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="12"/>
                  <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '14px', fontWeight: '600', color: 'var(--unsupported-color)', marginBottom: '4px' }}>
                  Verification Resiliency Notice
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.5, marginBottom: '12px' }}>
                  {errorMessage}
                </div>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button onClick={onClearError} className="btn btn-secondary btn-sm">
                    Dismiss
                  </button>
                  <button onClick={onSelectDemo} className="btn btn-primary btn-sm">
                    Load Worked Sample Instead
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* The Upload Card */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className="panel"
            style={{
              maxWidth: '720px',
              margin: '0 auto',
              padding: '48px 36px',
              textAlign: 'center',
              border: dragOver ? '2px dashed var(--accent-orange)' : '1px solid var(--border-line)',
              background: dragOver ? 'var(--accent-orange-subtle)' : 'var(--bg-surface)',
              transition: 'all 0.2s ease'
            }}
          >
            <input
              type="file"
              ref={fileInputRef}
              accept=".pdf,.docx,.doc"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />

            {loading ? (
              /* Animated Loading State */
              <div style={{ padding: '24px 0' }}>
                <div style={{
                  width: '52px',
                  height: '52px',
                  margin: '0 auto 20px',
                  borderRadius: '50%',
                  border: '3px solid var(--border-line)',
                  borderTopColor: 'var(--accent-orange)',
                }} className="spinner-glow" />

                <div style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '8px' }}>
                  Verifying Manuscript Claims...
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '24px' }}>
                  {loadingProgress || 'Extracting claims and resolving cited papers in databases...'}
                </div>

                <div style={{
                  width: '100%',
                  maxWidth: '360px',
                  height: '5px',
                  background: 'var(--bg-surface-elevated)',
                  borderRadius: '3px',
                  margin: '0 auto',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    width: '100%',
                    height: '100%',
                    background: 'linear-gradient(90deg, var(--accent-orange), var(--accent-orange-hover))',
                    borderRadius: '3px',
                  }} className="progress-bar-animated" />
                </div>
              </div>
            ) : (
              /* Ready Upload State */
              <div>
                <div style={{
                  width: '64px',
                  height: '64px',
                  borderRadius: '16px',
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-line)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 20px',
                  color: 'var(--accent-orange)',
                  boxShadow: 'var(--shadow-sm)'
                }}>
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="12" y1="18" x2="12" y2="12"/>
                    <line x1="9" y1="15" x2="12" y2="12"/>
                    <line x1="15" y1="15" x2="12" y2="12"/>
                  </svg>
                </div>

                <div style={{ fontSize: '18px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '8px' }}>
                  Drop your manuscript PDF or DOCX here
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '24px', maxWidth: '440px', margin: '0 auto 24px' }}>
                  Extracts in-text citations like <code>[1]</code> and <code>(Author, 2020)</code>, retrieves the cited literature, and deterministically validates claims.
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', flexWrap: 'wrap' }}>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="btn btn-primary"
                  >
                    Select File from Device
                  </button>
                  <button
                    onClick={onSelectDemo}
                    className="btn btn-secondary"
                  >
                    Quick-Load <code>sample_paper.pdf</code>
                  </button>
                </div>

                {/* Subtext info */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px', marginTop: '28px', fontSize: '11.5px', color: 'var(--text-tertiary)' }}>
                  <span>Supported: .pdf, .docx</span>
                  <span>•</span>
                  <span>Max: 50MB</span>
                  <span>•</span>
                  <span>
                    Status: <strong style={{ color: demoMode ? 'var(--supported-color)' : 'var(--text-primary)' }}>{demoMode ? 'Offline Demo Mode' : 'Live Gateway'}</strong>
                  </span>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* ==================================================================
            3. THREE CORE ARCHITECTURAL PILLARS
            ================================================================== */}
        <section style={{ marginBottom: '80px' }}>
          <div style={{ textAlign: 'center', maxWidth: '640px', margin: '0 auto 40px' }}>
            <h2 style={{ fontSize: '28px', marginBottom: '8px' }}>The Credence Epistemic Guarantee</h2>
            <p style={{ fontSize: '14px' }}>
              How Credence provides deterministic scientific truth without relying on LLM self-reporting.
            </p>
          </div>

          <div className="pillar-grid">
            {/* Pillar 1 */}
            <div className="panel" style={{ padding: '28px 24px' }}>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '10px',
                background: 'var(--accent-orange-subtle)',
                color: 'var(--accent-orange)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '20px'
              }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                  <path d="m9 15 2 2 4-4"/>
                </svg>
              </div>
              <h3 style={{ fontSize: '18px', marginBottom: '10px' }}>1. Deterministic Proof</h3>
              <p style={{ fontSize: '13px', lineHeight: 1.6 }}>
                LLMs judge meaning only. Python deterministically decides every fact: character-level quote existence after 
                Unicode NFKC normalization, number and unit equality, and epistemic hedge word stripping.
              </p>
            </div>

            {/* Pillar 2 */}
            <div className="panel" style={{ padding: '28px 24px' }}>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '10px',
                background: 'var(--accent-orange-subtle)',
                color: 'var(--accent-orange)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '20px'
              }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="m16 10-4 4-2-2"/>
                </svg>
              </div>
              <h3 style={{ fontSize: '18px', marginBottom: '10px' }}>2. Computed Confidence</h3>
              <p style={{ fontSize: '13px', lineHeight: 1.6 }}>
                Confidence is calculated mathematically from paper access tier ceilings (0.9 full-text, 0.6 abstract) minus 
                penalties for unverified slots and pass disagreement. Never the model's self-reported number.
              </p>
            </div>

            {/* Pillar 3 */}
            <div className="panel" style={{ padding: '28px 24px' }}>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '10px',
                background: 'var(--accent-orange-subtle)',
                color: 'var(--accent-orange)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '20px'
              }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                  <line x1="12" y1="8" x2="12" y2="12"/>
                  <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
              </div>
              <h3 style={{ fontSize: '18px', marginBottom: '10px' }}>3. Human Review Ledger</h3>
              <p style={{ fontSize: '13px', lineHeight: 1.6 }}>
                Credence is a research triage aid. Default stance is human review. Reviewers can accept, override, or comment on any claim; 
                all actions are recorded in an append-only SQLite ledger.
              </p>
            </div>
          </div>
        </section>

        {/* ==================================================================
            4. SYSTEM METHODOLOGY STRIP
            ================================================================== */}
        <section style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-line)',
          borderRadius: '14px',
          padding: '36px 32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '24px'
        }}>
          <div>
            <div style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>
              Resilient Academic Pipeline
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              Crossref • OpenAlex • Semantic Scholar • Unpaywall • arXiv • PubMed Central
            </div>
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <button onClick={onForceError} className="btn btn-outline btn-sm" title="Simulates API gateway timeout to prove error handling">
              Simulate Pipeline Failure
            </button>
            <button onClick={onSelectDemo} className="btn btn-primary btn-sm">
              Launch Interactive Dossier
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
