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
  const [heroImageSrc, setHeroImageSrc] = useState('/assets/hero-research.jpg');
  const [imageChecked, setImageChecked] = useState(true);
  const fileInputRef = useRef(null);
  const heroImageInputRef = useRef(null);

  // Ensure permanent hero research photograph is active
  useEffect(() => {
    const img = new Image();
    img.src = '/assets/hero-research.jpg';
    img.onload = () => {
      setHeroImageSrc('/assets/hero-research.jpg');
      setImageChecked(true);
    };
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
    <div style={{ padding: '24px 0 80px' }}>
      <div className="container">
        {/* ==================================================================
            1. SEAMLESS INTEGRATED HERO SECTION (BLENDED PHOTOGRAPH)
            ================================================================== */}
        <section className="hero-integrated-section">
          <div className="hero-integrated-grid">
            {/* Left Column: Heading, Value Proposition & Actions */}
            <div className="hero-text-stage">
              {/* Scholarly Badge */}
              <div style={{ display: 'inline-flex', alignItems: 'center' }}>
                <span className="hero-badge-pill">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"/>
                  </svg>
                  Epistemic Verification Engine
                </span>
              </div>

              {/* Main Headline (Spectral Serif) with "Proof." highlighted in Credence orange */}
              <h1 className="hero-title-headline">
                Scientific Claims Demand<br />
                Deterministic <span className="hero-proof-highlight">Proof.</span>
              </h1>

              {/* Description */}
              <p className="hero-description-text">
                Academic manuscripts frequently cite literature out of context, strip hedges, or rely on outdated findings. 
                Credence retrieves the cited source paper and verifies whether the text genuinely backs each empirical assertion with 
                verbatim proof.
              </p>

              {/* Action Buttons */}
              <div className="hero-cta-group">
                <button
                  onClick={scrollToUpload}
                  className="hero-btn-primary"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>
                  Verify Manuscript
                </button>

                <button
                  onClick={onSelectDemo}
                  className="hero-btn-secondary"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"/>
                    <polygon points="10 8 16 12 10 16 10 8" fill="currentColor"/>
                  </svg>
                  Explore Worked Demo
                </button>
              </div>

              {/* Statistics Row with subtle separators */}
              <div className="hero-stats-row">
                <div className="hero-stat-item">
                  <div className="hero-stat-number">100%</div>
                  <div className="hero-stat-label">Quotes Proven</div>
                </div>
                <div className="hero-stat-divider" />
                <div className="hero-stat-item">
                  <div className="hero-stat-number">95.0%</div>
                  <div className="hero-stat-label">Gold Accuracy</div>
                </div>
                <div className="hero-stat-divider" />
                <div className="hero-stat-item">
                  <div className="hero-stat-number">6</div>
                  <div className="hero-stat-label">Databases</div>
                </div>
                <div className="hero-stat-divider" />
                <div className="hero-stat-item">
                  <div className="hero-stat-number">0</div>
                  <div className="hero-stat-label">Black-Box Labels</div>
                </div>
              </div>
            </div>

            {/* Right Column: Seamlessly Blended Photograph (No Card, No Rectangular Border) */}
            <div className="hero-blended-stage">
              {/* Ambient backlight glow */}
              <div className="hero-ambient-glow" />

              {/* Subtle orbital trajectory curves */}
              <svg className="hero-orbital-svg" viewBox="0 0 600 500" fill="none" preserveAspectRatio="xMidYMid meet">
                <path
                  d="M 120 440 C 260 300, 420 140, 580 40"
                  stroke="url(#heroOrbitGrad)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <path
                  d="M 280 480 C 400 400, 510 290, 590 170"
                  stroke="url(#heroOrbitGradSubtle)"
                  strokeWidth="1.2"
                  strokeDasharray="4 6"
                />
                <defs>
                  <linearGradient id="heroOrbitGrad" x1="0%" y1="100%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#f06a2c" stopOpacity="0" />
                    <stop offset="40%" stopColor="#f06a2c" stopOpacity="0.75" />
                    <stop offset="85%" stopColor="#ff7d3c" stopOpacity="0.9" />
                    <stop offset="100%" stopColor="#ff7d3c" stopOpacity="0.1" />
                  </linearGradient>
                  <linearGradient id="heroOrbitGradSubtle" x1="0%" y1="100%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#f06a2c" stopOpacity="0" />
                    <stop offset="60%" stopColor="#f06a2c" stopOpacity="0.35" />
                    <stop offset="100%" stopColor="#ff7d3c" stopOpacity="0" />
                  </linearGradient>
                </defs>
              </svg>

              {/* The Photograph with multi-axis transparent edge masks */}
              <img
                src={heroImageSrc}
                alt="Research literature with magnifying glass and open volume"
                className="hero-blended-photograph"
                onError={(e) => {
                  if (e.target.src && !e.target.src.endsWith('/assets/hero-research.jpg')) {
                    e.target.src = '/assets/hero-research.jpg';
                  }
                }}
              />

              {/* Multi-angle soft edge dissolves that merge seamlessly into dark background */}
              <div className="hero-edge-fade-left" />
              <div className="hero-edge-fade-bottom" />
              <div className="hero-edge-fade-top" />
              <div className="hero-edge-fade-right" />
            </div>
          </div>
        </section>

        {/* Ambient Section Transition Divider */}
        <div className="hero-section-divider">
          <div className="hero-divider-line" />
          <div className="hero-divider-diamond" />
          <div className="hero-divider-line right" />
        </div>

        {/* ==================================================================
            2. INTERACTIVE UPLOAD & INGESTION BAY
            ================================================================== */}
        <section id="manuscript-upload-section" style={{ marginBottom: '88px' }}>
          <div style={{ textAlign: 'center', maxWidth: '640px', margin: '0 auto 26px' }}>
            <h2 style={{ fontSize: '26px', fontFamily: 'var(--font-serif)', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '8px' }}>
              Manuscript Ingestion Bay
            </h2>
            <p style={{ fontSize: '13.5px', color: 'var(--text-secondary)', margin: 0 }}>
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
            onClick={() => !loading && fileInputRef.current?.click()}
            className={`manuscript-ingestion-zone ${dragOver ? 'dragover' : ''}`}
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
                  width: '48px',
                  height: '48px',
                  margin: '0 auto 16px',
                  borderRadius: '50%',
                  border: '3px solid var(--border-line)',
                  borderTopColor: 'var(--accent-orange)',
                }} className="spinner-glow" />

                <div style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '6px' }}>
                  Verifying Manuscript Claims...
                </div>
                <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginBottom: '20px' }}>
                  {loadingProgress || 'Extracting claims and resolving cited papers in databases...'}
                </div>

                <div style={{
                  width: '100%',
                  maxWidth: '320px',
                  height: '4px',
                  background: 'var(--bg-surface-elevated)',
                  borderRadius: '2px',
                  margin: '0 auto',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    width: '100%',
                    height: '100%',
                    background: 'linear-gradient(90deg, var(--accent-orange), var(--accent-orange-hover))',
                    borderRadius: '2px',
                  }} className="progress-bar-animated" />
                </div>
              </div>
            ) : (
              /* Ready Upload State - Clean, Spacious matching reference image */
              <div style={{ padding: '4px 0' }}>
                <div style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '10px',
                  background: 'var(--accent-orange-subtle)',
                  border: '1px solid var(--accent-orange-border)',
                  color: 'var(--accent-orange)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 10px',
                }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="12" y1="18" x2="12" y2="12"/>
                    <line x1="9" y1="15" x2="12" y2="12"/>
                    <line x1="15" y1="15" x2="12" y2="12"/>
                  </svg>
                </div>

                <div style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>
                  Drop your manuscript PDF or DOCX here
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
                  or click to browse
                </div>
              </div>
            )}
          </div>

          {/* Quick-load & format footer below card */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '14px',
            marginTop: '16px',
            fontSize: '11px',
            color: 'var(--text-tertiary)'
          }}>
            <span>Supported: .pdf, .docx</span>
            <span>•</span>
            <span
              onClick={onSelectDemo}
              style={{ color: 'var(--accent-orange)', cursor: 'pointer', textDecoration: 'none', fontWeight: '600' }}
              role="button"
              tabIndex={0}
            >
              Quick-load worked demo (sample_paper.pdf) ↗
            </span>
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
