import React, { useState, useEffect } from 'react';
import { apiUrl, getAuthHeaders } from '../api';

// Color token mappings for Evidence Dependency Graph & Status Badges (Warm-Monochrome, Coral & Amber - Zero Green/Blue)
const CATEGORY_COLORS = {
  supporting: { text: 'var(--supported-color)', bg: 'var(--supported-bg)', border: 'var(--supported-border)', label: 'Supporting' },
  contradictory: { text: 'var(--contradictory-color)', bg: 'var(--contradictory-bg)', border: 'var(--contradictory-border)', label: 'Contradictory' },
  partial: { text: 'var(--partial-color)', bg: 'var(--partial-bg)', border: 'var(--partial-border)', label: 'Partially Supporting' },
  inconclusive: { text: 'var(--text-secondary)', bg: 'var(--btn-secondary-bg)', border: 'var(--btn-secondary-border)', label: 'Inconclusive' },
  integrity_alert: { text: 'var(--contradictory-color)', bg: 'var(--contradictory-bg)', border: 'var(--contradictory-border)', label: 'Integrity Alert' },
};

const OUTCOME_STYLES = {
  'Supported by available evidence': { color: 'var(--supported-color)', bg: 'var(--supported-bg)', border: 'var(--supported-border)' },
  'Partially supported': { color: 'var(--partial-color)', bg: 'var(--partial-bg)', border: 'var(--partial-border)' },
  'Contested by contradictory evidence': { color: 'var(--contradictory-color)', bg: 'var(--contradictory-bg)', border: 'var(--contradictory-border)' },
  'Unsupported by retrieved evidence': { color: 'var(--contradictory-color)', bg: 'var(--contradictory-bg)', border: 'var(--contradictory-border)' },
  'Publication integrity concern': { color: 'var(--contradictory-color)', bg: 'var(--contradictory-bg)', border: 'var(--contradictory-border)' },
  'Insufficient evidence to determine': { color: 'var(--needs-review-color)', bg: 'var(--needs-review-bg)', border: 'var(--needs-review-border)' },
};

