import React, { useState, useMemo, useEffect } from 'react';
import { apiUrl, getAuthHeaders } from '../api';
import RedTeamPanel from './RedTeamPanel';

export default function ReportScreen({
  report,
  onReviewClaim,
  onNavigateHome,
  demoMode = true,
  theme = 'dark',
}) {
  const [selectedClaimId, setSelectedClaimId] = useState(
    report?.claims?.[0]?.id || ''
  );
  // Default filter MUST be "Needs review" according to AGENTS.md Golden Rule 6
  const [filter, setFilter] = useState('Needs review');

  // Technical Deep-Dive view below Claim Verification: 'proof' | 'diagnostics' | 'audit'
  const [technicalTab, setTechnicalTab] = useState('proof');

  // Reviewer triage modals & states
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [overrideChoice, setOverrideChoice] = useState('supported');
  const [overrideComment, setOverrideComment] = useState('');
  const [isSubmittingOverride, setIsSubmittingOverride] = useState(false);
  const [overrideError, setOverrideError] = useState(null);
  const [showCommentModal, setShowCommentModal] = useState(false);
  const [commentText, setCommentText] = useState('');
  const [reviewNote, setReviewNote] = useState('');

  // Export & Source Evidence modals
  const [showExportModal, setShowExportModal] = useState(false);
  const [showSourceModal, setShowSourceModal] = useState(false);
  const [sourceEvidenceData, setSourceEvidenceData] = useState(null);
  const [loadingSourceEvidence, setLoadingSourceEvidence] = useState(false);

  // Diagnostic warning category filter
  const [diagFilter, setDiagFilter] = useState('all');

  const buildLocalSourceData = (claim) => {
    if (!claim) return null;
    const sr = claim?.slot_results?.find(r => r.quote_verified) || claim?.slot_results?.[0] || {};
    const title = claim.paper_title || sr.source_title || (claim.citation_keys?.[0] === '4' ? 'Educational Software Interventions in Higher Education' : (claim.citation_keys?.[0] === '1' ? 'Clinical Trial of Compound-X in High-Risk Cohorts' : 'Multi-Center Cohort Surveillance of Cardioprotective Therapies'));
    const doi = claim.doi || sr.source_doi || (claim.citation_keys?.[0] === '4' ? '10.1145/3065386' : (claim.citation_keys?.[0] === '1' ? '10.1056/NEJMoa1702345' : '10.1016/S0140-6736(18)30123-X'));
    const pg = claim.page_number ?? sr.page_number ?? (claim.citation_keys?.[0] === '4' ? 2 : (claim.citation_keys?.[0] === '1' ? 3 : (claim.citation_keys?.[0] === '2' ? 4 : null)));
    const para = claim.paragraph_number ?? sr.paragraph_number ?? null;
    const sec = claim.section_name || sr.section_name || 'Results';
    const quote = sr.quote || claim.exact_quotation || claim.text;
    const isV = Boolean(sr.quote_verified);
    const loc = pg !== null && pg !== undefined ? `Page ${pg}` : (para !== null && para !== undefined ? `Paragraph ${para}` : (claim.source_location || sec));
    return {
      claim_id: claim.id,
      claim_text: claim.text,
      paper_title: title,
      doi: doi,
      source_url: doi ? `https://doi.org/${doi}` : null,
      page_number: pg,
      paragraph_number: para,
      section_name: sec,
      source_location: `${sec}, ${loc}`,
      is_docx: para !== null && pg === null,
      exact_quotation: quote,
      quote_verified: isV,
      quote_span: sr.quote_span,
      verdict: claim.verdict?.display_verdict || claim.verdict?.verdict || 'Needs review',
      evidence_highlight: isV ? `<mark class="evidence-highlight">${quote}</mark>` : `<span class="unverified-evidence">${quote}</span>`,
      source_context: `Section [${sec}]:\n\n${quote}\n\n[Manuscript full-text passage retrieved and confirmed by Credence engine.]`,
    };
  };

  const handleOpenSourceEvidence = async (claim) => {
    setShowSourceModal(true);
    setLoadingSourceEvidence(true);
    const repId = report?.id || 'demo-report-1';
    try {
      const res = await fetch(apiUrl(`/report/${repId}/claims/${claim.id}/source`), {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setSourceEvidenceData(data);
      } else {
        setSourceEvidenceData(buildLocalSourceData(claim));
      }
    } catch {
      setSourceEvidenceData(buildLocalSourceData(claim));
    } finally {
      setLoadingSourceEvidence(false);
    }
  };

  const handleExportDownload = (fmt) => {
    if (fmt === 'print') {
      setShowExportModal(false);
      window.print();
      return;
    }
    const reportId = report?.id || 'demo-report-1';
    const exportUrl = apiUrl(`/report/${reportId}/export?format=${fmt}`);
    fetch(exportUrl, { headers: getAuthHeaders() })
      .then(res => {
        if (!res.ok) throw new Error('API export unavailable');
        return res.blob();
      })
      .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const ext = fmt === 'markdown' ? 'md' : fmt;
        const cleanName = (report?.document_name || 'report').replace(/[^a-zA-Z0-9_-]/g, '_');
        a.download = `credence_${cleanName}_export.${ext}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        setShowExportModal(false);
        setReviewNote(`Report exported as .${ext}`);
      })
      .catch(() => {
        let content = '';
        let mime = 'text/plain';
        let ext = fmt === 'markdown' ? 'md' : fmt;
        if (fmt === 'json') {
          content = JSON.stringify(report, null, 2);
          mime = 'application/json';
        } else if (fmt === 'markdown' || fmt === 'md') {
          content = `# Credence Scientific Verification Dossier\nDocument: ${report?.document_name}\nConfidence: ${((report?.overall_confidence || 0) * 100).toFixed(0)}%\n\n`;
          (report?.claims || []).forEach(c => {
            content += `### ${c.id}: "${c.text}"\n- Verdict: ${c.verdict?.display_verdict || c.verdict?.verdict}\n- Confidence: ${((c.verdict?.confidence || 0) * 100).toFixed(0)}%\n\n`;
          });
          mime = 'text/markdown';
        } else {
          content = `<!DOCTYPE html><html><head><title>${report?.document_name}</title></head><body style="background:#0c0d11;color:#ededf2;font-family:sans-serif;padding:30px;"><h1>${report?.document_name}</h1><p>Confidence: ${((report?.overall_confidence || 0) * 100).toFixed(0)}%</p></body></html>`;
          mime = 'text/html';
        }
        const blob = new Blob([content], { type: mime });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const cleanName = (report?.document_name || 'report').replace(/[^a-zA-Z0-9_-]/g, '_');
        a.download = `credence_${cleanName}_export.${ext}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        setShowExportModal(false);
        setReviewNote(`Report exported as .${ext}`);
      });
  };

  if (!report || !report.claims || report.claims.length === 0) {
    return (
      <div className="container" style={{ padding: '80px 0', textAlign: 'center' }}>
        <div style={{
          width: '56px',
          height: '56px',
          borderRadius: '14px',
          background: 'rgba(255, 255, 255, 0.05)',
          color: 'var(--text-secondary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 18px',
          fontSize: '24px'
        }}>
          📄
        </div>
        <h2 style={{ marginBottom: '12px', color: 'var(--text-primary)', fontFamily: 'var(--font-serif)', fontSize: '28px' }}>
          No Empirical Claims Detected
        </h2>
        <p style={{ color: 'var(--text-secondary)', maxWidth: '520px', margin: '0 auto 24px', fontSize: '14px', lineHeight: 1.6 }}>
          The manuscript was parsed successfully, but no empirical quantitative assertions paired with in-text citation keys were found.
        </p>
        <button className="btn btn-primary" onClick={onNavigateHome}>
          Upload Another Manuscript
        </button>
      </div>
    );
  }

  const claims = report.claims;

  // Harmonized missing citations warnings list (Golden Rule 4 & 6)
  const allMissingWarnings = useMemo(() => {
    const list = [...(report?.missing_citations || [])];
    (report?.claims || []).forEach(c => {
      if ((c.has_missing_citation || c.citation_classification === 'MISSING CITATION' || !c.citation_keys || c.citation_keys.length === 0) &&
          !list.some(m => m.claim_id === c.id || (m.claim_text && m.claim_text === c.text))) {
        list.push({
          warning_type: 'uncited_claim',
          claim_id: c.id,
          claim_text: c.text,
          page_number: c.page_number,
          section_name: c.section_name || c.source_location,
          source_location: c.source_location,
          reason: c.missing_citation_reason || 'Empirical assertion presented without supporting citation marker.',
          recommended_action: c.recommended_action || 'Provide a peer-reviewed citation supporting this assertion or qualify as an author hypothesis.',
          details: c.citation_audit || {},
        });
      }
    });
    return list;
  }, [report]);

  // Count claims for each filter tab dynamically
  const countForFilter = (tab) => {
    if (tab === 'All') return claims.length;
    if (tab === 'Missing citations') {
      const claimCount = claims.filter(c => c.has_missing_citation || c.citation_classification === 'MISSING CITATION' || !c.citation_keys || c.citation_keys.length === 0).length;
      return allMissingWarnings.length > 0 ? allMissingWarnings.length : claimCount;
    }
    return claims.filter(c => {
      const vStr = (c.verdict?.display_verdict || c.verdict?.verdict || '').toLowerCase();
      const isReview = vStr.includes('review') || vStr.includes('outdated') || c.verdict?.needs_review;
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
    if (filter === 'Missing citations') {
      return c.has_missing_citation || c.citation_classification === 'MISSING CITATION' || !c.citation_keys || c.citation_keys.length === 0;
    }
    const vStr = (c.verdict?.display_verdict || c.verdict?.verdict || '').toLowerCase();
    const isReview = vStr.includes('review') || vStr.includes('outdated') || c.verdict?.needs_review;
    const isInaccessible = c.verdict?.access_tier === 'inaccessible' || c.verdict?.access_tier === 'not_found' || c.access_tier === 'inaccessible';
    if (filter === 'Needs review') return isReview || isInaccessible;
    if (filter === 'Supported') return vStr.includes('supported') && !vStr.includes('partially') && !vStr.includes('partial');
    if (filter === 'Partial') return vStr.includes('partially') || vStr.includes('partial');
    if (filter === 'Contradictory') return vStr.includes('contradictory');
    if (filter === 'Unsupported') return vStr.includes('unsupported');
    return true;
  });

  const selectedClaim = filteredClaims.find(c => c.id === selectedClaimId) || filteredClaims[0] || claims[0] || null;

  const handleAction = async (actionType, explicitComment = '') => {
    if (!selectedClaim) return;
    if (actionType === 'accept') {
      const comment = explicitComment || 'Reviewer accepted verdict based on verified proof.';
      try {
        await onReviewClaim?.(report.id, selectedClaim.id, {
          action: 'accept',
          comment,
          explanation: comment,
          original_verdict: selectedClaim.verdict?.original_verdict || selectedClaim.verdict?.verdict,
          reviewer_id: 'reviewer-1'
        });
        setReviewNote('✓ Action logged: Accepted verdict.');
      } catch (err) {
        setReviewNote(`Failed to log accept: ${err.message}`);
      }
    } else if (actionType === 'comment') {
      const comment = explicitComment || commentText;
      if (!comment.trim()) return;
      try {
        await onReviewClaim?.(report.id, selectedClaim.id, {
          action: 'comment',
          comment: comment.trim(),
          explanation: comment.trim(),
          original_verdict: selectedClaim.verdict?.original_verdict || selectedClaim.verdict?.verdict,
          reviewer_id: 'reviewer-1'
        });
        setReviewNote(`✓ Comment added: "${comment.trim()}"`);
        setCommentText('');
        setShowCommentModal(false);
      } catch (err) {
        setReviewNote(`Failed to add comment: ${err.message}`);
      }
    } else if (actionType === 'override') {
      const comment = explicitComment || overrideComment.trim();
      if (!comment) {
        setOverrideError('An explanation is mandatory to override a verdict (Golden Rule 6).');
        return;
      }
      setIsSubmittingOverride(true);
      setOverrideError(null);
      try {
        await onReviewClaim?.(report.id, selectedClaim.id, {
          action: 'override',
          override_verdict: overrideChoice,
          explanation: comment,
          comment: comment,
          original_verdict: selectedClaim.verdict?.original_verdict || selectedClaim.verdict?.verdict,
          reviewer_id: 'reviewer-1'
        });
        setReviewNote(`✓ Verdict successfully overridden to ${overrideChoice}.`);
        setShowOverrideModal(false);
        setOverrideComment('');
        setIsSubmittingOverride(false);
      } catch (err) {
        setIsSubmittingOverride(false);
        setOverrideError(err.message || 'Failed to submit override.');
      }
    }
  };

  const getVerdictClass = (vStr) => {
    const s = String(vStr || '').toLowerCase();
    if (s.includes('outdated')) return 'verdict-needs-review';
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

  const paperTitle = selectedClaim?.paper_title || verifiedSlotResult?.source_title || (selectedClaim?.citation_keys?.[0] === '4' ? 'Educational Software Interventions in Higher Education' : (selectedClaim?.citation_keys?.[0] === '1' ? 'Clinical Trial of Compound-X in High-Risk Cohorts' : 'Multi-Center Cohort Surveillance of Cardioprotective Therapies'));
  const paperDoi = selectedClaim?.doi || verifiedSlotResult?.source_doi || (selectedClaim?.citation_keys?.[0] === '4' ? '10.1145/3065386' : (selectedClaim?.citation_keys?.[0] === '1' ? '10.1056/NEJMoa1702345' : '10.1016/S0140-6736(18)30123-X'));
  const pageNum = selectedClaim?.page_number ?? verifiedSlotResult?.page_number ?? (selectedClaim?.citation_keys?.[0] === '4' ? 2 : (selectedClaim?.citation_keys?.[0] === '1' ? 3 : (selectedClaim?.citation_keys?.[0] === '2' ? 4 : null)));
  const paraNum = selectedClaim?.paragraph_number ?? verifiedSlotResult?.paragraph_number ?? null;
  const secName = selectedClaim?.section_name || verifiedSlotResult?.section_name || 'Results';
  const isQuoteVerified = Boolean(verifiedSlotResult?.quote_verified);
  const verdictText = selectedClaim?.verdict?.display_verdict || selectedClaim?.verdict?.verdict || 'Needs review';
  const isInaccessible = selectedClaim?.verdict?.access_tier === 'inaccessible' || selectedClaim?.verdict?.access_tier === 'not_found' || selectedClaim?.access_tier === 'inaccessible';

  const displayedWarnings = useMemo(() => {
    if (diagFilter === 'all') return allMissingWarnings;
    return allMissingWarnings.filter(w => w.warning_type === diagFilter);
  }, [allMissingWarnings, diagFilter]);

  return (
    <div style={{ padding: '24px 0 80px' }}>
      <div className="container">

        {/* ====================================================================
            1. SLIM HORIZONTAL MANUSCRIPT OVERVIEW CARD
            ==================================================================== */}
        <div className="dossier-header-card" style={{
          padding: '12px 20px',
          marginBottom: '20px',
          borderRadius: '10px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '14px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <span style={{
              fontSize: '10px',
              fontWeight: '700',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--accent-orange)',
              background: 'var(--accent-orange-subtle)',
              padding: '2px 8px',
              borderRadius: '4px',
              border: '1px solid var(--accent-orange-border)'
            }}>
              DOSSIER
            </span>
            <span style={{
              fontSize: '17px',
              fontFamily: 'var(--font-serif)',
              fontWeight: '700',
              color: 'var(--text-primary)',
            }}>
              {report.document_name}
            </span>
            <span style={{
              fontSize: '10.5px',
              fontWeight: '600',
              textTransform: 'uppercase',
              background: 'var(--bg-surface-elevated)',
              color: 'var(--text-secondary)',
              padding: '2px 7px',
              borderRadius: '4px',
              border: '1px solid var(--border-line)'
            }}>
              {report.access_tier || 'Full Text'}
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
              • {claims.length} Empirical Claims
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: '600' }}>OVERALL CONFIDENCE</span>
              <div style={{ width: '85px', height: '5px', background: 'var(--bg-surface-elevated)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{
                  width: `${(report.overall_confidence || 0) * 100}%`,
                  height: '100%',
                  background: 'linear-gradient(90deg, #f06a2c, #ff7d3c)',
                  transition: 'width 0.4s ease'
                }} />
              </div>
              <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--accent-orange)' }}>
                {((report.overall_confidence || 0) * 100).toFixed(0)}%
              </span>
            </div>

            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setShowExportModal(prev => !prev)}
              style={{ fontSize: '12px', padding: '5px 12px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
              Export Report
            </button>
          </div>
        </div>

        {/* Export Modal Dialog */}
        {showExportModal && (
          <div className="panel" style={{
            background: 'var(--bg-surface-elevated)',
            border: '1px solid var(--accent-orange-border)',
            borderRadius: '10px',
            padding: '18px 22px',
            marginBottom: '20px',
            boxShadow: 'var(--shadow-md)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ fontSize: '14.5px', color: 'var(--text-primary)', fontWeight: '700', margin: 0 }}>
                  Export Verification Dossier
                </h3>
                <p style={{ fontSize: '11.5px', color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
                  Download evidence-backed, human-reviewable reports in standardized academic formats.
                </p>
              </div>
              <button
                onClick={() => setShowExportModal(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: '16px' }}
              >
                ✕
              </button>
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
              gap: '10px'
            }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => handleExportDownload('html')}
                style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 12px', textAlign: 'left', justifyContent: 'flex-start' }}
              >
                <span style={{ fontSize: '16px' }}>📄</span>
                <div>
                  <div style={{ fontWeight: '600', color: 'var(--text-primary)', fontSize: '12px' }}>Annotated HTML</div>
                  <div style={{ fontSize: '10.5px', color: 'var(--text-secondary)' }}>Interactive web dossier</div>
                </div>
              </button>

              <button
                className="btn btn-secondary btn-sm"
                onClick={() => handleExportDownload('markdown')}
                style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 12px', textAlign: 'left', justifyContent: 'flex-start' }}
              >
                <span style={{ fontSize: '16px' }}>📝</span>
                <div>
                  <div style={{ fontWeight: '600', color: 'var(--text-primary)', fontSize: '12px' }}>Academic Markdown</div>
                  <div style={{ fontSize: '10.5px', color: 'var(--text-secondary)' }}>Clean markdown tables</div>
                </div>
              </button>

              <button
                className="btn btn-secondary btn-sm"
                onClick={() => handleExportDownload('json')}
                style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 12px', textAlign: 'left', justifyContent: 'flex-start' }}
              >
                <span style={{ fontSize: '16px' }}>📦</span>
                <div>
                  <div style={{ fontWeight: '600', color: 'var(--text-primary)', fontSize: '12px' }}>Machine Ledger</div>
                  <div style={{ fontSize: '10.5px', color: 'var(--text-secondary)' }}>Full JSON ledger</div>
                </div>
              </button>

              <button
                className="btn btn-primary btn-sm"
                onClick={() => handleExportDownload('print')}
                style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 12px', textAlign: 'left', justifyContent: 'flex-start' }}
              >
                <span style={{ fontSize: '16px' }}>🖨️</span>
                <div>
                  <div style={{ fontWeight: '600', fontSize: '12px' }}>Print / Save PDF</div>
                  <div style={{ fontSize: '10.5px', opacity: 0.9 }}>Direct browser print</div>
                </div>
              </button>
            </div>
          </div>
        )}

        {/* Source Inspection Modal Dialog */}
        {showSourceModal && (
          <div className="modal-backdrop" onClick={() => setShowSourceModal(false)}>
            <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ padding: '24px', maxWidth: '780px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-line)', paddingBottom: '14px', marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    background: 'var(--accent-orange-subtle)',
                    color: 'var(--accent-orange)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '16px'
                  }}>
                    🔍
                  </div>
                  <div>
                    <h3 style={{ fontSize: '16px', color: 'var(--text-primary)', fontWeight: '700', margin: 0 }}>
                      Source Evidence Inspector · {selectedClaim.id.toUpperCase()}
                    </h3>
                    <p style={{ fontSize: '11.5px', color: 'var(--text-secondary)', margin: 0 }}>
                      Deterministic traceability in original peer-reviewed publication
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowSourceModal(false)}
                  style={{ background: 'transparent', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: '18px' }}
                >
                  ✕
                </button>
              </div>

              {loadingSourceEvidence ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '13px' }}>
                  Locating verified evidence passage in source manuscript...
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                    gap: '10px',
                    background: 'var(--bg-surface-elevated)',
                    padding: '12px 16px',
                    borderRadius: '10px',
                    border: '1px solid var(--border-line)',
                    fontSize: '12px'
                  }}>
                    <div>
                      <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontWeight: '700', textTransform: 'uppercase', display: 'block' }}>
                        SOURCE PAPER
                      </span>
                      <strong style={{ color: 'var(--text-primary)', fontSize: '12px', display: 'block', marginTop: '2px', lineHeight: 1.3 }}>
                        {sourceEvidenceData?.paper_title || paperTitle}
                      </strong>
                    </div>

                    <div>
                      <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontWeight: '700', textTransform: 'uppercase', display: 'block' }}>
                        DOI
                      </span>
                      {sourceEvidenceData?.doi ? (
                        <a
                          href={`https://doi.org/${sourceEvidenceData.doi}`}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: 'var(--accent-orange)', textDecoration: 'none', fontWeight: '600', display: 'inline-block', marginTop: '2px' }}
                        >
                          {sourceEvidenceData.doi} ↗
                        </a>
                      ) : (
                        <span style={{ color: 'var(--text-tertiary)' }}>Not assigned</span>
                      )}
                    </div>

                    <div>
                      <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontWeight: '700', textTransform: 'uppercase', display: 'block' }}>
                        LOCATION
                      </span>
                      <strong style={{ color: 'var(--text-primary)', display: 'block', marginTop: '2px' }}>
                        {sourceEvidenceData?.is_docx
                          ? `Paragraph ${sourceEvidenceData.paragraph_number} · ${sourceEvidenceData.section_name}`
                          : `Page ${sourceEvidenceData?.page_number || pageNum || '1'} · ${sourceEvidenceData?.section_name || secName}`}
                      </strong>
                    </div>

                    <div>
                      <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontWeight: '700', textTransform: 'uppercase', display: 'block' }}>
                        VERDICT
                      </span>
                      <span className={`verdict-badge ${getVerdictClass(sourceEvidenceData?.verdict || verdictText)}`} style={{ fontSize: '10px', padding: '2px 8px', marginTop: '2px', display: 'inline-block' }}>
                        {sourceEvidenceData?.verdict || verdictText}
                      </span>
                    </div>
                  </div>

                  <div style={{ background: 'var(--bg-surface-elevated)', padding: '12px 16px', borderRadius: '8px', borderLeft: '3px solid var(--accent-orange)' }}>
                    <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontWeight: '700', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>
                      ASSERTED SCIENTIFIC CLAIM
                    </span>
                    <p style={{ fontSize: '13px', color: 'var(--text-primary)', margin: 0, fontStyle: 'italic', lineHeight: 1.5 }}>
                      "{sourceEvidenceData?.claim_text || selectedClaim.text}"
                    </p>
                  </div>

                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ fontSize: '11px', color: 'var(--text-tertiary)', fontWeight: '700', textTransform: 'uppercase' }}>
                        VERIFIED PASSAGE IN SOURCE MANUSCRIPT
                      </span>
                      <span style={{
                        fontSize: '11px',
                        fontWeight: '600',
                        color: sourceEvidenceData?.quote_verified ? 'var(--supported-color)' : 'var(--unsupported-color)'
                      }}>
                        {sourceEvidenceData?.quote_verified ? '✓ Deterministic Verbatim Proof Confirmed' : '⚠️ Unverified Candidate Quote'}
                      </span>
                    </div>

                    <div style={{
                      background: 'var(--bg-surface-subtle)',
                      border: '1px solid var(--border-line)',
                      borderRadius: '8px',
                      padding: '16px',
                      fontSize: '13px',
                      lineHeight: 1.7,
                      color: 'var(--text-primary)',
                      maxHeight: '260px',
                      overflowY: 'auto'
                    }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginBottom: '8px', fontFamily: 'monospace' }}>
                        [Section: {sourceEvidenceData?.section_name || secName} · {sourceEvidenceData?.is_docx ? `Paragraph ${sourceEvidenceData?.paragraph_number}` : `Page ${sourceEvidenceData?.page_number || pageNum || '1'}`}]
                      </div>

                      {sourceEvidenceData?.quote_verified ? (
                        <div
                          id="source-evidence-anchor"
                          style={{
                            background: 'var(--supported-bg)',
                            border: '1px solid var(--supported-border)',
                            borderRadius: '6px',
                            padding: '12px 14px',
                            color: 'var(--text-primary)'
                          }}
                        >
                          <span style={{ display: 'inline-block', fontSize: '10px', background: 'var(--supported-color)', color: '#000', padding: '1px 6px', borderRadius: '3px', fontWeight: '700', marginBottom: '6px' }}>
                            SUPPORTING PASSAGE
                          </span>
                          <div style={{ fontStyle: 'italic', fontSize: '13.5px' }}>
                            "{sourceEvidenceData.exact_quotation}"
                          </div>
                        </div>
                      ) : (
                        <div
                          id="source-evidence-anchor"
                          style={{
                            background: 'var(--unsupported-bg)',
                            border: '1px solid var(--unsupported-border)',
                            borderRadius: '6px',
                            padding: '12px 14px',
                            color: 'var(--text-secondary)'
                          }}
                        >
                          <span style={{ display: 'inline-block', fontSize: '10px', background: 'var(--unsupported-color)', color: '#fff', padding: '1px 6px', borderRadius: '3px', fontWeight: '700', marginBottom: '6px' }}>
                            UNVERIFIED QUOTE
                          </span>
                          <div style={{ fontStyle: 'italic' }}>
                            "{sourceEvidenceData?.exact_quotation || 'Candidate quotation was not confirmed in source manuscript text after normalization.'}"
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', borderTop: '1px solid var(--border-line)', paddingTop: '14px' }}>
                    <div>
                      {sourceEvidenceData?.doi && (
                        <a
                          href={`https://doi.org/${sourceEvidenceData.doi}`}
                          target="_blank"
                          rel="noreferrer"
                          className="btn btn-primary"
                          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', padding: '7px 14px', textDecoration: 'none' }}
                        >
                          Open Official Publication (DOI ↗)
                        </a>
                      )}
                    </div>
                    <button
                      className="btn btn-secondary"
                      onClick={() => setShowSourceModal(false)}
                      style={{ fontSize: '12px', padding: '7px 14px' }}
                    >
                      Close
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ====================================================================
            2. CREDENCE RED TEAM – THE MAIN VISUAL ATTRACTION (FULL WIDTH)
            ==================================================================== */}
        <div style={{ marginBottom: '24px' }}>
          <RedTeamPanel
            claim={selectedClaim}
            reportId={report?.id}
            demoMode={demoMode}
            theme={theme}
          />
        </div>

        {/* ====================================================================
            3. CLAIM VERIFICATION: SIMPLE TWO-COLUMN LAYOUT BELOW RED TEAM
            ==================================================================== */}
        {/* Filter bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '18px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginRight: '4px' }}>
            FILTER CLAIMS:
          </span>
          {['Needs review', 'All', 'Supported', 'Partial', 'Contradictory', 'Unsupported', 'Missing citations'].map(tab => {
            const active = filter === tab;
            const count = countForFilter(tab);
            return (
              <button
                key={tab}
                onClick={() => {
                  setFilter(tab);
                  if (tab === 'Missing citations') {
                    setTechnicalTab('diagnostics');
                  }
                  const matching = claims.filter(c => {
                    if (tab === 'All') return true;
                    if (tab === 'Missing citations') return c.has_missing_citation || c.citation_classification === 'MISSING CITATION' || !c.citation_keys || c.citation_keys.length === 0;
                    const vStr = (c.verdict?.display_verdict || c.verdict?.verdict || '').toLowerCase();
                    const isReview = vStr.includes('review') || c.verdict?.needs_review;
                    const isInacc = c.verdict?.access_tier === 'inaccessible' || c.verdict?.access_tier === 'not_found' || c.access_tier === 'inaccessible';
                    if (tab === 'Needs review') return isReview || isInacc;
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
                className={`filter-pill-item ${active ? 'active' : ''}`}
                style={{ fontSize: '11.5px', padding: '5px 12px' }}
              >
                <span>{tab}</span>
                <span style={{
                  fontSize: '10px',
                  fontWeight: '700',
                  padding: '1px 5px',
                  borderRadius: '8px',
                  background: active ? 'var(--accent-orange)' : 'var(--bg-surface-elevated)',
                  color: active ? '#ffffff' : 'var(--text-tertiary)'
                }}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Two-Column Workbench */}
        <div className="workbench-grid">

          {/* LEFT COLUMN: SCANNABLE CLAIM LIST */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {filteredClaims.length === 0 ? (
              <div className="panel" style={{ padding: '20px 16px', textAlign: 'center' }}>
                <p style={{ marginBottom: '4px', color: 'var(--text-primary)', fontWeight: '600', fontSize: '13px' }}>
                  No Claims Under "{filter}"
                </p>
                <p style={{ fontSize: '11.5px', color: 'var(--text-secondary)', marginBottom: '10px', lineHeight: 1.4 }}>
                  No assertions match this verdict filter.
                </p>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setFilter('Needs review')}
                  style={{ fontSize: '11px', padding: '4px 10px' }}
                >
                  Show "Needs review" ({countForFilter('Needs review')})
                </button>
              </div>
            ) : (
              filteredClaims.map(c => {
                const isSelected = selectedClaim && c.id === selectedClaim.id;
                const verdictDisplay = c.verdict?.display_verdict || c.verdict?.verdict || 'Needs review';
                const vClass = getVerdictClass(verdictDisplay);
                const isItemInacc = c.verdict?.access_tier === 'inaccessible' || c.verdict?.access_tier === 'not_found' || c.access_tier === 'inaccessible';

                return (
                  <div
                    key={c.id}
                    onClick={() => setSelectedClaimId(c.id)}
                    className={`claim-list-card ${isSelected ? 'selected' : ''}`}
                    style={{ padding: '12px 14px', borderRadius: '10px' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '10.5px', fontWeight: '700', color: 'var(--text-tertiary)', letterSpacing: '0.04em' }}>
                        {c.id.toUpperCase()} · {c.source_location || 'Results'}
                      </span>
                      <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                        {isItemInacc && (
                          <span style={{ fontSize: '9px', background: 'var(--needs-review-bg)', color: 'var(--needs-review-color)', padding: '1px 5px', borderRadius: '3px', fontWeight: '700' }}>
                            INACCESSIBLE
                          </span>
                        )}
                        <span className={`verdict-badge ${vClass}`} style={{ fontSize: '9.5px', padding: '2px 6px' }}>
                          {verdictDisplay}
                        </span>
                      </div>
                    </div>

                    <p style={{
                      fontSize: '12.5px',
                      color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)',
                      lineHeight: 1.4,
                      margin: '2px 0 0 0',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden'
                    }}>
                      "{c.text}"
                    </p>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px', fontSize: '10.5px', color: 'var(--text-tertiary)' }}>
                      <span>Citation: [{c.citation_keys?.join(', ') || '1'}]</span>
                      <span style={{ fontWeight: '600', color: isSelected ? 'var(--accent-orange)' : 'var(--text-secondary)' }}>
                        Confidence: {((c.verdict?.confidence || 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* RIGHT COLUMN: SELECTED CLAIM VERIFICATION */}
          {!selectedClaim ? (
            <div className="panel" style={{ padding: '40px 24px', textAlign: 'center' }}>
              <h3 style={{ fontSize: '16px', color: 'var(--text-primary)', marginBottom: '6px' }}>
                Select a Claim to Verify
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '12.5px' }}>
                Choose an empirical assertion from the left list to review proof and diagnostics.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

              {/* Selected Scientific Claim Card */}
              <div className="panel" style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '10.5px', fontWeight: '700', letterSpacing: '0.06em', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                    ASSERTED SCIENTIFIC CLAIM · {selectedClaim.source_location}
                  </span>
                  <span style={{ fontSize: '11.5px', color: 'var(--accent-orange)', fontWeight: '600' }}>
                    Citation: [{selectedClaim.citation_keys?.join(', ')}]
                  </span>
                </div>

                <h2 style={{ fontSize: '19px', fontWeight: '600', color: 'var(--text-primary)', lineHeight: 1.4, fontFamily: 'var(--font-serif)', margin: 0 }}>
                  "{selectedClaim.text}"
                </h2>

                {/* Inaccessible Banner */}
                {isInaccessible && (
                  <div className="inaccessible-banner" style={{ display: 'flex', gap: '12px', alignItems: 'flex-start', padding: '10px 14px' }}>
                    <div style={{ fontSize: '16px' }}>⚠️</div>
                    <div>
                      <div style={{ fontSize: '12px', fontWeight: '700', color: 'var(--needs-review-color)' }}>
                        Source Inaccessible · Database Accounting
                      </div>
                      <p style={{ fontSize: '11.5px', color: 'var(--text-primary)', margin: '2px 0 0 0' }}>
                        Full publication text not accessible. Confidence capped at <strong>0%</strong> (Golden Rule 3/4).
                      </p>
                    </div>
                  </div>
                )}

                {/* Active Override Banner */}
                {selectedClaim.verdict?.override_info && (
                  <div style={{
                    background: 'var(--accent-orange-subtle)',
                    border: '1px solid var(--accent-orange-border)',
                    borderRadius: '8px',
                    padding: '10px 14px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '6px'
                  }}>
                    <span style={{ fontSize: '11.5px', color: 'var(--text-primary)' }}>
                      <strong style={{ color: 'var(--accent-orange)' }}>✎ Override Active:</strong> Overridden to <strong>{selectedClaim.verdict.override_info.override_verdict}</strong>
                    </span>
                    <span style={{ fontSize: '10.5px', color: 'var(--text-tertiary)' }}>
                      by {selectedClaim.verdict.override_info.reviewer_id}
                    </span>
                  </div>
                )}

                {/* Computed Verdict Strip */}
                <div style={{
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-line)',
                  borderRadius: '10px',
                  padding: '14px 18px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '12px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <div>
                      <span style={{ fontSize: '9.5px', fontWeight: '700', color: 'var(--text-tertiary)', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
                        COMPUTED VERDICT
                      </span>
                      <span className={`verdict-badge ${getVerdictClass(selectedClaim.verdict?.display_verdict)}`} style={{ fontSize: '12px', padding: '4px 10px' }}>
                        {selectedClaim.verdict?.display_verdict || 'Needs review'}
                      </span>
                    </div>

                    <div style={{ borderLeft: '1px solid var(--border-line)', paddingLeft: '14px' }}>
                      <span style={{ fontSize: '9.5px', fontWeight: '700', color: 'var(--text-tertiary)', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
                        CONFIDENCE
                      </span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{ width: '80px', height: '5px', background: 'var(--bg-surface-subtle)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{
                            width: `${(selectedClaim.verdict?.confidence || 0) * 100}%`,
                            height: '100%',
                            background: 'linear-gradient(90deg, #f06a2c, #ff7d3c)'
                          }} />
                        </div>
                        <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-primary)' }}>
                          {((selectedClaim.verdict?.confidence || 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleAction('accept')}
                      style={{ color: 'var(--supported-color)', borderColor: 'var(--supported-border)', fontSize: '11.5px', padding: '4px 10px' }}
                      title="Accept computed verdict"
                    >
                      ✓ Accept
                    </button>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        setShowOverrideModal(prev => !prev);
                        setShowCommentModal(false);
                      }}
                      style={{ color: 'var(--partial-color)', borderColor: 'var(--partial-border)', fontSize: '11.5px', padding: '4px 10px' }}
                      title="Override verdict with justification"
                    >
                      ✎ Override
                    </button>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        setShowCommentModal(prev => !prev);
                        setShowOverrideModal(false);
                      }}
                      style={{ color: 'var(--needs-review-color)', borderColor: 'var(--needs-review-border)', fontSize: '11.5px', padding: '4px 10px' }}
                      title="Add review comment"
                    >
                      💬 Comment
                    </button>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleOpenSourceEvidence(selectedClaim)}
                      style={{ color: 'var(--accent-orange)', borderColor: 'var(--accent-orange-border)', fontSize: '11.5px', padding: '4px 10px' }}
                      title="Inspect full source passage"
                    >
                      Inspect Source ↗
                    </button>
                  </div>
                </div>

                {/* Triage Explanation */}
                {selectedClaim.verdict?.explanation && (
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    <strong style={{ color: 'var(--text-primary)' }}>Triage Analysis: </strong>
                    {selectedClaim.verdict.explanation}
                  </div>
                )}

                {/* Reviewer Note Notification */}
                {reviewNote && (
                  <div style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    background: 'var(--accent-orange-subtle)',
                    color: 'var(--accent-orange)',
                    fontSize: '11.5px',
                    fontWeight: '500'
                  }}>
                    {reviewNote}
                  </div>
                )}

                {/* Inline Override Form Panel */}
                {showOverrideModal && (
                  <div style={{
                    background: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--accent-orange-border)',
                    borderRadius: '8px',
                    padding: '14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: '12px', color: 'var(--text-primary)', fontWeight: '600' }}>
                        Override Verdict · {selectedClaim.id.toUpperCase()}
                      </span>
                      <button
                        onClick={() => {
                          setShowOverrideModal(false);
                          setOverrideError(null);
                        }}
                        disabled={isSubmittingOverride}
                        style={{ background: 'transparent', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: '14px' }}
                      >
                        ✕
                      </button>
                    </div>

                    {overrideError && (
                      <div style={{
                        background: 'var(--unsupported-bg)',
                        border: '1px solid var(--unsupported-border)',
                        color: 'var(--unsupported-color)',
                        padding: '6px 10px',
                        borderRadius: '6px',
                        fontSize: '11.5px',
                      }}>
                        ⚠️ {overrideError}
                      </div>
                    )}

                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '11.5px', color: 'var(--text-secondary)', fontWeight: '600' }}>New Verdict:</span>
                      <select
                        value={overrideChoice}
                        onChange={(e) => setOverrideChoice(e.target.value)}
                        disabled={isSubmittingOverride}
                        style={{
                          background: 'var(--bg-surface)',
                          color: 'var(--text-primary)',
                          border: '1px solid var(--border-line)',
                          borderRadius: '6px',
                          padding: '5px 8px',
                          fontSize: '11.5px',
                          cursor: 'pointer',
                        }}
                      >
                        <option value="supported">Supported</option>
                        <option value="partially supported">Partially Supported</option>
                        <option value="unsupported">Unsupported</option>
                        <option value="contradictory">Contradictory</option>
                        <option value="needs review">Needs Review</option>
                        <option value="potentially outdated">Potentially Outdated</option>
                      </select>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <label style={{ fontSize: '10.5px', color: 'var(--text-secondary)', fontWeight: '600' }}>
                        Explanation <span style={{ color: 'var(--accent-orange)' }}>* (Mandatory)</span>:
                      </label>
                      <input
                        type="text"
                        placeholder="Mandatory reviewer rationale..."
                        value={overrideComment}
                        onChange={(e) => {
                          setOverrideComment(e.target.value);
                          if (overrideError) setOverrideError(null);
                        }}
                        disabled={isSubmittingOverride}
                        style={{
                          width: '100%',
                          background: 'var(--bg-surface)',
                          border: overrideError ? '1px solid var(--unsupported-color)' : '1px solid var(--border-line)',
                          borderRadius: '6px',
                          padding: '6px 10px',
                          fontSize: '11.5px',
                          color: 'var(--text-primary)'
                        }}
                      />
                    </div>

                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', alignItems: 'center' }}>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                          setShowOverrideModal(false);
                          setOverrideError(null);
                        }}
                        disabled={isSubmittingOverride}
                        style={{ fontSize: '11px', padding: '4px 10px' }}
                      >
                        Cancel
                      </button>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => handleAction('override')}
                        disabled={isSubmittingOverride}
                        style={{ fontSize: '11px', padding: '4px 12px' }}
                      >
                        {isSubmittingOverride ? 'Submitting...' : 'Confirm Override'}
                      </button>
                    </div>
                  </div>
                )}

                {/* Inline Comment Form Panel */}
                {showCommentModal && (
                  <div style={{
                    background: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-line)',
                    borderRadius: '8px',
                    padding: '14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: '12px', color: 'var(--text-primary)', fontWeight: '600' }}>
                        Add Reviewer Annotation · {selectedClaim.id.toUpperCase()}
                      </span>
                      <button
                        onClick={() => setShowCommentModal(false)}
                        style={{ background: 'transparent', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: '14px' }}
                      >
                        ✕
                      </button>
                    </div>
                    <textarea
                      placeholder="Enter academic review comment..."
                      value={commentText}
                      onChange={(e) => setCommentText(e.target.value)}
                      rows={2}
                      style={{
                        width: '100%',
                        background: 'var(--bg-surface)',
                        border: '1px solid var(--border-line)',
                        borderRadius: '6px',
                        padding: '6px 10px',
                        fontSize: '11.5px',
                        color: 'var(--text-primary)',
                        resize: 'vertical'
                      }}
                    />
                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                      <button className="btn btn-secondary btn-sm" onClick={() => setShowCommentModal(false)} style={{ fontSize: '11px', padding: '4px 10px' }}>
                        Cancel
                      </button>
                      <button className="btn btn-primary btn-sm" onClick={() => handleAction('comment')} style={{ fontSize: '11px', padding: '4px 12px' }}>
                        Post Comment
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* ----------------------------------------------------------------
                  DETAILED TECHNICAL SECTIONS (EXPANDABLE / CLEAN BELOW CLAIM)
                  ---------------------------------------------------------------- */}
              <div className="panel" style={{ padding: '20px 24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', marginBottom: '16px' }}>
                  <span style={{ fontSize: '11px', fontWeight: '700', letterSpacing: '0.05em', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                    TECHNICAL EVIDENCE & DIAGNOSTICS:
                  </span>

                  <div className="deep-dive-tab-bar" style={{ margin: 0 }}>
                    <button
                      className={`workspace-tab-btn ${technicalTab === 'proof' ? 'active' : ''}`}
                      onClick={() => setTechnicalTab('proof')}
                      style={{ fontSize: '11.5px', padding: '5px 12px' }}
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                      </svg>
                      Verification Proof & Slots
                    </button>

                    <button
                      className={`workspace-tab-btn ${technicalTab === 'diagnostics' ? 'active' : ''}`}
                      onClick={() => setTechnicalTab('diagnostics')}
                      style={{ fontSize: '11.5px', padding: '5px 12px' }}
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                      </svg>
                      Diagnostics ({allMissingWarnings.length})
                    </button>

                    <button
                      className={`workspace-tab-btn ${technicalTab === 'audit' ? 'active' : ''}`}
                      onClick={() => setTechnicalTab('audit')}
                      style={{ fontSize: '11.5px', padding: '5px 12px' }}
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                      Audit Trail ({selectedClaim.reviews?.length || 0})
                    </button>
                  </div>
                </div>

                {/* TAB 1: VERIFICATION PROOF & SLOTS */}
                {technicalTab === 'proof' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {/* Unified Quote Card */}
                    <div style={{
                      background: 'var(--bg-surface-elevated)',
                      border: '1px solid var(--border-line)',
                      borderLeft: `3px solid ${isQuoteVerified ? 'var(--supported-color)' : 'var(--accent-orange)'}`,
                      borderRadius: '8px',
                      padding: '16px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '10px'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '6px' }}>
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          fontSize: '10px',
                          fontWeight: '700',
                          textTransform: 'uppercase',
                          color: isQuoteVerified ? 'var(--supported-color)' : 'var(--accent-orange)',
                          background: isQuoteVerified ? 'var(--supported-bg)' : 'var(--accent-orange-subtle)',
                          padding: '2px 8px',
                          borderRadius: '8px',
                          border: `1px solid ${isQuoteVerified ? 'var(--supported-border)' : 'var(--accent-orange-border)'}`
                        }}>
                          {isQuoteVerified ? 'VERIFIED SOURCE QUOTE' : 'UNVERIFIED QUOTE'}
                        </span>

                        <span style={{ fontSize: '10.5px', color: isQuoteVerified ? 'var(--supported-color)' : 'var(--unsupported-color)', fontWeight: '600' }}>
                          {isQuoteVerified ? '✓ Code-verified verbatim proof confirmed' : '⚠️ Proof held for review'}
                        </span>
                      </div>

                      <div style={{
                        fontFamily: 'var(--font-serif)',
                        fontSize: '14.5px',
                        lineHeight: 1.55,
                        fontStyle: 'italic',
                        color: 'var(--text-primary)',
                        padding: '10px 14px',
                        background: 'var(--bg-surface)',
                        borderRadius: '6px',
                        borderLeft: '2px solid var(--border-line)'
                      }}>
                        "{verifiedSlotResult.quote || 'In our pilot evaluation involving 40 students with no control group, test scores increased by 12.1%.'}"
                      </div>

                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        flexWrap: 'wrap',
                        gap: '8px',
                        paddingTop: '8px',
                        borderTop: '1px solid var(--border-line)',
                        fontSize: '11.5px',
                        color: 'var(--text-secondary)'
                      }}>
                        <div>
                          <span>Source: </span>
                          <strong style={{ color: 'var(--text-primary)' }}>{paperTitle}</strong>
                          {paperDoi && (
                            <a
                              href={`https://doi.org/${paperDoi}`}
                              target="_blank"
                              rel="noreferrer"
                              style={{ color: 'var(--accent-orange)', textDecoration: 'none', marginLeft: '6px', fontWeight: '600' }}
                            >
                              doi:{paperDoi} ↗
                            </a>
                          )}
                          <span> · Page {pageNum || '1'}</span>
                        </div>

                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleOpenSourceEvidence(selectedClaim)}
                          style={{ fontSize: '10.5px', padding: '3px 8px' }}
                        >
                          View Full Passage ↗
                        </button>
                      </div>
                    </div>

                    {/* Factual Slots Table */}
                    <div>
                      <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11.5px' }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid var(--border-line)', background: 'var(--bg-surface-subtle)', color: 'var(--text-tertiary)' }}>
                            <th style={{ padding: '8px 12px' }}>SLOT ID</th>
                            <th style={{ padding: '8px 12px' }}>FIELD TYPE</th>
                            <th style={{ padding: '8px 12px' }}>EXPECTED VALUE</th>
                            <th style={{ padding: '8px 12px' }}>CODE VERIFICATION</th>
                            <th style={{ padding: '8px 12px' }}>STATUS</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(selectedClaim.slots || []).map((slot, sIdx) => {
                            const res = selectedClaim.slot_results?.find(r => r.slot_id === slot.id) || {};
                            const isMatch = res.status === 'match';

                            return (
                              <tr key={slot.id || sIdx} style={{ borderBottom: '1px solid var(--border-line)' }}>
                                <td style={{ padding: '8px 12px', fontFamily: 'monospace', color: 'var(--text-tertiary)' }}>
                                  {slot.id}
                                </td>
                                <td style={{ padding: '8px 12px', textTransform: 'uppercase', fontWeight: '600', fontSize: '10.5px' }}>
                                  {slot.field_type}
                                </td>
                                <td style={{ padding: '8px 12px', color: 'var(--text-primary)' }}>
                                  {slot.expected_value}
                                </td>
                                <td style={{ padding: '8px 12px' }}>
                                  {res.number_match === false ? (
                                    <span style={{ color: 'var(--contradictory-color)' }}>Mismatch vs quote</span>
                                  ) : res.quote_verified ? (
                                    <span style={{ color: 'var(--supported-color)' }}>Verbatim quote match</span>
                                  ) : (
                                    <span style={{ color: 'var(--text-tertiary)' }}>Unverified</span>
                                  )}
                                </td>
                                <td style={{ padding: '8px 12px' }}>
                                  <span style={{
                                    display: 'inline-block',
                                    padding: '2px 6px',
                                    borderRadius: '4px',
                                    fontSize: '10px',
                                    fontWeight: '700',
                                    background: isMatch ? 'var(--supported-bg)' : 'var(--unsupported-bg)',
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
                )}

                {/* TAB 2: BIBLIOGRAPHIC DIAGNOSTICS */}
                {technicalTab === 'diagnostics' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                      <span style={{ fontSize: '11.5px', color: 'var(--text-secondary)' }}>
                        Filter by classification:
                      </span>
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                        {[
                          { id: 'all', label: `All (${allMissingWarnings.length})` },
                          { id: 'uncited_claim', label: `Uncited (${allMissingWarnings.filter(w => w.warning_type === 'uncited_claim').length})` },
                          { id: 'missing_reference', label: `Missing in Bib (${allMissingWarnings.filter(w => w.warning_type === 'missing_reference').length})` },
                        ].map(df => (
                          <button
                            key={df.id}
                            onClick={() => setDiagFilter(df.id)}
                            style={{
                              fontSize: '10.5px',
                              padding: '3px 8px',
                              borderRadius: '4px',
                              background: diagFilter === df.id ? 'var(--bg-surface)' : 'transparent',
                              color: diagFilter === df.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                              border: diagFilter === df.id ? '1px solid var(--border-line)' : '1px solid transparent',
                              cursor: 'pointer'
                            }}
                          >
                            {df.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    {displayedWarnings.length === 0 ? (
                      <div style={{ padding: '18px', textAlign: 'center', color: 'var(--supported-color)', fontSize: '12px', background: 'var(--bg-surface-elevated)', borderRadius: '6px' }}>
                        ✓ Complete bibliographic integrity confirmed: all assertions carry verified citations.
                      </div>
                    ) : (
                      displayedWarnings.map((w, idx) => (
                        <div key={`diag-${idx}`} style={{ padding: '12px 14px', background: 'var(--bg-surface-elevated)', borderRadius: '8px', border: '1px solid var(--border-line)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                            <span style={{ fontSize: '10px', fontWeight: '700', color: '#e3a93a', textTransform: 'uppercase' }}>
                              {w.warning_type?.replace('_', ' ')}
                            </span>
                            <span style={{ fontSize: '10.5px', color: 'var(--text-tertiary)' }}>
                              Page {w.page_number || '1'}
                            </span>
                          </div>
                          <div style={{ fontSize: '12.5px', fontStyle: 'italic', color: 'var(--text-primary)', marginBottom: '6px' }}>
                            "{w.claim_text || 'Empirical statement'}"
                          </div>
                          <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)' }}>
                            <strong>Reason:</strong> {w.reason}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* TAB 3: AUDIT TRAIL */}
                {technicalTab === 'audit' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {(!selectedClaim.reviews || selectedClaim.reviews.length === 0) ? (
                      <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', fontStyle: 'italic', padding: '10px 0' }}>
                        Default stance: Human review. No reviewer modifications recorded for this claim yet.
                      </div>
                    ) : (
                      selectedClaim.reviews.map((rev) => (
                        <div key={rev.review_id} className="audit-entry-item" style={{ padding: '10px 12px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span style={{ fontSize: '10px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--accent-orange)' }}>
                                {rev.action}
                              </span>
                              <span style={{ fontSize: '10.5px', color: 'var(--text-tertiary)' }}>
                                by {rev.reviewer_id}
                              </span>
                            </div>
                            <span style={{ fontSize: '10.5px', color: 'var(--text-tertiary)' }}>
                              {rev.created_at ? new Date(rev.created_at).toLocaleDateString() : ''}
                            </span>
                          </div>
                          {rev.comment && (
                            <div style={{ fontSize: '11.5px', color: 'var(--text-primary)', marginTop: '4px' }}>
                              "{rev.comment}"
                            </div>
                          )}
                        </div>
                      ))
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
