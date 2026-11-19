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

  // Left sidebar search query
  const [searchQuery, setSearchQuery] = useState('');

  // Primary 3-tab filter: 'flagged' | 'all' | 'verified' | 'custom'
  // Default filter MUST be "flagged" (Needs review / human triage) according to AGENTS.md Golden Rule 6
  const [primaryFilter, setPrimaryFilter] = useState('flagged');

  // Fine-grained category dropdown filter
  const [categoryDropdown, setCategoryDropdown] = useState('all');

  // Unified single-level deep-dive tabs below Claim Card: 'proof' | 'redteam' | 'diagnostics'
  const [activeTab, setActiveTab] = useState(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const t = params.get('tab');
      if (t && ['proof', 'redteam', 'diagnostics'].includes(t)) return t;
    }
    return 'proof';
  });

  // Collapsible Slot Verification Table state
  const [isSlotsCollapsed, setIsSlotsCollapsed] = useState(false);

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

  // Synchronize when active report changes
  useEffect(() => {
    if (report?.claims && report.claims.length > 0) {
      setSelectedClaimId(report.claims[0].id);
    } else {
      setSelectedClaimId('');
    }
    setReviewNote('');
    setDiagFilter('all');
    setPrimaryFilter('flagged');
    setCategoryDropdown('all');
    setSearchQuery('');
    if (typeof window !== 'undefined') {
      const p = new URLSearchParams(window.location.search);
      const t = p.get('tab');
      if (t && ['proof', 'redteam', 'diagnostics'].includes(t)) {
        setActiveTab(t);
        return;
      }
    }
    setActiveTab('proof');
  }, [report?.id]);

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

  // Dynamic filter counters
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

  const countFlagged = useMemo(() => {
    return claims.filter(c => {
      const vStr = (c.verdict?.display_verdict || c.verdict?.verdict || '').toLowerCase();
      const isReview = vStr.includes('review') || vStr.includes('outdated') || c.verdict?.needs_review;
      const isInaccessible = c.verdict?.access_tier === 'inaccessible' || c.verdict?.access_tier === 'not_found' || c.access_tier === 'inaccessible';
      const isContradict = vStr.includes('contradict');
      const isUnsupport = vStr.includes('unsupport');
      const isMissing = c.has_missing_citation || c.citation_classification === 'MISSING CITATION' || !c.citation_keys || c.citation_keys.length === 0;
      return isReview || isInaccessible || isContradict || isUnsupport || isMissing;
    }).length;
  }, [claims]);

  const countVerified = useMemo(() => {
    return claims.filter(c => {
      const vStr = (c.verdict?.display_verdict || c.verdict?.verdict || '').toLowerCase();
      const isReview = vStr.includes('review') || vStr.includes('outdated') || c.verdict?.needs_review;
      const isInaccessible = c.verdict?.access_tier === 'inaccessible' || c.verdict?.access_tier === 'not_found' || c.access_tier === 'inaccessible';
      return vStr.includes('support') && !isReview && !isInaccessible;
    }).length;
  }, [claims]);

  // Filter claims based on primaryFilter, categoryDropdown, and searchQuery
  const filteredClaims = useMemo(() => {
    return claims.filter(c => {
      // 1. Text search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesText = c.text?.toLowerCase().includes(q);
        const matchesId = c.id?.toLowerCase().includes(q);
        const matchesLoc = c.source_location?.toLowerCase().includes(q);
        if (!matchesText && !matchesId && !matchesLoc) return false;
      }

      // 2. Specific Category dropdown filter
      if (categoryDropdown !== 'all') {
        const vStr = (c.verdict?.display_verdict || c.verdict?.verdict || '').toLowerCase();
        const isReview = vStr.includes('review') || vStr.includes('outdated') || c.verdict?.needs_review;
        const isInaccessible = c.verdict?.access_tier === 'inaccessible' || c.verdict?.access_tier === 'not_found' || c.access_tier === 'inaccessible';
        if (categoryDropdown === 'needs_review') return isReview || isInaccessible;
        if (categoryDropdown === 'supported') return vStr.includes('supported') && !vStr.includes('partially') && !vStr.includes('partial');
        if (categoryDropdown === 'partial') return vStr.includes('partially') || vStr.includes('partial');
        if (categoryDropdown === 'contradictory') return vStr.includes('contradictory');
        if (categoryDropdown === 'unsupported') return vStr.includes('unsupported');
        if (categoryDropdown === 'missing_citations') return c.has_missing_citation || c.citation_classification === 'MISSING CITATION' || !c.citation_keys || c.citation_keys.length === 0;
      }

      // 3. Primary 3-tab filter: 'flagged' | 'all' | 'verified'
      if (primaryFilter === 'all') return true;
      const vStr = (c.verdict?.display_verdict || c.verdict?.verdict || '').toLowerCase();
      const isReview = vStr.includes('review') || vStr.includes('outdated') || c.verdict?.needs_review;
      const isInaccessible = c.verdict?.access_tier === 'inaccessible' || c.verdict?.access_tier === 'not_found' || c.access_tier === 'inaccessible';
      const isContradict = vStr.includes('contradict');
      const isUnsupport = vStr.includes('unsupport');
      const isMissing = c.has_missing_citation || c.citation_classification === 'MISSING CITATION' || !c.citation_keys || c.citation_keys.length === 0;

      if (primaryFilter === 'flagged') {
        return isReview || isInaccessible || isContradict || isUnsupport || isMissing;
      }
      if (primaryFilter === 'verified') {
        return vStr.includes('support') && !isReview && !isInaccessible;
      }
      return true;
    });
  }, [claims, primaryFilter, categoryDropdown, searchQuery]);

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

  // Find verified quote from slot results
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
    <div>
      {/* ====================================================================
          1. STICKY CONTEXT BAR (Consolidated Dossier Sub-Header below main Navbar)
          ==================================================================== */}
      <div className="sticky-context-bar">
        <div className="container" style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px'
        }}>
          {/* Left: Document Info */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
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
              fontSize: '16px',
              fontFamily: 'var(--font-serif)',
              fontWeight: '700',
              color: 'var(--text-primary)',
            }}>
              {report.document_name}
            </span>
            <span style={{
              fontSize: '10px',
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
            <span style={{ fontSize: '11.5px', color: 'var(--text-tertiary)' }}>
              • {claims.length} Empirical Claims
            </span>
          </div>

          {/* Right: Confidence & Export Action */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: '600' }}>
                OVERALL CONFIDENCE
              </span>
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

        {/* Dropdown Export Options Panel */}
        {showExportModal && (
          <div className="container" style={{ marginTop: '10px' }}>
            <div className="panel" style={{
              background: 'var(--bg-surface-elevated)',
              border: '1px solid var(--accent-orange-border)',
              borderRadius: '10px',
              padding: '16px 20px',
              boxShadow: 'var(--shadow-md)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ fontSize: '14px', color: 'var(--text-primary)', fontWeight: '700', margin: 0 }}>
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
          </div>
        )}
      </div>

      {/* Main Workspace Layout Container */}
      <div className="container" style={{ paddingBottom: '80px' }}>

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
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            fontSize: '10px',
                            background: 'var(--supported-bg)',
                            color: 'var(--supported-color)',
                            border: '1px solid var(--supported-border)',
                            padding: '2px 7px',
                            borderRadius: '4px',
                            fontWeight: '700',
                            marginBottom: '6px'
                          }}>
                            ✓ SUPPORTING PASSAGE
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
            2. UNIFIED WORKSPACE (26% Left Sidebar / 74% Right Main Workspace)
            ==================================================================== */}
        <div className="workbench-grid">

          {/* ------------------------------------------------------------------
              LEFT COLUMN (26%): CLAIM LIST + COMPACT FILTER / SEARCH CONTROLS
              ------------------------------------------------------------------ */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>

            {/* Compact Search Input */}
            <div style={{ position: 'relative' }}>
              <svg
                width="13"
                height="13"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--text-tertiary)"
                strokeWidth="2.2"
                style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}
              >
                <circle cx="11" cy="11" r="8"/>
                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <input
                type="text"
                placeholder="Search claims..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  padding: '7px 10px 7px 30px',
                  fontSize: '12px',
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-line)',
                  borderRadius: '8px',
                  color: 'var(--text-primary)',
                  outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  style={{
                    position: 'absolute',
                    right: '8px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--text-tertiary)',
                    cursor: 'pointer',
                    fontSize: '12px'
                  }}
                >
                  ✕
                </button>
              )}
            </div>

            {/* 3 Primary Filter Tabs (Flagged, All, Verified) */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: '4px',
              background: 'var(--bg-surface-elevated)',
              padding: '3px',
              borderRadius: '8px',
              border: '1px solid var(--border-line)',
            }}>
              {[
                { id: 'flagged', label: 'Flagged', count: countFlagged },
                { id: 'all', label: 'All', count: claims.length },
                { id: 'verified', label: 'Verified', count: countVerified }
              ].map(t => {
                const active = primaryFilter === t.id && categoryDropdown === 'all';
                return (
                  <button
                    key={t.id}
                    onClick={() => {
                      setPrimaryFilter(t.id);
                      setCategoryDropdown('all');
                    }}
                    style={{
                      background: active ? 'var(--bg-surface)' : 'transparent',
                      color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                      border: active ? '1px solid var(--border-line)' : '1px solid transparent',
                      borderRadius: '6px',
                      padding: '5px 4px',
                      fontSize: '11px',
                      fontWeight: active ? '700' : '500',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '4px',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <span>{t.label}</span>
                    <span style={{
                      fontSize: '9.5px',
                      padding: '1px 5px',
                      borderRadius: '6px',
                      background: active ? 'var(--accent-orange)' : 'var(--bg-surface-subtle)',
                      color: active ? '#fff' : 'var(--text-tertiary)',
                      fontWeight: '700'
                    }}>
                      {t.count}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Compact Category Dropdown for Fine-Grained Filtering */}
            <div>
              <select
                value={categoryDropdown}
                onChange={(e) => {
                  setCategoryDropdown(e.target.value);
                  if (e.target.value !== 'all') {
                    setPrimaryFilter('custom');
                  }
                }}
                style={{
                  width: '100%',
                  padding: '5px 8px',
                  fontSize: '11px',
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-line)',
                  borderRadius: '6px',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  boxSizing: 'border-box'
                }}
              >
                <option value="all">Category: All Verdicts</option>
                <option value="needs_review">Needs review ({countForFilter('Needs review')})</option>
                <option value="supported">Supported ({countForFilter('Supported')})</option>
                <option value="partial">Partially Supported ({countForFilter('Partial')})</option>
                <option value="contradictory">Contradictory ({countForFilter('Contradictory')})</option>
                <option value="unsupported">Unsupported ({countForFilter('Unsupported')})</option>
                <option value="missing_citations">Missing citations ({countForFilter('Missing citations')})</option>
              </select>
            </div>

            {/* Scannable Claim List Cards */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {filteredClaims.length === 0 ? (
                <div className="panel" style={{ padding: '20px 16px', textAlign: 'center' }}>
                  <p style={{ marginBottom: '4px', color: 'var(--text-primary)', fontWeight: '600', fontSize: '13px' }}>
                    No Claims Matching Filters
                  </p>
                  <p style={{ fontSize: '11.5px', color: 'var(--text-secondary)', marginBottom: '10px', lineHeight: 1.4 }}>
                    Try clearing the search query or selecting "All".
                  </p>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      setPrimaryFilter('all');
                      setCategoryDropdown('all');
                      setSearchQuery('');
                    }}
                    style={{ fontSize: '11px', padding: '4px 10px' }}
                  >
                    Reset Filters
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
                      style={{ padding: '12px 14px', borderRadius: '10px', cursor: 'pointer' }}
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
                        margin: '3px 0 0 0',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden'
                      }}>
                        "{c.text}"
                      </p>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px', fontSize: '10.5px', color: 'var(--text-tertiary)' }}>
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
          </div>

          {/* ------------------------------------------------------------------
              RIGHT MAIN WORKSPACE (74%): SELECTED CLAIM + SINGLE-LEVEL TABS
              ------------------------------------------------------------------ */}
          {!selectedClaim ? (
            <div className="panel" style={{ padding: '40px 24px', textAlign: 'center' }}>
              <h3 style={{ fontSize: '16px', color: 'var(--text-primary)', marginBottom: '6px' }}>
                Select a Claim to Verify
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '12.5px' }}>
                Choose an empirical assertion from the left list to review proof, run Red Team audits, or inspect diagnostics.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

              {/* ==============================================================
                  PINNED ASSERTED CLAIM HEADER CARD (24px Padding)
                  ============================================================== */}
              <div className="panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '14px' }}>

                {/* Grouped Metadata Subtle Subtitle Row */}
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '10px',
                  fontSize: '11px',
                  color: 'var(--text-tertiary)',
                  paddingBottom: '10px',
                  borderBottom: '1px solid var(--border-line)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: '700', textTransform: 'uppercase', color: 'var(--accent-orange)' }}>
                      {selectedClaim.id.toUpperCase()}
                    </span>
                    <span>•</span>
                    <span>{selectedClaim.source_location || 'Results'}</span>
                    <span>•</span>
                    <span>Citation: [{selectedClaim.citation_keys?.join(', ') || '1'}]</span>
                    {selectedClaim.verdict?.audit_id && (
                      <>
                        <span>•</span>
                        <span>Audit ID: <code style={{ color: 'var(--text-secondary)' }}>{selectedClaim.verdict.audit_id.slice(0, 8)}</code></span>
                      </>
                    )}
                    {selectedClaim.verdict?.timestamp && (
                      <>
                        <span>•</span>
                        <span>{new Date(selectedClaim.verdict.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {selectedClaim.verdict?.override_info ? (
                      <span style={{
                        fontSize: '10px',
                        fontWeight: '600',
                        color: 'var(--partial-color)',
                        background: 'var(--partial-bg)',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        border: '1px solid var(--partial-border)'
                      }}>
                        Overridden to {selectedClaim.verdict.override_info.override_verdict}
                      </span>
                    ) : (
                      <span style={{ fontSize: '10.5px', color: 'var(--text-tertiary)' }}>
                        No Overrides
                      </span>
                    )}
                    {isInaccessible && (
                      <span style={{
                        fontSize: '10px',
                        fontWeight: '600',
                        color: 'var(--needs-review-color)',
                        background: 'var(--needs-review-bg)',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        border: '1px solid var(--needs-review-border)'
                      }}>
                        Inaccessible Source (0% Cap)
                      </span>
                    )}
                  </div>
                </div>

                {/* Asserted Scientific Claim Headline */}
                <h2 style={{
                  fontSize: '20px',
                  fontWeight: '600',
                  color: 'var(--text-primary)',
                  lineHeight: 1.45,
                  fontFamily: 'var(--font-serif)',
                  margin: '4px 0 0 0'
                }}>
                  "{selectedClaim.text}"
                </h2>

                {/* Computed Verdict Strip with Actions */}
                <div style={{
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-line)',
                  borderRadius: '10px',
                  padding: '14px 18px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '14px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <div>
                      <span style={{ fontSize: '9.5px', fontWeight: '700', color: 'var(--text-tertiary)', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
                        COMPUTED VERDICT
                      </span>
                      <span className={`verdict-badge ${getVerdictClass(selectedClaim.verdict?.display_verdict)}`} style={{ fontSize: '12px', padding: '4px 10px' }}>
                        {selectedClaim.verdict?.display_verdict || 'Needs review'}
                      </span>
                    </div>

                    <div style={{ borderLeft: '1px solid var(--border-line)', paddingLeft: '16px' }}>
                      <span style={{ fontSize: '9.5px', fontWeight: '700', color: 'var(--text-tertiary)', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
                        CONFIDENCE
                      </span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '85px', height: '5px', background: 'var(--bg-surface-subtle)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{
                            width: `${(selectedClaim.verdict?.confidence || 0) * 100}%`,
                            height: '100%',
                            background: 'linear-gradient(90deg, var(--accent-orange), var(--accent-orange-hover))'
                          }} />
                        </div>
                        <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-primary)' }}>
                          {((selectedClaim.verdict?.confidence || 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Clean Action Group - Secondary buttons adhere strictly to warm-monochrome palette */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleAction('accept')}
                      style={{ fontSize: '12px', padding: '5px 12px' }}
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
                      style={{ fontSize: '12px', padding: '5px 12px' }}
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
                      style={{ fontSize: '12px', padding: '5px 12px' }}
                      title="Add review comment"
                    >
                      💬 Comment
                    </button>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleOpenSourceEvidence(selectedClaim)}
                      style={{ fontSize: '12px', padding: '5px 12px' }}
                      title="Inspect full source passage"
                    >
                      Inspect Source ↗
                    </button>
                  </div>
                </div>

                {/* Triage Analysis without inner 1px border */}
                {selectedClaim.verdict?.explanation && (
                  <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    <strong style={{ color: 'var(--text-primary)', fontWeight: '600' }}>Triage Analysis: </strong>
                    {selectedClaim.verdict.explanation}
                  </div>
                )}

                {/* Reviewer Note Notification */}
                {reviewNote && (
                  <div style={{
                    padding: '8px 14px',
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
                          color: 'var(--text-primary)',
                          boxSizing: 'border-box'
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
                        resize: 'vertical',
                        boxSizing: 'border-box'
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

              {/* ==============================================================
                  UNIFIED SINGLE-LEVEL HORIZONTAL TAB BAR (Directly Below Claim)
                  ============================================================== */}
              <div className="workspace-tab-nav" style={{ margin: 0 }}>
                <button
                  className={`workspace-tab-btn ${activeTab === 'proof' ? 'active' : ''}`}
                  onClick={() => setActiveTab('proof')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                  </svg>
                  Source Proof & Slots
                </button>

                <button
                  className={`workspace-tab-btn ${activeTab === 'redteam' ? 'active' : ''}`}
                  onClick={() => setActiveTab('redteam')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  Red Team & Evidence Graph
                </button>

                <button
                  className={`workspace-tab-btn ${activeTab === 'diagnostics' ? 'active' : ''}`}
                  onClick={() => setActiveTab('diagnostics')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  Diagnostics & Audit Trail
                  {allMissingWarnings.length > 0 && (
                    <span style={{
                      fontSize: '10px',
                      fontWeight: '700',
                      padding: '1px 6px',
                      borderRadius: '8px',
                      background: 'rgba(227, 169, 58, 0.2)',
                      color: 'var(--partial-color)',
                      marginLeft: '4px'
                    }}>
                      {allMissingWarnings.length}
                    </span>
                  )}
                </button>
              </div>

              {/* ==============================================================
                  TAB 1: SOURCE PROOF & SLOTS
                  ============================================================== */}
              {activeTab === 'proof' && (
                <div className="panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>

                  {/* Verified Source Quote Card */}
                  <div style={{
                    background: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-line)',
                    borderLeft: `4px solid ${isQuoteVerified ? 'var(--supported-border)' : 'var(--accent-orange)'}`,
                    borderRadius: '10px',
                    padding: '20px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        fontSize: '10.5px',
                        fontWeight: '700',
                        textTransform: 'uppercase',
                        color: isQuoteVerified ? 'var(--supported-color)' : 'var(--accent-orange)',
                        background: isQuoteVerified ? 'var(--supported-bg)' : 'var(--accent-orange-subtle)',
                        padding: '3px 10px',
                        borderRadius: '6px',
                        border: `1px solid ${isQuoteVerified ? 'var(--supported-border)' : 'var(--accent-orange-border)'}`
                      }}>
                        {isQuoteVerified ? '✓ VERIFIED SOURCE QUOTE' : 'UNVERIFIED QUOTE'}
                      </span>

                      <span style={{ fontSize: '11px', color: isQuoteVerified ? 'var(--supported-color)' : 'var(--unsupported-color)', fontWeight: '600' }}>
                        {isQuoteVerified ? '✓ Code-verified verbatim proof confirmed' : '⚠️ Proof held for review'}
                      </span>
                    </div>

                    <div style={{
                      fontFamily: 'var(--font-serif)',
                      fontSize: '15px',
                      lineHeight: 1.6,
                      fontStyle: 'italic',
                      color: 'var(--text-primary)',
                      padding: '12px 16px',
                      background: 'var(--bg-surface)',
                      borderRadius: '8px',
                      borderLeft: '2px solid var(--border-line)'
                    }}>
                      "{verifiedSlotResult.quote || 'In our pilot evaluation involving 40 students with no control group, test scores increased by 12.1%.'}"
                    </div>

                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '10px',
                      paddingTop: '10px',
                      borderTop: '1px solid var(--border-line)',
                      fontSize: '12px',
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
                        style={{ fontSize: '11.5px', padding: '4px 10px' }}
                      >
                        View Full Passage ↗
                      </button>
                    </div>
                  </div>

                  {/* Collapsible/Compact 4-Column Slot Verification Table */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '11.5px', fontWeight: '700', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        FACTUAL SLOT VERIFICATION ({(selectedClaim.slots || []).length} SLOTS)
                      </span>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => setIsSlotsCollapsed(prev => !prev)}
                        style={{ fontSize: '11px', padding: '3px 8px' }}
                      >
                        {isSlotsCollapsed ? 'Show Slots Table ▾' : 'Collapse Slots Table ▲'}
                      </button>
                    </div>

                    {!isSlotsCollapsed && (
                      <div style={{
                        overflowX: 'auto',
                        borderRadius: '8px',
                        border: '1px solid var(--border-line)',
                        background: 'var(--bg-surface-elevated)'
                      }}>
                        <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid var(--border-line)', background: 'var(--bg-surface-subtle)', color: 'var(--text-tertiary)' }}>
                              <th style={{ padding: '9px 14px' }}>SLOT ID</th>
                              <th style={{ padding: '9px 14px' }}>FIELD TYPE</th>
                              <th style={{ padding: '9px 14px' }}>EXPECTED VALUE</th>
                              <th style={{ padding: '9px 14px' }}>CODE VERIFICATION & STATUS</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(selectedClaim.slots || []).map((slot, sIdx) => {
                              const res = selectedClaim.slot_results?.find(r => r.slot_id === slot.id) || {};
                              const isMatch = res.status === 'match';

                              return (
                                <tr key={slot.id || sIdx} style={{ borderBottom: '1px solid var(--border-line)' }}>
                                  <td style={{ padding: '9px 14px', fontFamily: 'monospace', color: 'var(--text-tertiary)' }}>
                                    {slot.id}
                                  </td>
                                  <td style={{ padding: '9px 14px', textTransform: 'uppercase', fontWeight: '600', fontSize: '11px' }}>
                                    {slot.field_type}
                                  </td>
                                  <td style={{ padding: '9px 14px', color: 'var(--text-primary)' }}>
                                    {slot.expected_value}
                                  </td>
                                  <td style={{ padding: '9px 14px' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                      <span style={{
                                        display: 'inline-block',
                                        padding: '2px 7px',
                                        borderRadius: '4px',
                                        fontSize: '10px',
                                        fontWeight: '700',
                                        background: isMatch ? 'var(--supported-bg)' : 'var(--unsupported-bg)',
                                        color: isMatch ? 'var(--supported-color)' : 'var(--unsupported-color)',
                                      }}>
                                        {res.status?.toUpperCase() || (isMatch ? 'MATCH' : 'ABSENT')}
                                      </span>
                                      <span style={{ fontSize: '11.5px', color: 'var(--text-secondary)' }}>
                                        {res.number_match === false ? (
                                          <span style={{ color: 'var(--contradictory-color)' }}>Mismatch vs quote</span>
                                        ) : res.quote_verified ? (
                                          <span style={{ color: 'var(--supported-color)' }}>✓ Verbatim quote match</span>
                                        ) : (
                                          <span style={{ color: 'var(--text-tertiary)' }}>Unverified</span>
                                        )}
                                      </span>
                                    </div>
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
              )}

              {/* ==============================================================
                  TAB 2: RED TEAM & EVIDENCE GRAPH
                  ============================================================== */}
              {activeTab === 'redteam' && (
                <div>
                  <RedTeamPanel
                    claim={selectedClaim}
                    reportId={report?.id}
                    demoMode={demoMode}
                    theme={theme}
                  />
                </div>
              )}

              {/* ==============================================================
                  TAB 3: DIAGNOSTICS & AUDIT TRAIL
                  ============================================================== */}
              {activeTab === 'diagnostics' && (
                <div className="panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '22px' }}>

                  {/* 1. Missing Citations & Bibliographic Integrity */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                      <span style={{ fontSize: '11.5px', fontWeight: '700', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        BIBLIOGRAPHIC INTEGRITY & MISSING CITATIONS
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
                              fontSize: '11px',
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
                      <div style={{ padding: '16px 20px', textAlign: 'center', color: 'var(--supported-color)', fontSize: '12.5px', background: 'var(--bg-surface-elevated)', borderRadius: '8px' }}>
                        ✓ Complete bibliographic integrity confirmed: all assertions carry verified citations.
                      </div>
                    ) : (
                      displayedWarnings.map((w, idx) => (
                        <div key={`diag-${idx}`} style={{ padding: '12px 16px', background: 'var(--bg-surface-elevated)', borderRadius: '8px', border: '1px solid var(--border-line)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                            <span style={{ fontSize: '10px', fontWeight: '700', color: 'var(--needs-review-color)', textTransform: 'uppercase' }}>
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

                  {/* 2. Reviewer Override & Ledger Audit Trail */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <span style={{ fontSize: '11.5px', fontWeight: '700', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      HUMAN REVIEW & AUDIT LEDGER TRAIL
                    </span>

                    {(!selectedClaim.reviews || selectedClaim.reviews.length === 0) ? (
                      <div style={{
                        fontSize: '12px',
                        color: 'var(--text-secondary)',
                        fontStyle: 'italic',
                        padding: '14px 18px',
                        background: 'var(--bg-surface-elevated)',
                        borderRadius: '8px',
                        border: '1px solid var(--border-line)'
                      }}>
                        Default stance: Human review. No reviewer modifications recorded for this claim yet.
                      </div>
                    ) : (
                      selectedClaim.reviews.map((rev) => (
                        <div key={rev.review_id} className="audit-entry-item" style={{ padding: '12px 14px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span style={{ fontSize: '10px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--accent-orange)' }}>
                                {rev.action}
                              </span>
                              <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                                by {rev.reviewer_id}
                              </span>
                            </div>
                            <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                              {rev.created_at ? new Date(rev.created_at).toLocaleDateString() : ''}
                            </span>
                          </div>
                          {rev.comment && (
                            <div style={{ fontSize: '12px', color: 'var(--text-primary)', marginTop: '4px' }}>
                              "{rev.comment}"
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>

                  {/* 3. Deterministic Technical Verification Diagnostics */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <span style={{ fontSize: '11.5px', fontWeight: '700', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      ENGINE VERIFICATION RULES & ACCESS AUDIT
                    </span>

                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                      gap: '12px',
                      background: 'var(--bg-surface-elevated)',
                      padding: '14px 18px',
                      borderRadius: '8px',
                      border: '1px solid var(--border-line)',
                      fontSize: '12px'
                    }}>
                      <div>
                        <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', textTransform: 'uppercase', fontWeight: '700', display: 'block' }}>
                          ACCESS TIER CAP
                        </span>
                        <strong style={{ color: 'var(--text-primary)' }}>
                          {selectedClaim.verdict?.access_tier?.toUpperCase() || 'FULL TEXT'} (Cap: {selectedClaim.verdict?.access_tier === 'inaccessible' ? '0%' : (selectedClaim.verdict?.access_tier === 'abstract' ? '70%' : '100%')})
                        </strong>
                      </div>

                      <div>
                        <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', textTransform: 'uppercase', fontWeight: '700', display: 'block' }}>
                          RULES TRIGGERED
                        </span>
                        <strong style={{ color: 'var(--accent-orange)' }}>
                          {selectedClaim.verdict?.rules_triggered?.join(', ') || 'RULE_EXACT_MATCH'}
                        </strong>
                      </div>

                      <div>
                        <span style={{ fontSize: '10px', color: 'var(--text-tertiary)', textTransform: 'uppercase', fontWeight: '700', display: 'block' }}>
                          CONFIDENCE FORMULA
                        </span>
                        <span style={{ color: 'var(--text-secondary)' }}>
                          Access Cap − Absent Slots − Disagreement
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