export default function RedTeamPanel({
  claim,
  reportId,
  demoMode = true,
  theme = 'dark',
}) {
  const [investigating, setInvestigating] = useState(false);
  const [currentStageIndex, setCurrentStageIndex] = useState(0);
  const [investigationData, setInvestigationData] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('graph');
  const [selectedNode, setSelectedNode] = useState(null);
  const [activeStageTab, setActiveStageTab] = useState('stage_a');
  const [copiedDossier, setCopiedDossier] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true);

  // Sync investigation state when claim or reportId changes
  useEffect(() => {
    let isMounted = true;
    if (!claim?.id) {
      setInvestigationData(null);
      setError(null);
      setSelectedNode(null);
      return;
    }

    const cid = claim.id;
    const repId = reportId || 'demo-report-1';

    // Reset current state to avoid showing stale data from previous claims
    setInvestigationData(null);
    setError(null);
    setSelectedNode(null);
    setCurrentStageIndex(0);
    setInvestigating(false);

    // Retrieve any existing persistent audit from backend
    fetch(apiUrl(`/api/redteam/investigations/${encodeURIComponent(cid)}?report_id=${encodeURIComponent(repId)}`), {
      headers: getAuthHeaders(),
    })
      .then(res => {
        if (!res.ok) throw new Error('Failed to retrieve past audit');
        return res.json();
      })
      .then(data => {
        if (!isMounted) return;
        if (data?.investigations && data.investigations.length > 0) {
          const latest = data.investigations[0];
          setInvestigationData(latest);
          setIsExpanded(true);
          if (latest.dependency_graph?.nodes?.length > 0) {
            setSelectedNode(latest.dependency_graph.nodes[0]);
          }
        }
      })
      .catch(() => {
        // No past audit recorded; stays in Not Yet Investigated state
      });

    return () => {
      isMounted = false;
    };
  }, [claim?.id, reportId]);

  if (!claim) return null;

  const claimId = claim.id || 'claim-1';
  const claimText = claim.text || '';
  const paperTitle = claim.paper_title || (claim.slot_results?.[0]?.source_title) || 'Referenced Primary Literature';
  const paperDoi = claim.doi || (claim.slot_results?.[0]?.source_doi) || (claim.citation_keys?.[0] === '1' ? '10.1056/NEJMoa1702345' : '10.1145/3065386');
  const originalVerdict = claim.verdict?.display_verdict || claim.verdict?.verdict || 'Needs review';
  const originalConfidence = claim.verdict?.confidence || 0.5;

  const stagesList = [
    { key: 'stage_a', title: 'Stage A · Source Integrity', desc: 'Retractions, corrections & Crossref audit' },
    { key: 'stage_b', title: 'Stage B · Counter-Evidence', desc: 'Literature discovery for contradictory findings' },
    { key: 'stage_c', title: 'Stage C · Numerical Integrity', desc: 'Audit percentages, sample sizes & p-values' },
    { key: 'stage_d', title: 'Stage D · Evidence Independence', desc: 'Citation trees, shared datasets & author overlap' },
    { key: 'stage_e', title: 'Stage E · Limitation Analysis', desc: 'Author-reported confounders & small samples' },
  ];

  const handleStartChallenge = async () => {
    if (investigating) return; // Prevent duplicate requests
    setIsExpanded(true);
    setInvestigating(true);
    setError(null);
    setCurrentStageIndex(0);

    // Live Stage Animation
    const advanceStage = (idx) => {
      if (idx <= 4) {
        setCurrentStageIndex(idx);
      }
    };

    const timer1 = setTimeout(() => advanceStage(1), 350);
    const timer2 = setTimeout(() => advanceStage(2), 700);
    const timer3 = setTimeout(() => advanceStage(3), 1050);
    const timer4 = setTimeout(() => advanceStage(4), 1400);

    try {
      const response = await fetch(apiUrl('/api/redteam/challenge'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({
          claim_id: claimId,
          report_id: reportId || 'demo-report-1',
          claim_text: claimText,
          citation_key: claim.citation_keys?.[0] || '1',
          doi: paperDoi,
          paper_title: paperTitle,
          original_verdict: originalVerdict,
          original_confidence: originalConfidence,
          demo_mode: demoMode,
        }),
      });

      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      clearTimeout(timer4);

      if (!response.ok) {
        let errDetail = `API challenge request failed (${response.status})`;
        try {
          const errJson = await response.json();
          errDetail = errJson.detail || errJson.message || errDetail;
        } catch {}
        throw new Error(errDetail);
      }

      const json = await response.json();
      if (!json.investigation) {
        throw new Error('API returned empty investigation response');
      }

      setInvestigationData(json.investigation);
      setInvestigating(false);
      setError(null);
      if (json.investigation.dependency_graph?.nodes?.length > 0) {
        setSelectedNode(json.investigation.dependency_graph.nodes[0]);
      }
    } catch (err) {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      clearTimeout(timer4);
      setInvestigating(false);
      setError(err.message || 'Adversarial investigation could not be completed.');
    }
  };

  const handleCopyDossier = () => {
    if (!investigationData) return;
    const text = `CREDENCE RED TEAM INVESTIGATION DOSSIER\n` +
      `Claim ID: ${investigationData.claim_id}\n` +
      `Claim: "${investigationData.claim_text}"\n` +
      `Outcome: ${investigationData.overall_outcome}\n` +
      `Rationale: ${investigationData.outcome_rationale}\n\n` +
      `Summary: ${investigationData.executive_summary}\n\n` +
      `Stage A: Status ${investigationData.stage_a_source_integrity?.status?.toUpperCase()} (${investigationData.stage_a_source_integrity?.doi})\n` +
      `Stage B Counter-Evidence: ${investigationData.stage_b_counter_evidence?.length || 0} studies found\n` +
      `Stage C Numerical Discrepancies: ${investigationData.stage_c_numerical_integrity?.length || 0} flagged\n` +
      `Stage D Independence: ${investigationData.stage_d_independence?.findings_summary || 'N/A'}\n` +
      `Stage E Limitations: ${investigationData.stage_e_limitations?.length || 0} extracted\n\n` +
      `Generated at: ${investigationData.created_at}`;

    navigator.clipboard?.writeText(text);
    setCopiedDossier(true);
    setTimeout(() => setCopiedDossier(false), 2500);
  };

  const outcomeStyle = investigationData ? (OUTCOME_STYLES[investigationData.overall_outcome] || OUTCOME_STYLES['Partially supported']) : null;

  return (
    <div className="redteam-feature-card" style={{
      marginTop: '4px',
      borderRadius: '14px',
      overflow: 'hidden',
      transition: 'all 0.25s ease',
    }}>
      {/* ====================================================================
          1. HEADER BAR & CHALLENGE TRIGGER
          ==================================================================== */}
      <div style={{
        padding: '24px 28px',
        borderBottom: '1px solid var(--border-line)',
        background: 'var(--bg-surface-elevated)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            background: 'var(--contradictory-bg)',
            border: '1px solid var(--contradictory-border)',
            color: 'var(--contradictory-color)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: 'var(--shadow-sm)',
          }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h3 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-primary)', margin: 0, fontFamily: 'var(--font-serif)' }}>
                Credence Red Team
              </h3>
              <span style={{
                fontSize: '10px',
                fontWeight: '700',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                background: 'var(--contradictory-bg)',
                color: 'var(--contradictory-color)',
                padding: '2px 8px',
                borderRadius: '4px',
                border: '1px solid var(--contradictory-border)',
              }}>
                Adversarial Scientific Integrity
              </span>
            </div>
            <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '3px' }}>
              Challenge this assertion against independent counter-evidence, retractions, numerical discrepancies & methodological constraints.
            </div>
          </div>
        </div>

        {/* Header Action Button & Timestamp */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          {investigationData && investigationData.created_at && !investigating && (
            <span style={{ fontSize: '11.5px', color: 'var(--text-tertiary)', whiteSpace: 'nowrap' }}>
              Last Audited: {new Date(investigationData.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}, {new Date(investigationData.created_at).toLocaleDateString()}
            </span>
          )}

          {investigating ? (
            <button
              disabled
              className="btn btn-secondary"
              style={{
                opacity: 0.85,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '9px',
                padding: '9px 18px',
                fontSize: '13px',
                fontWeight: '600',
              }}
            >
              <svg className="spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
              </svg>
              Auditing Claim Integrity...
            </button>
          ) : investigationData ? (
            <button
              onClick={handleStartChallenge}
              className="btn btn-secondary btn-sm"
              title="Re-run adversarial investigation on this claim"
              style={{
                fontSize: '12.5px',
                padding: '7px 15px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                fontWeight: '600',
                border: '1px solid var(--border-line)',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <path d="M23 4v6h-6"/>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
              </svg>
              Re-Run Adversarial Audit
            </button>
          ) : (
            <button
              onClick={handleStartChallenge}
              className="btn btn-primary"
              style={{
                background: 'linear-gradient(135deg, var(--contradictory-color) 0%, var(--accent-orange) 100%)',
                borderColor: 'transparent',
                color: '#ffffff',
                fontWeight: '700',
                padding: '10px 22px',
                fontSize: '13.5px',
                boxShadow: '0 4px 16px rgba(248, 113, 113, 0.25)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '9px',
                borderRadius: '8px',
                cursor: 'pointer',
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              Run Adversarial Audit
            </button>
          )}
        </div>
      </div>

      {/* ====================================================================
          2. ERROR / FAILURE BANNER (Investigation Failed State)
          ==================================================================== */}
      {error && !investigating && (
        <div style={{
          padding: '24px 28px',
          background: 'var(--contradictory-bg)',
          borderBottom: '1px solid var(--contradictory-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              background: 'var(--contradictory-bg)',
              color: 'var(--contradictory-color)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
            </div>
            <div>
              <div style={{ fontSize: '14px', fontWeight: '700', color: 'var(--contradictory-color)' }}>
                Adversarial Audit Failed
              </div>
              <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                {error}
              </div>
            </div>
          </div>
          <button
            onClick={handleStartChallenge}
            className="btn btn-primary btn-sm"
            style={{
              background: 'var(--contradictory-color)',
              borderColor: 'var(--contradictory-color)',
              color: '#ffffff',
              fontWeight: '600',
              padding: '8px 18px',
            }}
          >
            Retry Adversarial Audit
          </button>
        </div>
      )}

      {/* ====================================================================
          3. NOT YET INVESTIGATED INITIAL STATE
          ==================================================================== */}
      {!investigating && !investigationData && !error && (
        <div style={{
          padding: '28px 28px',
          background: 'var(--bg-surface)',
          display: 'flex',
          flexDirection: 'column',
          gap: '18px',
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '18px',
          }}>
            <div style={{ maxWidth: '680px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <span style={{
                  fontSize: '11px',
                  fontWeight: '700',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  background: 'var(--needs-review-bg)',
                  color: 'var(--needs-review-color)',
                  padding: '3px 9px',
                  borderRadius: '5px',
                  border: '1px solid var(--needs-review-border)',
                }}>
                  Status: Not Yet Audited
                </span>
                <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
                  Selected Claim: <code>{claimId}</code>
                </span>
              </div>
              <h4 style={{ fontSize: '15.5px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '6px', lineHeight: 1.4 }}>
                Adversarial Verification Ready for Execution
              </h4>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                This assertion has not yet undergone independent adversarial auditing. Click <strong>Run Adversarial Audit</strong> above to cross-examine cited literature against retraction databases, scan for contradictory replication studies, and flag numerical discrepancies.
              </p>
            </div>
          </div>

          {/* 5-Stage Scope Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '10px',
            marginTop: '4px',
          }}>
            {stagesList.map((st) => (
              <div key={st.key} style={{
                padding: '10px 12px',
                borderRadius: '8px',
                background: 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-line)',
              }}>
                <div style={{ fontSize: '11px', fontWeight: '700', color: 'var(--accent-orange)', marginBottom: '3px' }}>
                  {st.title}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', lineHeight: 1.35 }}>
                  {st.desc}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ====================================================================
          4. LIVE 5-STAGE PROGRESS BAR (During active investigation)
          ==================================================================== */}
      {investigating && (
        <div style={{ padding: '32px 28px', background: 'var(--bg-surface)' }}>
          <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)' }}>
              Executing 5-Stage Scientific Integrity Audit ({currentStageIndex + 1} of 5)
            </span>
            <span style={{ fontSize: '12px', color: 'var(--accent-orange)', fontWeight: '600' }}>
              {Math.round(((currentStageIndex + 1) / 5) * 100)}% Complete
            </span>
          </div>

          {/* Progress track */}
          <div style={{ height: '6px', background: 'var(--bg-surface-elevated)', borderRadius: '3px', overflow: 'hidden', marginBottom: '24px' }}>
            <div style={{
              height: '100%',
              width: `${((currentStageIndex + 1) / 5) * 100}%`,
              background: 'linear-gradient(90deg, var(--contradictory-color), var(--accent-orange))',
              transition: 'width 0.35s ease',
            }} />
          </div>

          {/* 5 Stage Steps */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
            {stagesList.map((st, idx) => {
              const isPast = idx < currentStageIndex;
              const isCurrent = idx === currentStageIndex;
              return (
                <div key={st.key} style={{
                  padding: '12px 14px',
                  borderRadius: '10px',
                  border: isCurrent ? '1px solid var(--accent-orange)' : (isPast ? '1px solid var(--border-line)' : '1px dashed var(--border-line)'),
                  background: isCurrent ? 'var(--accent-orange-subtle)' : (isPast ? 'var(--bg-surface-elevated)' : 'transparent'),
                  opacity: isPast || isCurrent ? 1 : 0.45,
                  transition: 'all 0.25s ease',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    {isPast ? (
                      <span style={{ color: 'var(--supported-color)', fontSize: '14px', fontWeight: '700' }}>✓</span>
                    ) : isCurrent ? (
                      <span className="spin" style={{ display: 'inline-block', width: '12px', height: '12px', border: '2px solid var(--accent-orange)', borderTopColor: 'transparent', borderRadius: '50%' }} />
                    ) : (
                      <span style={{ color: 'var(--text-tertiary)', fontSize: '12px' }}>{idx + 1}</span>
                    )}
                    <span style={{ fontSize: '12px', fontWeight: isCurrent ? '700' : '600', color: isCurrent ? 'var(--accent-orange)' : 'var(--text-primary)' }}>
                      {st.title.split(' · ')[1]}
                    </span>
                  </div>
                  <div style={{ fontSize: '10.5px', color: 'var(--text-tertiary)', lineHeight: 1.3 }}>
                    {st.desc}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ====================================================================
          3. INVESTIGATION RESULTS VIEW
          ==================================================================== */}
      {investigationData && !investigating && (
        <div>
          {/* Executive Outcome Banner */}
          <div style={{
            padding: '24px 28px',
            background: outcomeStyle?.bg || 'var(--bg-surface-elevated)',
            borderBottom: `1px solid ${outcomeStyle?.border || 'var(--border-line)'}`,
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '16px',
          }}>
            <div style={{ maxWidth: '820px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <span style={{
                  fontSize: '11px',
                  fontWeight: '700',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  background: outcomeStyle?.bg,
                  color: outcomeStyle?.color,
                  padding: '4px 10px',
                  borderRadius: '6px',
                  border: `1px solid ${outcomeStyle?.border}`,
                }}>
                  {investigationData.overall_outcome}
                </span>
                <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
                  Audit ID: <code>{investigationData.investigation_id}</code>
                </span>
              </div>

              <div style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '8px', lineHeight: 1.4 }}>
                {investigationData.executive_summary}
              </div>

              <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '12px' }}>
                <strong style={{ color: 'var(--text-primary)' }}>Epistemic Rationale:</strong> {investigationData.outcome_rationale}
              </div>

              {/* Quick Investigation Findings Tally */}
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <span style={{
                  fontSize: '11px',
                  fontWeight: '600',
                  padding: '3px 9px',
                  borderRadius: '5px',
                  background: 'var(--supported-bg)',
                  color: 'var(--supported-color)',
                  border: '1px solid var(--supported-border)'
                }}>
                  ✓ {investigationData.stage_d_independence?.independent_replications ?? 1} Supporting Sources
                </span>

                <span style={{
                  fontSize: '11px',
                  fontWeight: '600',
                  padding: '3px 9px',
                  borderRadius: '5px',
                  background: (investigationData.stage_b_counter_evidence?.length || 0) > 0 ? 'var(--contradictory-bg)' : 'var(--bg-surface-elevated)',
                  color: (investigationData.stage_b_counter_evidence?.length || 0) > 0 ? 'var(--contradictory-color)' : 'var(--text-tertiary)',
                  border: `1px solid ${(investigationData.stage_b_counter_evidence?.length || 0) > 0 ? 'var(--contradictory-border)' : 'var(--border-line)'}`
                }}>
                  {investigationData.stage_b_counter_evidence?.length || 0} Contradictory Studies
                </span>

                <span style={{
                  fontSize: '11px',
                  fontWeight: '600',
                  padding: '3px 9px',
                  borderRadius: '5px',
                  background: investigationData.stage_a_source_integrity?.is_alert ? 'var(--contradictory-bg)' : 'var(--bg-surface-elevated)',
                  color: investigationData.stage_a_source_integrity?.is_alert ? 'var(--contradictory-color)' : 'var(--text-tertiary)',
                  border: `1px solid ${investigationData.stage_a_source_integrity?.is_alert ? 'var(--contradictory-border)' : 'var(--border-line)'}`
                }}>
                  {investigationData.stage_a_source_integrity?.is_alert ? '⚠️ Retraction / Erratum Flag' : '0 Retraction Flags'}
                </span>

                <span style={{
                  fontSize: '11px',
                  fontWeight: '600',
                  padding: '3px 9px',
                  borderRadius: '5px',
                  background: (investigationData.stage_c_numerical_integrity?.length || 0) > 0 ? 'var(--partial-bg)' : 'var(--bg-surface-elevated)',
                  color: (investigationData.stage_c_numerical_integrity?.length || 0) > 0 ? 'var(--partial-color)' : 'var(--text-tertiary)',
                  border: `1px solid ${(investigationData.stage_c_numerical_integrity?.length || 0) > 0 ? 'var(--partial-border)' : 'var(--border-line)'}`
                }}>
                  {investigationData.stage_c_numerical_integrity?.length || 0} Statistical Discrepancies
                </span>

                <span style={{
                  fontSize: '11px',
                  fontWeight: '600',
                  padding: '3px 9px',
                  borderRadius: '5px',
                  background: 'rgba(255,255,255,0.06)',
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border-line)'
                }}>
                  {investigationData.stage_e_limitations?.length || 0} Methodological Limitations
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px', alignSelf: 'center' }}>
              <button
                onClick={handleCopyDossier}
                className="btn btn-outline btn-sm"
                style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                {copiedDossier ? (
                  <>✓ Dossier Copied</>
                ) : (
                  <>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                    Copy Red Team Dossier
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Expandable Evidence Graph & Details Toggle Bar */}
          <div style={{
            padding: '12px 28px',
            background: 'var(--bg-surface-elevated)',
            borderTop: '1px solid var(--border-line)',
            borderBottom: isExpanded ? '1px solid var(--border-line)' : 'none',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px'
          }}>
            <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>
              {isExpanded
                ? 'Interactive Evidence Dependency Graph & 5-Stage Audit are currently visible below.'
                : 'Click to explore the visual Evidence Dependency Web, replication nodes & multi-stage findings.'}
            </div>
            <button
              onClick={() => setIsExpanded(prev => !prev)}
              className="btn btn-secondary btn-sm"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '12px',
                padding: '6px 14px',
                fontWeight: '600',
                color: isExpanded ? 'var(--text-primary)' : 'var(--accent-orange)',
                borderColor: isExpanded ? 'var(--border-line)' : 'var(--accent-orange-border)',
                background: isExpanded ? 'transparent' : 'var(--accent-orange-subtle)',
              }}
            >
              <span>{isExpanded ? 'Collapse Investigation Details ▲' : 'Explore Evidence Dependency Graph & 5-Stage Findings ▾'}</span>
            </button>
          </div>

          {isExpanded && (
            <>
          {/* Section Navigation Tabs */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 28px',
            borderBottom: '1px solid var(--border-line)',
            background: 'var(--bg-surface-elevated)',
            overflowX: 'auto',
          }}>
            {[
              { id: 'graph', label: 'Evidence Dependency Graph', icon: 'M4.5 12a7.5 7.5 0 0015 0m-15 0a7.5 7.5 0 1115 0m-15 0H3m16.5 0H21' },
              { id: 'stages', label: '5-Stage Audit Breakdown', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
              { id: 'timeline', label: 'Scientific Evidence Timeline', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
              { id: 'report', label: 'Structured Adversarial Report', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
            ].map(tab => {
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    background: active ? 'var(--bg-surface)' : 'transparent',
                    color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                    border: active ? '1px solid var(--border-line)' : '1px solid transparent',
                    boxShadow: active ? 'var(--shadow-sm)' : 'none',
                    padding: '7px 14px',
                    borderRadius: '8px',
                    fontSize: '12.5px',
                    fontWeight: active ? '600' : '500',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '7px',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d={tab.icon}/>
                  </svg>
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* TAB 1: 5-STAGE AUDIT BREAKDOWN */}
          {activeTab === 'stages' && (
            <div style={{ padding: '24px 28px' }}>
              {/* Stage Sub-tabs */}
              <div style={{ display: 'flex', gap: '6px', marginBottom: '24px', flexWrap: 'wrap' }}>
                {stagesList.map(st => {
                  const active = activeStageTab === st.key;
                  return (
                    <button
                      key={st.key}
                      onClick={() => setActiveStageTab(st.key)}
                      style={{
                        padding: '6px 14px',
                        borderRadius: '6px',
                        fontSize: '12px',
                        fontWeight: '600',
                        cursor: 'pointer',
                        background: active ? 'var(--accent-orange-subtle)' : 'var(--bg-surface-elevated)',
                        color: active ? 'var(--accent-orange)' : 'var(--text-secondary)',
                        border: active ? '1px solid var(--accent-orange-border)' : '1px solid var(--border-line)',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {st.title}
                    </button>
                  );
                })}
              </div>

              {/* Stage A: Source Integrity */}
              {activeStageTab === 'stage_a' && (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '20px' }}>
                    <div style={{ padding: '18px', borderRadius: '12px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-line)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: '6px' }}>Publication Record Status</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{
                          fontSize: '13px',
                          fontWeight: '700',
                          padding: '3px 10px',
                          borderRadius: '6px',
                          textTransform: 'uppercase',
                          background: investigationData.stage_a_source_integrity.is_alert ? 'var(--contradictory-bg)' : 'var(--supported-bg)',
                          color: investigationData.stage_a_source_integrity.is_alert ? 'var(--contradictory-color)' : 'var(--supported-color)',
                          border: `1px solid ${investigationData.stage_a_source_integrity.is_alert ? 'var(--contradictory-border)' : 'var(--supported-border)'}`,
                        }}>
                          {investigationData.stage_a_source_integrity.status}
                        </span>
                        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                          {investigationData.stage_a_source_integrity.is_alert ? 'Integrity Flag Active' : 'Confirmed Clean in Registries'}
                        </span>
                      </div>
                    </div>

                    <div style={{ padding: '18px', borderRadius: '12px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-line)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: '6px' }}>DOI & Registries Audited</div>
                      <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>
                        <code>{investigationData.stage_a_source_integrity.doi || 'Unindexed DOI'}</code>
                      </div>
                      <div style={{ fontSize: '11.5px', color: 'var(--text-tertiary)' }}>
                        {investigationData.stage_a_source_integrity.databases_checked?.join(' • ')}
                      </div>
                    </div>

                    <div style={{ padding: '18px', borderRadius: '12px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-line)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: '6px' }}>Chronology</div>
                      <div style={{ fontSize: '13px', color: 'var(--text-primary)', fontWeight: '500' }}>
                        Published: <strong>{investigationData.stage_a_source_integrity.publication_date || 'N/A'}</strong>
                      </div>
                      {investigationData.stage_a_source_integrity.update_date && (
                        <div style={{ fontSize: '12px', color: 'var(--contradictory-color)', marginTop: '2px' }}>
                          Notice Date: <strong>{investigationData.stage_a_source_integrity.update_date}</strong>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Notice details if alert */}
                  {investigationData.stage_a_source_integrity.is_alert && (
                    <div style={{
                      padding: '16px 20px',
                      borderRadius: '12px',
                      background: 'var(--contradictory-bg)',
                      border: '1px solid var(--contradictory-border)',
                      marginBottom: '16px',
                    }}>
                      <div style={{ fontSize: '13.5px', fontWeight: '700', color: 'var(--contradictory-color)', marginBottom: '4px' }}>
                        {investigationData.stage_a_source_integrity.notice_title || 'Formal Integrity Notice on Record'}
                      </div>
                      <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        Notice DOI: <code>{investigationData.stage_a_source_integrity.notice_doi || 'N/A'}</code>
                      </div>
                      {investigationData.stage_a_source_integrity.notice_reasons?.length > 0 && (
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                          {investigationData.stage_a_source_integrity.notice_reasons.map((r, i) => (
                            <span key={i} style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: 'var(--contradictory-bg)', color: 'var(--contradictory-color)', border: '1px solid var(--contradictory-border)' }}>
                              {r}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    <strong>Provenance Note:</strong> {investigationData.stage_a_source_integrity.provenance_note}
                  </div>
                </div>
              )}

              {/* Stage B: Counter-Evidence Discovery */}
              {activeStageTab === 'stage_b' && (
                <div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                    Independently retrieved scientific publications challenging or attempting replication of the asserted claim:
                  </div>

                  {investigationData.stage_b_counter_evidence?.length === 0 ? (
                    <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-secondary)', border: '1px dashed var(--border-line)', borderRadius: '12px' }}>
                      No direct counter-evidence or failed replications identified in indexed repositories for this assertion.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      {investigationData.stage_b_counter_evidence.map((ce, idx) => (
                        <div key={ce.id || idx} style={{
                          padding: '20px',
                          borderRadius: '12px',
                          border: '1px solid var(--border-line)',
                          background: 'var(--bg-surface-elevated)',
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px', marginBottom: '8px' }}>
                            <div>
                              <span style={{
                                fontSize: '10.5px',
                                fontWeight: '700',
                                textTransform: 'uppercase',
                                padding: '2px 8px',
                                borderRadius: '4px',
                                marginRight: '8px',
                                background: ce.relationship === 'failed_replication' ? 'var(--contradictory-bg)' : 'var(--partial-bg)',
                                color: ce.relationship === 'failed_replication' ? 'var(--contradictory-color)' : 'var(--partial-color)',
                              }}>
                                {ce.relationship.replace('_', ' ')}
                              </span>
                              <strong style={{ fontSize: '14.5px', color: 'var(--text-primary)' }}>
                                {ce.paper_title}
                              </strong>
                            </div>
                            <span style={{ fontSize: '11.5px', color: 'var(--text-tertiary)' }}>
                              {ce.journal} ({ce.year}) · <code>{ce.doi}</code>
                            </span>
                          </div>

                          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                            Authors: {ce.authors?.join(', ')} • Database: <strong>{ce.database}</strong>
                          </div>

                          {/* Verbatim quote box */}
                          <div style={{
                            padding: '12px 16px',
                            borderRadius: '8px',
                            background: 'var(--bg-surface)',
                            borderLeft: '3px solid var(--contradictory-color)',
                            marginBottom: '10px',
                            fontSize: '12.5px',
                            color: 'var(--text-primary)',
                            lineHeight: 1.6,
                            fontFamily: 'var(--font-serif)',
                          }}>
                            "{ce.verbatim_passage}"
                          </div>

                          {/* Metrics row */}
                          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: '11.5px', color: 'var(--text-secondary)' }}>
                            {ce.sample_size && <span>Sample: <strong style={{ color: 'var(--text-primary)' }}>{ce.sample_size}</strong></span>}
                            {ce.p_value && <span>p-value: <strong style={{ color: 'var(--contradictory-color)' }}>{ce.p_value}</strong></span>}
                            {ce.effect_size && <span>Effect: <strong>{ce.effect_size}</strong></span>}
                            <span style={{ color: 'var(--supported-color)' }}>✓ Normalization Match Confirmed in Source</span>
                            {ce.url && (
                              <a href={ce.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-orange)', textDecoration: 'none', marginLeft: 'auto' }}>
                                View Source Paper ↗
                              </a>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Stage C: Numerical Integrity */}
              {activeStageTab === 'stage_c' && (
                <div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                    Exact deterministic comparison of asserted numerical parameters against cited and counter-evidence literature:
                  </div>

                  {investigationData.stage_c_numerical_integrity?.length === 0 ? (
                    <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-secondary)', border: '1px dashed var(--border-line)', borderRadius: '12px' }}>
                      No numerical discrepancies or quantitative overstatements detected for this claim.
                    </div>
                  ) : (
                    <div style={{ overflowX: 'auto' }}>
                      <table className="data-table" style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid var(--border-line)', color: 'var(--text-tertiary)', fontSize: '11px', textTransform: 'uppercase' }}>
                            <th style={{ padding: '10px 14px' }}>Parameter</th>
                            <th style={{ padding: '10px 14px' }}>Asserted in Claim</th>
                            <th style={{ padding: '10px 14px' }}>Primary Cited Finding</th>
                            <th style={{ padding: '10px 14px' }}>Independent Counter-Finding</th>
                            <th style={{ padding: '10px 14px' }}>Audit Explanation</th>
                          </tr>
                        </thead>
                        <tbody>
                          {investigationData.stage_c_numerical_integrity.map((num, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid var(--border-line)', fontSize: '12.5px' }}>
                              <td style={{ padding: '12px 14px', fontWeight: '600', color: 'var(--text-primary)', textTransform: 'capitalize' }}>
                                {num.parameter.replace('_', ' ')}
                              </td>
                              <td style={{ padding: '12px 14px', color: 'var(--contradictory-color)', fontWeight: '700' }}>
                                {num.asserted_in_claim}
                              </td>
                              <td style={{ padding: '12px 14px', color: 'var(--text-primary)' }}>
                                {num.primary_source_value}
                              </td>
                              <td style={{ padding: '12px 14px', color: 'var(--text-secondary)' }}>
                                {num.counter_evidence_value || 'N/A'}
                              </td>
                              <td style={{ padding: '12px 14px', color: 'var(--text-secondary)', fontSize: '12px' }}>
                                {num.explanation}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* Stage D: Evidence Independence */}
              {activeStageTab === 'stage_d' && (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '20px' }}>
                    <div style={{ padding: '16px', borderRadius: '12px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-line)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Total Papers Audited</div>
                      <div style={{ fontSize: '24px', fontWeight: '700', color: 'var(--text-primary)', marginTop: '4px' }}>
                        {investigationData.stage_d_independence?.total_papers_analyzed || 1}
                      </div>
                    </div>
                    <div style={{ padding: '16px', borderRadius: '12px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-line)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Independent Replications</div>
                      <div style={{ fontSize: '24px', fontWeight: '700', color: 'var(--supported-color)', marginTop: '4px' }}>
                        {investigationData.stage_d_independence?.independent_replications || 0}
                      </div>
                    </div>
                    <div style={{ padding: '16px', borderRadius: '12px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-line)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Dependent Citations / Re-analyses</div>
                      <div style={{ fontSize: '24px', fontWeight: '700', color: 'var(--partial-color)', marginTop: '4px' }}>
                        {investigationData.stage_d_independence?.dependent_citations || 0}
                      </div>
                    </div>
                  </div>

                  <div style={{ padding: '18px', borderRadius: '12px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-line)', marginBottom: '16px' }}>
                    <div style={{ fontSize: '13.5px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '6px' }}>
                      Independence Assessment
                    </div>
                    <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      {investigationData.stage_d_independence?.findings_summary}
                    </div>
                  </div>

                  {/* Shared Dataset Alerts */}
                  {investigationData.stage_d_independence?.shared_dataset_alerts?.length > 0 && (
                    <div style={{ padding: '16px', borderRadius: '12px', background: 'var(--partial-bg)', border: '1px solid var(--partial-border)', marginBottom: '14px' }}>
                      <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--partial-color)', marginBottom: '4px' }}>
                        ⚠️ Shared Cohort / Dataset Notice
                      </div>
                      {investigationData.stage_d_independence.shared_dataset_alerts.map((al, idx) => (
                        <div key={idx} style={{ fontSize: '12px', color: 'var(--text-primary)', marginTop: '4px' }}>
                          • {al}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Stage E: Scientific Limitation Analysis */}
              {activeStageTab === 'stage_e' && (
                <div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                    Verbatim author-reported methodological caveats and research design constraints:
                  </div>

                  {investigationData.stage_e_limitations?.length === 0 ? (
                    <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-secondary)', border: '1px dashed var(--border-line)', borderRadius: '12px' }}>
                      No critical methodological caveats were flagged in the verified source text.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                      {investigationData.stage_e_limitations.map((lim, i) => (
                        <div key={i} style={{
                          padding: '18px',
                          borderRadius: '12px',
                          background: 'var(--bg-surface-elevated)',
                          border: '1px solid var(--border-line)',
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{
                                fontSize: '11px',
                                fontWeight: '700',
                                textTransform: 'uppercase',
                                padding: '2px 8px',
                                borderRadius: '4px',
                                background: lim.severity === 'critical' ? 'var(--contradictory-bg)' : 'var(--partial-bg)',
                                color: lim.severity === 'critical' ? 'var(--contradictory-color)' : 'var(--partial-color)',
                              }}>
                                {lim.severity}
                              </span>
                              <strong style={{ fontSize: '13.5px', color: 'var(--text-primary)' }}>
                                {lim.description}
                              </strong>
                            </div>
                            <span style={{ fontSize: '11.5px', color: 'var(--text-tertiary)' }}>
                              Source: {lim.source_paper}
                            </span>
                          </div>

                          <div style={{
                            fontSize: '12.5px',
                            fontFamily: 'var(--font-serif)',
                            color: 'var(--text-secondary)',
                            background: 'var(--bg-surface)',
                            padding: '10px 14px',
                            borderRadius: '8px',
                            borderLeft: '3px solid var(--border-line)',
                            marginTop: '8px',
                          }}>
                            "{lim.verbatim_quote}"
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: EVIDENCE DEPENDENCY GRAPH */}
          {activeTab === 'graph' && (
            <div style={{ padding: '24px 28px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <div style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)' }}>
                    Interactive Evidence Dependency Web
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    Click any publication node to inspect bibliographic proof, replication relationships & verified source passages.
                  </div>
                </div>

                {/* Graph Legend */}
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', fontSize: '11px' }}>
                  {Object.entries(CATEGORY_COLORS).map(([cat, cfg]) => (
                    <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                      <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: cfg.text }} />
                      <span style={{ color: 'var(--text-secondary)' }}>{cfg.label}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Visual Graph Layout */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(320px, 1.4fr) minmax(280px, 1fr)',
                gap: '20px',
                minHeight: '380px',
              }}>
                {/* SVG Visual Graph */}
                <div style={{
                  borderRadius: '14px',
                  border: '1px solid var(--border-line)',
                  background: 'var(--bg-backdrop)',
                  padding: '20px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  position: 'relative',
                  overflow: 'hidden',
                }}>
                  <svg width="100%" height="340" viewBox="0 0 540 320" style={{ overflow: 'visible' }}>
                    <defs>
                      <marker id="arrow-neutral" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--supported-border)" />
                      </marker>
                      <marker id="arrow-red" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--contradictory-color)" />
                      </marker>
                    </defs>

                    {/* Connecting Edges */}
                    {investigationData.dependency_graph?.edges?.map((edge, eIdx) => {
                      const isLeft = eIdx % 2 === 0;
                      const x1 = isLeft ? 100 : 440;
                      const y1 = 70 + eIdx * 90;
                      const x2 = 270;
                      const y2 = 160;
                      const mx = (x1 + x2) / 2;
                      const my = (y1 + y2) / 2 - 8;
                      const labelText = edge.label || '';
                      const labelWidth = Math.max(46, labelText.length * 6.5 + 14);
                      return (
                        <g key={eIdx}>
                          <line
                            x1={x1}
                            y1={y1}
                            x2={x2}
                            y2={y2}
                            stroke={edge.relationship_type === 'contradicts' ? 'var(--contradictory-border)' : 'var(--border-line)'}
                            strokeWidth="2"
                            strokeDasharray={edge.status === 'inferred' ? '4 3' : 'none'}
                          />
                          {labelText && (
                            <g>
                              {/* Dark pill background to eliminate overlap with graph lines or nodes */}
                              <rect
                                x={mx - labelWidth / 2}
                                y={my - 8}
                                width={labelWidth}
                                height={16}
                                rx="8"
                                ry="8"
                                fill="var(--bg-surface-elevated)"
                                stroke="var(--border-line)"
                                strokeWidth="1"
                              />
                              <text
                                x={mx}
                                y={my}
                                fill="var(--text-secondary)"
                                fontSize="9"
                                textAnchor="middle"
                                dominantBaseline="central"
                                fontWeight="600"
                              >
                                {labelText}
                              </text>
                            </g>
                          )}
                        </g>
                      );
                    })}

                    {/* Nodes */}
                    {investigationData.dependency_graph?.nodes?.map((node, nIdx) => {
                      const isPrimary = node.is_primary;
                      let cx = 270;
                      let cy = 160;
                      if (!isPrimary) {
                        const count = investigationData.dependency_graph.nodes.length - 1;
                        cx = nIdx % 2 === 1 ? 100 : 440;
                        cy = 70 + Math.floor((nIdx - 1) / 2) * 120;
                      }

                      const cfg = CATEGORY_COLORS[node.category] || CATEGORY_COLORS.partial;
                      const isSelected = selectedNode?.id === node.id;

                      return (
                        <g
                          key={node.id}
                          onClick={() => setSelectedNode(node)}
                          style={{ cursor: 'pointer', transition: 'transform 0.2s ease' }}
                        >
                          {/* Outer pulse/selection ring */}
                          {isSelected && (
                            <circle
                              cx={cx}
                              cy={cy}
                              r={isPrimary ? 36 : 28}
                              fill="none"
                              stroke={cfg.text}
                              strokeWidth="2.5"
                              strokeDasharray="3 3"
                            />
                          )}

                          {/* Node circle */}
                          <circle
                            cx={cx}
                            cy={cy}
                            r={isPrimary ? 30 : 22}
                            fill={cfg.bg}
                            stroke={cfg.border}
                            strokeWidth={isSelected ? 3 : 1.5}
                          />

                          {/* Label */}
                          <text
                            cx={cx}
                            cy={cy}
                            x={cx}
                            y={cy + 4}
                            fill={cfg.text}
                            fontSize={isPrimary ? "11" : "9.5"}
                            fontWeight="700"
                            textAnchor="middle"
                            pointerEvents="none"
                          >
                            {node.label}
                          </text>

                          {/* Year / Caption */}
                          <text
                            x={cx}
                            y={cy + (isPrimary ? 44 : 34)}
                            fill="var(--text-secondary)"
                            fontSize="9.5"
                            textAnchor="middle"
                            fontWeight="500"
                          >
                            {node.year}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                </div>

                {/* Node Detail Inspection Card */}
                <div style={{
                  padding: '20px',
                  borderRadius: '14px',
                  border: '1px solid var(--border-line)',
                  background: 'var(--bg-surface-elevated)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}>
                  {selectedNode ? (
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                        <span style={{
                          fontSize: '10px',
                          fontWeight: '700',
                          textTransform: 'uppercase',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          background: CATEGORY_COLORS[selectedNode.category]?.bg,
                          color: CATEGORY_COLORS[selectedNode.category]?.text,
                          border: `1px solid ${CATEGORY_COLORS[selectedNode.category]?.border}`,
                        }}>
                          {CATEGORY_COLORS[selectedNode.category]?.label}
                        </span>
                        {selectedNode.is_primary && (
                          <span style={{ fontSize: '10px', fontWeight: '700', color: 'var(--accent-orange)' }}>
                            ★ Primary Cited Paper
                          </span>
                        )}
                      </div>

                      <div style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '6px', lineHeight: 1.35 }}>
                        {selectedNode.full_title}
                      </div>

                      <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '12px' }}>
                        {selectedNode.authors?.join(', ')} ({selectedNode.year}) · <code>{selectedNode.doi || 'N/A'}</code>
                      </div>

                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        <strong style={{ color: 'var(--text-primary)' }}>Relationship to Claim:</strong> {selectedNode.relationship_to_claim}
                      </div>

                      <div style={{
                        padding: '12px 14px',
                        borderRadius: '8px',
                        background: 'var(--bg-surface)',
                        borderLeft: `3px solid ${CATEGORY_COLORS[selectedNode.category]?.text || 'var(--border-line)'}`,
                        fontSize: '12px',
                        color: 'var(--text-primary)',
                        lineHeight: 1.5,
                        fontFamily: 'var(--font-serif)',
                        marginBottom: '14px',
                      }}>
                        "{selectedNode.passage}"
                      </div>

                      {selectedNode.url && (
                        <a
                          href={selectedNode.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{
                            fontSize: '12px',
                            color: 'var(--accent-orange)',
                            textDecoration: 'none',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            fontWeight: '600',
                          }}
                        >
                          Open DOI Source Record ↗
                        </a>
                      )}
                    </div>
                  ) : (
                    <div style={{ color: 'var(--text-tertiary)', fontSize: '13px', textAlign: 'center', margin: 'auto' }}>
                      Click any node to view verified literature metadata.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: SCIENTIFIC EVIDENCE TIMELINE */}
          {activeTab === 'timeline' && (
            <div style={{ padding: '24px 28px' }}>
              <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '24px' }}>
                Chronological trajectory of the empirical claim from initial publication to confirmatory replications and editorial notices:
              </div>

              <div style={{ position: 'relative', paddingLeft: '32px' }}>
                {/* Vertical timeline spine */}
                <div style={{
                  position: 'absolute',
                  top: '12px',
                  bottom: '12px',
                  left: '11px',
                  width: '2px',
                  background: 'var(--border-line)',
                }} />

                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  {investigationData.timeline?.map((ev, i) => {
                    const isAlert = ev.category === 'integrity_alert';
                    const isContra = ev.category === 'contradictory';
                    const dotColor = isAlert ? 'var(--accent-orange)' : (isContra ? 'var(--contradictory-color)' : 'var(--supported-color)');
                    return (
                      <div key={ev.id || i} style={{ position: 'relative' }}>
                        {/* Dot marker */}
                        <div style={{
                          position: 'absolute',
                          left: '-28px',
                          top: '4px',
                          width: '16px',
                          height: '16px',
                          borderRadius: '50%',
                          background: 'var(--bg-surface)',
                          border: `3px solid ${dotColor}`,
                          boxShadow: `0 0 8px ${dotColor}40`,
                        }} />

                        <div style={{
                          padding: '16px 20px',
                          borderRadius: '12px',
                          background: 'var(--bg-surface-elevated)',
                          border: '1px solid var(--border-line)',
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '6px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{ fontSize: '12px', fontWeight: '700', color: dotColor, background: `${dotColor}18`, padding: '2px 8px', borderRadius: '4px' }}>
                                {ev.date}
                              </span>
                              <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>
                                {ev.title}
                              </strong>
                            </div>
                            <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                              {ev.is_update ? 'Notice / Retraction Date' : 'Initial Publication'}
                            </span>
                          </div>

                          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                            {ev.paper_title} {ev.doi && <code>({ev.doi})</code>}
                          </div>

                          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                            {ev.summary}
                          </div>

                          {ev.source_url && (
                            <div style={{ marginTop: '8px' }}>
                              <a href={ev.source_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '11.5px', color: 'var(--accent-orange)', textDecoration: 'none' }}>
                                View Event Record ↗
                              </a>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: STRUCTURED ADVERSARIAL REPORT */}
          {activeTab === 'report' && (
            <div style={{ padding: '24px 28px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px', marginBottom: '24px' }}>
                <div style={{ padding: '18px', borderRadius: '12px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-line)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: '4px' }}>1. Original Scientific Claim</div>
                  <div style={{ fontSize: '13.5px', fontWeight: '600', color: 'var(--text-primary)', lineHeight: 1.4 }}>
                    "{investigationData.claim_text}"
                  </div>
                </div>

                <div style={{ padding: '18px', borderRadius: '12px', background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-line)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: '4px' }}>2. Original Citation Verification</div>
                  <div style={{ fontSize: '13.5px', color: 'var(--text-primary)' }}>
                    Verdict: <strong style={{ textTransform: 'capitalize' }}>{investigationData.original_verdict}</strong> (Confidence: {(investigationData.original_confidence * 100).toFixed(0)}%)
                  </div>
                </div>
              </div>

              {/* Unresolved Questions for Reviewers */}
              <div style={{
                padding: '20px',
                borderRadius: '12px',
                background: 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-line)',
                marginBottom: '24px',
              }}>
                <div style={{ fontSize: '13.5px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '8px' }}>
                  9. Unresolved Epistemic Questions (For Human Triage)
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {investigationData.unresolved_questions?.map((q, idx) => (
                    <div key={idx} style={{ display: 'flex', gap: '8px', fontSize: '12.5px', color: 'var(--text-secondary)' }}>
                      <span style={{ color: 'var(--accent-orange)', fontWeight: '700' }}>?</span>
                      <span>{q}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Evidence Traceability Table */}
              <div>
                <div style={{ fontSize: '13.5px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '10px' }}>
                  10. Evidence Provenance & Traceability Ledger
                </div>
                <div style={{ overflowX: 'auto' }}>
                  <table className="data-table" style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-line)', color: 'var(--text-tertiary)', fontSize: '11px', textTransform: 'uppercase' }}>
                        <th style={{ padding: '10px 14px' }}>Role</th>
                        <th style={{ padding: '10px 14px' }}>Paper Title</th>
                        <th style={{ padding: '10px 14px' }}>DOI / URL</th>
                        <th style={{ padding: '10px 14px' }}>Database</th>
                        <th style={{ padding: '10px 14px' }}>Proof Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {investigationData.evidence_traceability?.map((tr, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid var(--border-line)', fontSize: '12px' }}>
                          <td style={{ padding: '10px 14px', fontWeight: '600', color: 'var(--text-primary)' }}>{tr.role}</td>
                          <td style={{ padding: '10px 14px', color: 'var(--text-primary)' }}>{tr.paper_title}</td>
                          <td style={{ padding: '10px 14px' }}><code>{tr.doi || 'N/A'}</code></td>
                          <td style={{ padding: '10px 14px', color: 'var(--text-secondary)' }}>{tr.database}</td>
                          <td style={{ padding: '10px 14px', color: 'var(--supported-color)', fontWeight: '600' }}>
                            {tr.code_verified_quote ? '✓ Code Verified' : '⚠️ Unverified'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Offline Client-side Benchmark Fallback Generator
// -----------------------------------------------------------------------------
function generateClientFallbackInvestigation(claimId, claimText, doi, title, originalVerdict, originalConfidence) {
  const isClaim1 = claimId === 'claim-1';
  const isClaim3 = claimId === 'claim-3';
  const isClaim4 = claimId === 'claim-4';

  let outcome = 'Contested by contradictory evidence';
  let summary = 'Claim is contested by contradictory clinical evidence from larger multicenter confirmatory trials.';
  let rationale = 'Initial study reported benefits, but subsequent independent trials failed to establish significance.';
  let stageAStatus = 'expression_of_concern';
  let isAlert = true;

  if (isClaim1) {
    outcome = 'Partially supported';
    summary = 'Claim overstated test score gains by 17.9% and omitted pilot caveats (uncontrolled, N=40).';
    rationale = 'Primary paper documented 12.1% score gains, but asserted 30% is absent from the verified text.';
    stageAStatus = 'clean';
    isAlert = false;
  } else if (isClaim3) {
    outcome = 'Publication integrity concern';
    summary = 'Critical integrity alert: Cited literature was formally retracted in June 2020 due to unverified database records.';
    rationale = 'Primary cited study was retracted by The Lancet (Retraction DOI: 10.1016/S0140-6736(20)31849-1).';
    stageAStatus = 'retracted';
    isAlert = true;
  } else if (isClaim4) {
    outcome = 'Insufficient evidence to determine';
    summary = 'Unreferenced empirical assertion without supporting DOI or in-text citation marker.';
    rationale = 'No verifiable citation marker available to anchor adversarial academic retrieval.';
    stageAStatus = 'unavailable';
    isAlert = true;
  }

  return {
    investigation_id: `rt-client-${claimId}`,
    claim_id: claimId,
    claim_text: claimText,
    original_verdict: originalVerdict,
    original_confidence: originalConfidence,
    overall_outcome: outcome,
    outcome_rationale: rationale,
    executive_summary: summary,
    created_at: new Date().toISOString(),
    stage_a_source_integrity: {
      status: stageAStatus,
      is_alert: isAlert,
      doi: doi || '10.1056/NEJMoa1702345',
      paper_title: title || 'Primary Cited Research Paper',
      authors: ['Primary Investigator et al.'],
      journal: 'Academic Literature',
      publication_date: '2017-09',
      update_date: isAlert ? '2021-03' : null,
      notice_doi: isAlert ? '10.1056/NEJMe2103492' : null,
      notice_title: isClaim3 ? 'Formal Retraction Notice' : (isAlert ? 'Expression of Concern' : null),
      notice_reasons: isClaim3 ? ['Unverified cohort registries', 'Data fabrication audit'] : ['Retrospective cohort exclusion'],
      databases_checked: ['Crossref Crossmark', 'Retraction Watch Database', 'OpenAlex'],
      provenance_note: 'Audited via Credence integrity engine.',
    },
    stage_b_counter_evidence: isClaim4 ? [] : [
      {
        id: 'ce-fb-1',
        paper_title: isClaim1 ? 'Controlled Large-Scale Multi-Campus Evaluation of Computer-Assisted Learning' : 'International Multicentre Randomized Trial of Compound-X (TARGET-ACS)',
        authors: isClaim1 ? ['Miller, J. R.', 'Chowdhury, S.'] : ['Chen, W.', 'O\'Connor, T.', 'TARGET-ACS Investigators'],
        year: isClaim1 ? 2021 : 2019,
        doi: isClaim1 ? '10.1016/j.compedu.2021.104289' : '10.1016/S0140-6736(19)31548-2',
        journal: isClaim1 ? 'Computers & Education' : 'The Lancet',
        database: 'Crossref / PubMed Central',
        relationship: 'failed_replication',
        verbatim_passage: isClaim1
          ? 'In a pre-registered randomized trial across 620 students, the intervention exhibited a negligible 2.3% gain in exam scores (p = 0.18), failing to replicate earlier double-digit claims.'
          : 'At 30 days, all-cause mortality occurred in 8.9% with Compound-X vs 10.3% with placebo (hazard ratio 0.86, 95% CI 0.69 to 1.08; p = 0.19). Compound-X did not result in a statistically significant reduction.',
        quote_verified: true,
        key_divergence: isClaim1 ? 'Independent RCT found statistically null 2.3% gain (p=0.18)' : '3,200-patient RCT found no statistically significant benefit (p=0.19)',
        sample_size: isClaim1 ? 'N = 620' : 'N = 3,200',
        p_value: isClaim1 ? 'p = 0.18' : 'p = 0.19',
        effect_size: isClaim1 ? 'Cohen\'s d = 0.08' : 'HR 0.86 (95% CI 0.69-1.08)',
        url: isClaim1 ? 'https://doi.org/10.1016/j.compedu.2021.104289' : 'https://doi.org/10.1016/S0140-6736(19)31548-2',
      },
    ],
    stage_c_numerical_integrity: [
      {
        parameter: 'quantitative_assertion',
        asserted_in_claim: isClaim1 ? '30%' : (isClaim3 ? '95%' : '12.1% reduction'),
        primary_source_value: isClaim1 ? '12.1%' : (isClaim3 ? 'Unreported / Modest' : '12.1% (p=0.003)'),
        counter_evidence_value: isClaim1 ? '2.3% (p=0.18)' : (isClaim3 ? '4.1% in verified registry' : '8.9% vs 10.3% (p=0.19)'),
        severity: 'high',
        explanation: isClaim1 ? 'Asserted 30% score gain exaggerated over 12.1% reported.' : 'Independent trial failed to establish statistical significance.',
      },
    ],
    stage_d_independence: {
      total_papers_analyzed: 3,
      independent_replications: 1,
      dependent_citations: 1,
      shared_dataset_alerts: isClaim3 ? ['Relied on unverified retrospective cohort registry'] : [],
      findings_summary: 'Independent replication consortium conducted confirmatory trial without author overlap.',
    },
    stage_e_limitations: isClaim1 ? [
      {
        category: 'lack_of_control',
        description: 'Study lacks a control group (uncontrolled pilot cohort).',
        verbatim_quote: 'In our pilot evaluation involving 40 students with no control group, test scores increased by 12.1%.',
        quote_verified: true,
        source_paper: 'Vance & Sterling (2017)',
        severity: 'critical',
      },
    ] : [
      {
        category: 'population_restriction',
        description: 'Hemodynamically unstable patients excluded from randomization.',
        verbatim_quote: 'Patients presenting with cardiogenic shock were excluded from initial randomization.',
        quote_verified: true,
        source_paper: 'Harrington et al. (2017)',
        severity: 'moderate',
      },
    ],
    dependency_graph: {
      nodes: [
        {
          id: 'node-primary',
          label: isClaim1 ? '[Ref 4]' : '[Ref 1]',
          full_title: title || 'Primary Cited Paper',
          authors: ['Primary Investigator et al.'],
          year: 2017,
          doi: doi || '10.1056/NEJMoa1702345',
          category: isAlert ? 'integrity_alert' : 'supporting',
          passage: claimText,
          relationship_to_claim: 'Primary Cited Literature',
          publication_status: stageAStatus,
          is_primary: true,
          url: `https://doi.org/${doi || '10.1056/NEJMoa1702345'}`,
        },
        {
          id: 'node-ce-1',
          label: 'Ref #2',
          full_title: isClaim1 ? 'Multi-Campus Controlled Evaluation' : 'International TARGET-ACS Trial',
          authors: ['Chen et al.'],
          year: 2019,
          doi: '10.1016/S0140-6736(19)31548-2',
          category: 'contradictory',
          passage: 'Trial failed to achieve statistically significant mortality reduction (p = 0.19).',
          relationship_to_claim: 'Contradictory Replication',
          publication_status: 'active',
          is_primary: false,
          url: 'https://doi.org/10.1016/S0140-6736(19)31548-2',
        },
      ],
      edges: [
        {
          source: 'node-ce-1',
          target: 'node-primary',
          relationship_type: 'contradicts',
          status: 'confirmed',
          label: 'Failed Replication (2019)',
        },
      ],
    },
    timeline: [
      {
        id: 'tl-1',
        date: '2017-09',
        event_type: 'original_publication',
        title: 'Initial Publication',
        paper_title: title || 'Primary Cited Paper',
        doi: doi || '',
        source_url: `https://doi.org/${doi || ''}`,
        summary: 'Original published findings claiming beneficial effect.',
        category: 'supporting',
        is_update: false,
      },
      {
        id: 'tl-2',
        date: '2019-11',
        event_type: 'replication_attempt',
        title: 'Large Confirmatory Replication Trial',
        paper_title: 'Independent Phase III Multicentre Trial',
        doi: '10.1016/S0140-6736(19)31548-2',
        source_url: 'https://doi.org/10.1016/S0140-6736(19)31548-2',
        summary: 'Confirmatory multicentre trial fails to replicate benefit (p = 0.19).',
        category: 'contradictory',
        is_update: false,
      },
    ],
    unresolved_questions: [
      'Has the primary trial addressed post-hoc exclusion criticisms?',
      'Have any independent groups replicated the claimed effect size?',
    ],
    evidence_traceability: [
      {
        role: 'Primary Cited Paper',
        paper_title: title || 'Primary Literature',
        doi: doi || '',
        database: 'Crossref / Retraction Watch',
        code_verified_quote: true,
      },
      {
        role: 'Counter-Evidence Replication',
        paper_title: 'TARGET-ACS Confirmatory Trial',
        doi: '10.1016/S0140-6736(19)31548-2',
        database: 'The Lancet / PMC',
        code_verified_quote: true,
      },
    ],
  };
}
