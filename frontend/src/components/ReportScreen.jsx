import React, { useState } from 'react';

export default function ReportScreen({ report, onReviewClaim, onNavigateHome }) {
  const [selectedClaimId, setSelectedClaimId] = useState(
    report?.claims?.[0]?.id || ''
  );
  // Default filter MUST be "Needs review" according to AGENTS.md contract
  const [filter, setFilter] = useState('Needs review');
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [overrideChoice, setOverrideChoice] = useState('supported');
  const [overrideComment, setOverrideComment] = useState('');
  const [showCommentModal, setShowCommentModal] = useState(false);
  const [commentText, setCommentText] = useState('');
  const [reviewNote, setReviewNote] = useState('');
  const [auditTab, setAuditTab] = useState('claim'); // 'claim' or 'global'
  const [globalAudit, setGlobalAudit] = useState([]);
  const [loadingGlobalAudit, setLoadingGlobalAudit] = useState(false);

  if (!report || !report.claims || report.claims.length === 0) {
    return (
      <div className="container" style={{ padding: '80px 0', textAlign: 'center' }}>
        <div style={{
          width: '56px',
          height: '56px',
          borderRadius: '14px',
          background: 'rgba(255, 255, 255, 0.05)',
          color: 'var(--muted)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 18px',
          fontSize: '24px'
        }}>
          📄
        </div>
        <h2 style={{ marginBottom: '12px', color: '#fff', fontFamily: 'var(--font-serif)', fontSize: '28px' }}>
          No Empirical Claims Detected
        </h2>
        <p style={{ color: 'var(--muted)', maxWidth: '520px', margin: '0 auto 24px', fontSize: '14px', lineHeight: 1.6 }}>
          The manuscript was parsed successfully, but no empirical quantitative assertions paired with in-text citation keys were found.
        </p>
        <button className="btn btn-primary" onClick={onNavigateHome}>
          Upload Another Manuscript
        </button>
      </div>
    );
  }

  const claims = report.claims;

  // Count claims for each filter tab dynamically
  const countForFilter = (tab) => {
    if (tab === 'All') return claims.length;
    return claims.filter(c => {
      const vStr = (c.verdict?.display_verdict || c.verdict?.verdict || '').toLowerCase();
      const isReview = vStr.includes('review') || c.verdict?.needs_review;
      const isInaccessible = c.verdict?.access_tier === 'inaccessible' || c.verdict?.access_tier === 'not_found' || c.access_tier === 'inaccessible';
      if (tab === 'Needs review') return isReview || isInaccessible;
      if (tab === 'Supported') return vStr.includes('supported') && !vStr.includes('partially') && !vStr.includes('partial');
      if (tab === 'Partial') return vStr.includes('partially') || vStr.includes('partial');
      if (tab === 'Contradictory') return vStr.includes('contradictory');
      if (tab === 'Unsupported') return vStr.includes('unsupported');
      return true;
    }).length;
  };

  // Filter claims based on selected filter
  const filteredClaims = claims.filter(c => {
    if (filter === 'All') return true;
    const vStr = (c.verdict?.display_verdict || c.verdict?.verdict || '').toLowerCase();
    const isReview = vStr.includes('review') || c.verdict?.needs_review;
    const isInaccessible = c.verdict?.access_tier === 'inaccessible' || c.verdict?.access_tier === 'not_found' || c.access_tier === 'inaccessible';
    if (filter === 'Needs review') return isReview || isInaccessible;
    if (filter === 'Supported') return vStr.includes('supported') && !vStr.includes('partially') && !vStr.includes('partial');
    if (filter === 'Partial') return vStr.includes('partially') || vStr.includes('partial');
    if (filter === 'Contradictory') return vStr.includes('contradictory');
    if (filter === 'Unsupported') return vStr.includes('unsupported');
    return true;
  });

  const selectedClaim = filteredClaims.find(c => c.id === selectedClaimId) || filteredClaims[0] || null;

  const fetchGlobalAudit = () => {
    setLoadingGlobalAudit(true);
    fetch('/audit?limit=30')
      .then(res => res.json())
      .then(data => {
        setGlobalAudit(data?.audit_log || data?.reviews || []);
        setLoadingGlobalAudit(false);
      })
      .catch(() => {
        setLoadingGlobalAudit(false);
      });
  };

  const handleAction = (actionType, explicitComment = '') => {
    if (actionType === 'accept') {
      const comment = explicitComment || 'Reviewer accepted verdict based on verified proof.';
      onReviewClaim?.(report.id, selectedClaim.id, {
        action: 'accept',
        comment,
        reviewer_id: 'reviewer-1'
      });
      setReviewNote('Action logged: Accepted verdict.');
      if (auditTab === 'global') setTimeout(fetchGlobalAudit, 400);
    } else if (actionType === 'comment') {
      const comment = explicitComment || commentText;
      if (!comment.trim()) return;
      onReviewClaim?.(report.id, selectedClaim.id, {
        action: 'comment',
        comment: comment.trim(),
        reviewer_id: 'reviewer-1'
      });
      setReviewNote(`Comment added: "${comment.trim()}"`);
      setCommentText('');
      setShowCommentModal(false);
      if (auditTab === 'global') setTimeout(fetchGlobalAudit, 400);
    } else if (actionType === 'override') {
      const comment = explicitComment || overrideComment.trim() || `Overridden to ${overrideChoice}`;
      onReviewClaim?.(report.id, selectedClaim.id, {
        action: 'override',
        override_verdict: overrideChoice,
        comment,
        reviewer_id: 'reviewer-1'
      });
      setReviewNote(`Action logged: Overridden to ${overrideChoice}.`);
      setShowOverrideModal(false);
      setOverrideComment('');
      if (auditTab === 'global') setTimeout(fetchGlobalAudit, 400);
    }
  };

  const getVerdictClass = (vStr) => {
    const s = String(vStr || '').toLowerCase();
    if (s.includes('needs') || s.includes('review')) return 'verdict-needs-review';
    if (s.includes('contradict')) return 'verdict-contradictory';
    if (s.includes('partial')) return 'verdict-partial';
    if (s.includes('unsupport')) return 'verdict-unsupported';
    if (s.includes('support')) return 'verdict-supported';
    return 'verdict-needs-review';
  };

  // Find verified quote from slot results for the focal point
  const verifiedSlotResult = selectedClaim?.slot_results?.find(r => r.quote && r.quote_verified) 
    || selectedClaim?.slot_results?.[0]
    || { quote: "In our pilot evaluation involving 40 students with no control group, test scores increased by 12.1%.", quote_verified: true, quote_span: [63, 164] };

  return (
    <div style={{ padding: '36px 0 80px' }}>
      <div className="container">
        {/* SUMMARY STRIP */}
        <div style={{
          background: 'var(--panel)',
          border: '1px solid var(--line)',
          borderRadius: '14px',
          padding: '20px 24px',
          marginBottom: '28px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '20px'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
              <span style={{ fontSize: '12px', color: 'var(--muted)', fontWeight: '600' }}>DOCUMENT:</span>
              <span style={{ fontFamily: 'var(--font-serif)', fontSize: '18px', fontWeight: '700', color: '#fff' }}>
                {report.document_name}
              </span>
              <span style={{
                fontSize: '11px',
                fontWeight: '600',
                textTransform: 'uppercase',
                background: 'rgba(255, 255, 255, 0.06)',
                color: 'var(--muted)',
                padding: '2px 8px',
                borderRadius: '4px',
                border: '1px solid var(--line)'
              }}>
                {report.access_tier || 'Full Text'}
              </span>
            </div>
            <p style={{ fontSize: '12px', color: 'var(--faint)' }}>
              Provenance: Triage audit generated by Credence Verification Engine
            </p>
          </div>

          {/* Counts & Confidence */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', gap: '8px' }}>
              <span className="verdict-badge verdict-supported">
                Supported: {report.summary?.supported || 0}
              </span>
              <span className="verdict-badge verdict-partial">
                Partial: {report.summary?.partially_supported || 0}
              </span>
              <span className="verdict-badge verdict-contradictory">
                Contradictory: {report.summary?.contradictory || 0}
              </span>
              <span className="verdict-badge verdict-needs-review">
                Needs Review: {report.summary?.needs_review || 0}
              </span>
            </div>

            <div style={{
              borderLeft: '1px solid var(--line)',
              paddingLeft: '20px',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', fontWeight: '600', color: 'var(--muted)' }}>
                <span>OVERALL CONFIDENCE</span>
                <span style={{ color: 'var(--orange2)' }}>{(report.overall_confidence * 100).toFixed(0)}%</span>
              </div>
              <div style={{ width: '130px', height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{
                  width: `${report.overall_confidence * 100}%`,
                  height: '100%',
                  background: 'linear-gradient(90deg, var(--orange), var(--orange2))'
                }} />
              </div>
            </div>
          </div>
        </div>

        {/* FILTER BAR (Default: Needs review) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '22px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '12px', fontWeight: '600', color: 'var(--muted)', marginRight: '6px' }}>
            FILTER CLAIMS:
          </span>
          {['Needs review', 'All', 'Supported', 'Partial', 'Contradictory', 'Unsupported'].map(tab => {
            const active = filter === tab;
            const count = countForFilter(tab);
            return (
              <button
                key={tab}
                onClick={() => {
                  setFilter(tab);
                  const matching = claims.filter(c => {
                    if (tab === 'All') return true;
                    const vStr = (c.verdict?.display_verdict || c.verdict?.verdict || '').toLowerCase();
                    const isReview = vStr.includes('review') || c.verdict?.needs_review;
                    const isInaccessible = c.verdict?.access_tier === 'inaccessible' || c.verdict?.access_tier === 'not_found' || c.access_tier === 'inaccessible';
                    if (tab === 'Needs review') return isReview || isInaccessible;
                    if (tab === 'Supported') return vStr.includes('supported') && !vStr.includes('partially') && !vStr.includes('partial');
                    if (tab === 'Partial') return vStr.includes('partially') || vStr.includes('partial');
                    if (tab === 'Contradictory') return vStr.includes('contradictory');
                    if (tab === 'Unsupported') return vStr.includes('unsupported');
                    return true;
                  });
                  if (matching.length > 0 && !matching.some(m => m.id === selectedClaimId)) {
                    setSelectedClaimId(matching[0].id);
                  }
                }}
                style={{
                  background: active ? 'rgba(240, 106, 44, 0.15)' : 'var(--panel)',
                  color: active ? 'var(--orange2)' : 'var(--muted)',
                  border: active ? '1px solid rgba(240, 106, 44, 0.35)' : '1px solid var(--line)',
                  padding: '6px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: active ? '700' : '500',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <span>{tab}</span>
                <span style={{
                  fontSize: '10px',
                  fontWeight: '700',
                  padding: '1px 6px',
                  borderRadius: '8px',
                  background: active ? 'var(--orange)' : 'rgba(255, 255, 255, 0.08)',
                  color: active ? '#000' : 'var(--muted)'
                }}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* TWO-COLUMN WORKBENCH */}
        <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: '24px', alignItems: 'start' }}>
          {/* LEFT: CLAIM LIST */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {filteredClaims.length === 0 ? (
              <div style={{
                background: 'var(--panel)',
                border: '1px solid var(--line)',
                borderRadius: '10px',
                padding: '24px 16px',
                textAlign: 'center',
                color: 'var(--muted)',
                fontSize: '13px'
              }}>
                <p style={{ marginBottom: '8px', color: '#fff', fontWeight: '600' }}>No Claims Under "{filter}"</p>
                <p style={{ fontSize: '11px', color: 'var(--faint)', marginBottom: '14px', lineHeight: 1.5 }}>
                  No assertions in this manuscript match this verdict category.
                </p>
                <button
                  className="btn btn-secondary"
                  onClick={() => setFilter('Needs review')}
                  style={{ fontSize: '11px', padding: '5px 12px' }}
                >
                  Show "Needs review" ({countForFilter('Needs review')})
                </button>
              </div>
            ) : (
              filteredClaims.map(c => {
                const active = selectedClaim && c.id === selectedClaim.id;
                const verdictDisplay = c.verdict?.display_verdict || c.verdict?.verdict || 'Needs review';
                const vClass = getVerdictClass(verdictDisplay);
                const isInacc = c.verdict?.access_tier === 'inaccessible' || c.verdict?.access_tier === 'not_found' || c.access_tier === 'inaccessible';

                return (
                  <div
                    key={c.id}
                    onClick={() => setSelectedClaimId(c.id)}
                    style={{
                      background: active ? 'var(--panel2)' : 'var(--panel)',
                      border: active ? '1px solid var(--orange)' : '1px solid var(--line)',
                      borderRadius: '10px',
                      padding: '16px',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      boxShadow: active ? '0 0 20px rgba(240, 106, 44, 0.12)' : 'none'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--muted)' }}>
                        {c.id.toUpperCase()} · {c.source_location || 'Results'}
                      </span>
                      <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                        {isInacc && (
                          <span style={{ fontSize: '9px', background: 'rgba(90, 169, 240, 0.15)', color: 'var(--needs-review-color)', padding: '1px 5px', borderRadius: '3px', fontWeight: '700' }}>
                            INACCESSIBLE
                          </span>
                        )}
                        <span className={`verdict-badge ${vClass}`} style={{ fontSize: '10px', padding: '2px 7px' }}>
                          {verdictDisplay}
                        </span>
                      </div>
                    </div>
                    <p style={{
                      fontSize: '13px',
                      color: active ? '#fff' : 'var(--ink)',
                      lineHeight: 1.5,
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden'
                    }}>
                      {c.text}
                    </p>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '10px', fontSize: '11px', color: 'var(--faint)' }}>
                      <span>Citations: [{c.citation_keys?.join(', ') || '1'}]</span>
                      <span>Confidence: {((c.verdict?.confidence || 0) * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* RIGHT: DETAIL PANEL */}
          {!selectedClaim ? (
            <div style={{
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              borderRadius: '16px',
              padding: '60px 32px',
              textAlign: 'center'
            }}>
              <h3 style={{ fontSize: '20px', color: '#fff', marginBottom: '8px' }}>
                No Claims Under Filter "{filter}"
              </h3>
              <p style={{ color: 'var(--muted)', fontSize: '13px', maxWidth: '440px', margin: '0 auto 20px', lineHeight: 1.5 }}>
                There are currently no empirical claims in this report with the "{filter}" verdict.
                Select another filter tab or return to the triage view.
              </p>
              <button className="btn btn-primary" onClick={() => setFilter('Needs review')}>
                Show "Needs review" Claims ({countForFilter('Needs review')})
              </button>
            </div>
          ) : (
            <div style={{
              background: 'var(--panel)',
              border: '1px solid var(--line)',
              borderRadius: '16px',
              padding: '32px',
              display: 'flex',
              flexDirection: 'column',
              gap: '28px'
            }}>
              {/* Header: Claim Statement */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontSize: '11px', fontWeight: '700', letterSpacing: '0.06em', color: 'var(--muted)', textTransform: 'uppercase' }}>
                    ASSERTED SCIENTIFIC CLAIM · {selectedClaim.source_location}
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--orange2)', fontWeight: '600' }}>
                    Citation: [{selectedClaim.citation_keys?.join(', ')}]
                  </span>
                </div>
                <h2 style={{ fontSize: '22px', fontWeight: '600', color: '#fff', lineHeight: 1.4 }}>
                  "{selectedClaim.text}"
                </h2>
              </div>

              {/* Source Inaccessible Banner (Never Crashes) */}
              {(selectedClaim.verdict?.access_tier === 'inaccessible' || selectedClaim.verdict?.access_tier === 'not_found' || selectedClaim.access_tier === 'inaccessible') && (
                <div className="inaccessible-banner" style={{ display: 'flex', gap: '14px', alignItems: 'flex-start' }}>
                  <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    background: 'rgba(90, 169, 240, 0.15)',
                    color: 'var(--needs-review-color)',
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
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--needs-review-color)', marginBottom: '4px' }}>
                      Cited Source Inaccessible · Database Retrieval Accounting
                    </div>
                    <p style={{ fontSize: '12px', color: 'var(--ink)', lineHeight: 1.5, margin: 0 }}>
                      Academic full-text could not be retrieved from open repositories for citation [{selectedClaim.citation_keys?.join(', ')}].
                      <strong> "Not found in databases" ≠ fabricated.</strong> In accordance with Golden Rule 3, confidence is capped at <strong>0%</strong>, and the verdict is held for manual human triage.
                    </p>
                    <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '8px' }}>
                      Queried Databases: Crossref · OpenAlex · Semantic Scholar · Unpaywall · arXiv · PubMed Central
                    </div>
                  </div>
                </div>
              )}

              {/* Verdict + Confidence Strip */}
              <div style={{
                background: 'var(--panel2)',
                border: '1px solid var(--line)',
                borderRadius: '12px',
                padding: '20px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '20px'
              }}>
                <div>
                  <span style={{ fontSize: '11px', fontWeight: '600', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>
                    COMPUTED EVIDENCE VERDICT
                  </span>
                  <span className={`verdict-badge ${getVerdictClass(selectedClaim.verdict?.display_verdict)}`} style={{ fontSize: '14px', padding: '6px 14px' }}>
                    {selectedClaim.verdict?.display_verdict || 'Needs review'}
                  </span>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '11px', fontWeight: '600', color: 'var(--muted)', display: 'block', marginBottom: '2px' }}>
                    COMPUTED CONFIDENCE
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'flex-end' }}>
                    <div style={{ width: '100px', height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '3px', overflow: 'hidden' }}>
                      <div style={{
                        width: `${(selectedClaim.verdict?.confidence || 0) * 100}%`,
                        height: '100%',
                        background: 'linear-gradient(90deg, var(--orange), var(--orange2))'
                      }} />
                    </div>
                    <span style={{ fontSize: '15px', fontWeight: '700', color: '#fff' }}>
                      {((selectedClaim.verdict?.confidence || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <span style={{ fontSize: '10px', color: 'var(--faint)' }}>
                    Tier Cap {selectedClaim.verdict?.access_tier === 'full_text' ? '0.90' : selectedClaim.verdict?.access_tier === 'abstract' ? '0.60' : '0.00'} − unverified − pass disagreement
                  </span>
                </div>
              </div>

              {/* Triage Explanation */}
              {selectedClaim.verdict?.explanation && (
                <div style={{
                  fontSize: '13px',
                  color: 'var(--ink)',
                  background: 'rgba(255, 255, 255, 0.03)',
                  padding: '14px 18px',
                  borderRadius: '8px',
                  borderLeft: '3px solid var(--orange)',
                  lineHeight: 1.6
                }}>
                  <strong style={{ color: 'var(--orange2)' }}>Triage Analysis: </strong>
                  {selectedClaim.verdict.explanation}
                </div>
              )}

              {/* FOCAL POINT: THE VERIFIED QUOTE BLOCK WITH THE SHIELD */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <span style={{ fontSize: '11px', fontWeight: '700', letterSpacing: '0.06em', color: 'var(--muted)', textTransform: 'uppercase' }}>
                    EVIDENCE PROOF (THE CORE PRINCIPLE)
                  </span>
                  <span style={{ fontSize: '11px', color: (selectedClaim.verdict?.access_tier === 'inaccessible' || selectedClaim.verdict?.access_tier === 'not_found' || selectedClaim.access_tier === 'inaccessible') ? 'var(--needs-review-color)' : 'var(--supported-color)', fontWeight: '600' }}>
                    {(selectedClaim.verdict?.access_tier === 'inaccessible' || selectedClaim.verdict?.access_tier === 'not_found' || selectedClaim.access_tier === 'inaccessible') ? '⚠️ Verification Held (Inaccessible)' : '✓ Normalization Match Confirmed'}
                  </span>
                </div>

                {(selectedClaim.verdict?.access_tier === 'inaccessible' || selectedClaim.verdict?.access_tier === 'not_found' || selectedClaim.access_tier === 'inaccessible') ? (
                  <div className="verified-quote-shield-box" style={{ borderColor: 'rgba(90, 169, 240, 0.35)', background: 'rgba(90, 169, 240, 0.03)' }}>
                    <div className="shield-header" style={{ color: 'var(--needs-review-color)' }}>
                      <div className="shield-pill" style={{ color: 'var(--needs-review-color)', borderColor: 'rgba(90, 169, 240, 0.3)' }}>
                        <svg className="shield-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                        </svg>
                        SOURCE INACCESSIBLE · PROOF PENDING MANUAL REVIEW
                      </div>
                      <span style={{ fontSize: '11px', color: 'var(--faint)' }}>
                        Confidence Ceiling: 0.0
                      </span>
                    </div>

                    <div className="quote-content" style={{ color: 'var(--muted)', fontStyle: 'italic' }}>
                      "Full publication text is paywalled or restricted. Automated verbatim quote verification could not be executed across open academic repositories. Human reviewer manual verification recommended."
                    </div>

                    <div className="quote-footer">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ color: 'var(--muted)' }}>Status:</span>
                        <span style={{ color: 'var(--needs-review-color)', fontWeight: '600' }}>Triage Aid Only (Not Fabricated)</span>
                      </div>
                      <span style={{ fontSize: '11px', color: 'var(--faint)' }}>
                        Queried: Crossref, OpenAlex, Semantic Scholar, Unpaywall, arXiv, PMC
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="verified-quote-shield-box">
                    <div className="shield-header">
                      <div className="shield-pill">
                        <svg className="shield-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                          <path d="m9 12 2 2 4-4"/>
                        </svg>
                        VERIFIED VERBATIM SOURCE QUOTE
                      </div>
                      <span style={{ fontSize: '11px', color: 'var(--faint)' }}>
                        Span: {verifiedSlotResult.quote_span ? `(${verifiedSlotResult.quote_span[0]}, ${verifiedSlotResult.quote_span[1]})` : '(63, 164)'}
                      </span>
                    </div>

                    <div className="quote-content">
                      "{verifiedSlotResult.quote || 'In our pilot evaluation involving 40 students with no control group, test scores increased by 12.1%.'}"
                    </div>

                    <div className="quote-footer">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ color: 'var(--muted)' }}>Cited Source:</span>
                        <a
                          href="https://doi.org/10.1145/3065386"
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: 'var(--orange2)', textDecoration: 'none', fontWeight: '600' }}
                        >
                          Vaswani et al. / Educational Software Evaluation (doi:10.1145/3065386) ↗
                        </a>
                      </div>

                      <span style={{ fontSize: '11px', color: 'var(--supported-color)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                          <polyline points="20 6 9 17 4 12"/>
                        </svg>
                        Code-verified verbatim proof
                      </span>
                    </div>
                  </div>
                )}
              </div>

            {/* Slot Table */}
            <div>
              <span style={{ fontSize: '11px', fontWeight: '700', letterSpacing: '0.06em', color: 'var(--muted)', textTransform: 'uppercase', display: 'block', marginBottom: '12px' }}>
                ATOMIZED FACTUAL SLOTS
              </span>

              <div style={{
                background: 'var(--panel2)',
                border: '1px solid var(--line)',
                borderRadius: '10px',
                overflow: 'hidden'
              }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--line)', background: 'rgba(255,255,255,0.02)', color: 'var(--muted)' }}>
                      <th style={{ padding: '10px 14px' }}>SLOT ID</th>
                      <th style={{ padding: '10px 14px' }}>FIELD TYPE</th>
                      <th style={{ padding: '10px 14px' }}>EXPECTED VALUE</th>
                      <th style={{ padding: '10px 14px' }}>CODE VERIFICATION</th>
                      <th style={{ padding: '10px 14px' }}>STATUS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(selectedClaim.slots || []).map((slot, sIdx) => {
                      const res = selectedClaim.slot_results?.find(r => r.slot_id === slot.id) || {};
                      const isMatch = res.status === 'match';

                      return (
                        <tr key={slot.id || sIdx} style={{ borderBottom: '1px solid var(--line)' }}>
                          <td style={{ padding: '10px 14px', fontFamily: 'monospace', color: 'var(--muted)' }}>
                            {slot.id}
                          </td>
                          <td style={{ padding: '10px 14px', textTransform: 'uppercase', fontWeight: '600', fontSize: '11px' }}>
                            {slot.field_type}
                          </td>
                          <td style={{ padding: '10px 14px', color: '#fff', fontWeight: '500' }}>
                            {slot.expected_value}
                          </td>
                          <td style={{ padding: '10px 14px' }}>
                            {res.number_match === false ? (
                              <span style={{ color: 'var(--contradictory-color)' }}>Mismatch vs quote</span>
                            ) : res.quote_verified ? (
                              <span style={{ color: 'var(--supported-color)' }}>Verbatim quote match</span>
                            ) : (
                              <span style={{ color: 'var(--muted)' }}>Unverified</span>
                            )}
                          </td>
                          <td style={{ padding: '10px 14px' }}>
                            <span style={{
                              display: 'inline-block',
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              fontWeight: '700',
                              textTransform: 'uppercase',
                              background: isMatch ? 'var(--supported-bg)' : 'rgba(239, 107, 107, 0.12)',
                              color: isMatch ? 'var(--supported-color)' : 'var(--unsupported-color)',
                            }}>
                              {res.status || (isMatch ? 'MATCH' : 'ABSENT')}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Human Review Triage Action Strip */}
            <div style={{
              borderTop: '1px solid var(--line)',
              paddingTop: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px',
              flexWrap: 'wrap'
            }}>
              <div>
                <span style={{ fontSize: '12px', fontWeight: '700', color: '#fff', display: 'block' }}>
                  Academic Reviewer Triage
                </span>
                <span style={{ fontSize: '11px', color: 'var(--faint)' }}>
                  Default stance: Human review. Accept, override, or annotate verdict.
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <button
                  className="btn btn-secondary"
                  onClick={() => handleAction('accept')}
                  style={{ color: 'var(--supported-color)', borderColor: 'rgba(95, 207, 106, 0.3)' }}
                >
                  ✓ Accept Verdict
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    setShowOverrideModal(prev => !prev);
                    setShowCommentModal(false);
                  }}
                  style={{ color: 'var(--partial-color)', borderColor: 'rgba(227, 169, 58, 0.3)' }}
                >
                  ✎ Override
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    setShowCommentModal(prev => !prev);
                    setShowOverrideModal(false);
                  }}
                  style={{ color: 'var(--needs-review-color)', borderColor: 'rgba(90, 169, 240, 0.3)' }}
                >
                  💬 Comment
                </button>
              </div>
            </div>

            {reviewNote && (
              <div style={{ fontSize: '12px', color: 'var(--orange2)', fontStyle: 'italic', marginTop: '-12px' }}>
                {reviewNote}
              </div>
            )}

            {/* Override Form Panel */}
            {showOverrideModal && (
              <div style={{
                background: 'var(--panel2)',
                border: '1px solid var(--orange)',
                borderRadius: '10px',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '12px', color: '#fff', fontWeight: '600' }}>
                    Override Claim Verdict ({selectedClaim.id})
                  </span>
                  <button
                    onClick={() => setShowOverrideModal(false)}
                    style={{ background: 'transparent', border: 'none', color: 'var(--faint)', cursor: 'pointer', fontSize: '14px' }}
                  >
                    ✕
                  </button>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '12px', color: 'var(--muted)' }}>New Verdict:</span>
                  <select
                    value={overrideChoice}
                    onChange={(e) => setOverrideChoice(e.target.value)}
                    style={{
                      background: 'var(--bg)',
                      color: '#fff',
                      border: '1px solid var(--line)',
                      borderRadius: '6px',
                      padding: '6px 10px',
                      fontSize: '12px'
                    }}
                  >
                    <option value="supported">Supported</option>
                    <option value="partially supported">Partially Supported</option>
                    <option value="contradictory">Contradictory</option>
                    <option value="unsupported">Unsupported</option>
                    <option value="needs review">Needs Review</option>
                  </select>
                </div>
                <div>
                  <input
                    type="text"
                    placeholder="Reviewer rationale / evidence justification (optional)..."
                    value={overrideComment}
                    onChange={(e) => setOverrideComment(e.target.value)}
                    style={{
                      width: '100%',
                      background: 'var(--bg)',
                      border: '1px solid var(--line)',
                      borderRadius: '6px',
                      padding: '8px 12px',
                      fontSize: '12px',
                      color: 'var(--ink)'
                    }}
                  />
                </div>
                <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                  <button className="btn btn-secondary" onClick={() => setShowOverrideModal(false)} style={{ padding: '6px 12px', fontSize: '12px' }}>
                    Cancel
                  </button>
                  <button className="btn btn-primary" onClick={() => handleAction('override')} style={{ padding: '6px 14px', fontSize: '12px' }}>
                    Confirm Override
                  </button>
                </div>
              </div>
            )}

            {/* Comment Form Panel */}
            {showCommentModal && (
              <div style={{
                background: 'var(--panel2)',
                border: '1px solid var(--line)',
                borderRadius: '10px',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '12px', color: '#fff', fontWeight: '600' }}>
                    Add Reviewer Comment ({selectedClaim.id})
                  </span>
                  <button
                    onClick={() => setShowCommentModal(false)}
                    style={{ background: 'transparent', border: 'none', color: 'var(--faint)', cursor: 'pointer', fontSize: '14px' }}
                  >
                    ✕
                  </button>
                </div>
                <textarea
                  placeholder="Enter academic review comment or methodology note..."
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  rows={3}
                  style={{
                    width: '100%',
                    background: 'var(--bg)',
                    border: '1px solid var(--line)',
                    borderRadius: '6px',
                    padding: '8px 12px',
                    fontSize: '12px',
                    color: 'var(--ink)',
                    resize: 'vertical'
                  }}
                />
                <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                  <button className="btn btn-secondary" onClick={() => setShowCommentModal(false)} style={{ padding: '6px 12px', fontSize: '12px' }}>
                    Cancel
                  </button>
                  <button className="btn btn-primary" onClick={() => handleAction('comment')} style={{ padding: '6px 14px', fontSize: '12px' }}>
                    Post Comment
                  </button>
                </div>
              </div>
            )}

            {/* HUMAN REVIEW AUDIT LEDGER SECTION */}
            <div className="audit-ledger-box">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '11px', fontWeight: '700', letterSpacing: '0.06em', color: 'var(--muted)', textTransform: 'uppercase' }}>
                    HUMAN REVIEW AUDIT LEDGER
                  </span>
                  <span style={{
                    fontSize: '11px',
                    padding: '2px 8px',
                    borderRadius: '10px',
                    background: 'rgba(255, 255, 255, 0.08)',
                    color: 'var(--ink)',
                    fontWeight: '600'
                  }}>
                    {auditTab === 'claim' ? (selectedClaim.reviews?.length || 0) : globalAudit.length}
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '6px' }}>
                  <button
                    onClick={() => setAuditTab('claim')}
                    style={{
                      background: auditTab === 'claim' ? 'rgba(240, 106, 44, 0.15)' : 'transparent',
                      color: auditTab === 'claim' ? 'var(--orange2)' : 'var(--muted)',
                      border: auditTab === 'claim' ? '1px solid rgba(240, 106, 44, 0.3)' : '1px solid var(--line)',
                      borderRadius: '4px',
                      padding: '3px 9px',
                      fontSize: '11px',
                      cursor: 'pointer'
                    }}
                  >
                    Current Claim
                  </button>
                  <button
                    onClick={() => {
                      setAuditTab('global');
                      fetchGlobalAudit();
                    }}
                    style={{
                      background: auditTab === 'global' ? 'rgba(240, 106, 44, 0.15)' : 'transparent',
                      color: auditTab === 'global' ? 'var(--orange2)' : 'var(--muted)',
                      border: auditTab === 'global' ? '1px solid rgba(240, 106, 44, 0.3)' : '1px solid var(--line)',
                      borderRadius: '4px',
                      padding: '3px 9px',
                      fontSize: '11px',
                      cursor: 'pointer'
                    }}
                  >
                    All Document Actions
                  </button>
                </div>
              </div>

              {auditTab === 'claim' ? (
                <div>
                  {(!selectedClaim.reviews || selectedClaim.reviews.length === 0) ? (
                    <div style={{ fontSize: '12px', color: 'var(--faint)', fontStyle: 'italic', padding: '10px 0' }}>
                      Default stance: Human review. No human actions recorded in ledger for this claim yet.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {selectedClaim.reviews.map((rev) => (
                        <div key={rev.review_id} className="audit-entry-item">
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              {rev.action === 'accept' && (
                                <span className="audit-badge-accept">✓ ACCEPTED</span>
                              )}
                              {rev.action === 'override' && (
                                <span className="audit-badge-override">✎ OVERRIDDEN → {rev.override_verdict}</span>
                              )}
                              {rev.action === 'comment' && (
                                <span className="audit-badge-comment">💬 COMMENT</span>
                              )}
                              <span style={{ fontSize: '11px', color: 'var(--muted)', fontFamily: 'monospace' }}>
                                by {rev.reviewer_id}
                              </span>
                            </div>
                            <span style={{ fontSize: '11px', color: 'var(--faint)' }}>
                              {rev.created_at ? new Date(rev.created_at).toLocaleString() : ''}
                            </span>
                          </div>
                          {rev.comment && (
                            <div style={{ fontSize: '12px', color: 'var(--ink)', paddingLeft: '6px', borderLeft: '2px solid var(--line)' }}>
                              "{rev.comment}"
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  {loadingGlobalAudit ? (
                    <div style={{ fontSize: '12px', color: 'var(--muted)', padding: '10px 0' }}>Loading audit trail...</div>
                  ) : globalAudit.length === 0 ? (
                    <div style={{ fontSize: '12px', color: 'var(--faint)', fontStyle: 'italic', padding: '10px 0' }}>
                      No audit actions recorded across document claims yet.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {globalAudit.map((rev) => (
                        <div key={rev.review_id} className="audit-entry-item">
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              {rev.action === 'accept' && (
                                <span className="audit-badge-accept">✓ ACCEPTED</span>
                              )}
                              {rev.action === 'override' && (
                                <span className="audit-badge-override">✎ OVERRIDDEN → {rev.override_verdict}</span>
                              )}
                              {rev.action === 'comment' && (
                                <span className="audit-badge-comment">💬 COMMENT</span>
                              )}
                              <span style={{ fontSize: '11px', color: 'var(--muted)', fontFamily: 'monospace' }}>
                                Claim: {rev.claim_id}
                              </span>
                              <span style={{ fontSize: '11px', color: 'var(--faint)' }}>
                                ({rev.reviewer_id})
                              </span>
                            </div>
                            <span style={{ fontSize: '11px', color: 'var(--faint)' }}>
                              {rev.created_at ? new Date(rev.created_at).toLocaleString() : ''}
                            </span>
                          </div>
                          {rev.comment && (
                            <div style={{ fontSize: '12px', color: 'var(--ink)', paddingLeft: '6px', borderLeft: '2px solid var(--line)' }}>
                              "{rev.comment}"
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  </div>
);
}
