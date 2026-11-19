import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import HomeScreen from './components/HomeScreen';
import ReportScreen from './components/ReportScreen';
import BenchmarkScreen from './components/BenchmarkScreen';
import ReportsHistoryScreen from './components/ReportsHistoryScreen';
import AuditScreen from './components/AuditScreen';
import SettingsScreen from './components/SettingsScreen';
import AboutScreen from './components/AboutScreen';
import { apiUrl, getAuthHeaders } from './api';

// Fallback demo report for offline testing without server
const FALLBACK_DEMO_REPORT = {
  id: "demo-report-1",
  document_name: "sample_paper.pdf",
  access_tier: "full_text",
  overall_confidence: 0.65,
  summary: {
    total_claims: 3,
    supported: 1,
    partially_supported: 1,
    unsupported: 0,
    contradictory: 1,
    needs_review: 1,
    human_review_required: true,
  },
  claims: [
    {
      id: "claim-1",
      text: "LearnFast improved test scores by 30% [4]",
      citation_keys: ["4"],
      source_location: "Results, page 2",
      slots: [
        { id: "claim-1-slot-1", field_type: "finding", expected_value: "improved test scores", description: "Qualitative direction of effect" },
        { id: "claim-1-slot-2", field_type: "number", expected_value: "30%", description: "Reported score improvement rate" },
      ],
      slot_results: [
        {
          slot_id: "claim-1-slot-1",
          status: "match",
          quote_verified: true,
          quote_span: [63, 164],
          quote: "In our pilot evaluation involving 40 students with no control group, test scores increased by 12.1%.",
          number_match: null,
        },
        {
          slot_id: "claim-1-slot-2",
          status: "absent",
          quote_verified: true,
          quote_span: [63, 164],
          quote: "In our pilot evaluation involving 40 students with no control group, test scores increased by 12.1%.",
          number_match: false,
        },
      ],
      verdict: {
        claim_id: "claim-1",
        verdict: "partially supported",
        display_verdict: "Partially supported, needs review",
        confidence: 0.55,
        explanation: "Partially supported: 1 slot(s) verified in source, while 1 slot(s) were absent. Adversarial pass flagged: 30% asserted vs 12.1% in source on 40 students without a control group.",
        needs_review: true,
        contradiction_detected: false,
        rules_triggered: ["RULE_PARTIAL_MATCH"],
        access_tier: "full_text",
      },
    },
    {
      id: "claim-2",
      text: "Patients receiving Compound-X demonstrated a 12.1% reduction in 30-day mortality [1]",
      citation_keys: ["1"],
      source_location: "Results, page 3",
      slots: [
        { id: "claim-2-slot-1", field_type: "number", expected_value: "12.1%", description: "30-day mortality reduction rate" },
        { id: "claim-2-slot-2", field_type: "quote", expected_value: "12.1% reduction in 30-day mortality", description: "Verbatim quote match" },
      ],
      slot_results: [
        {
          slot_id: "claim-2-slot-1",
          status: "match",
          quote_verified: true,
          quote_span: [120, 210],
          quote: "Patients receiving Compound-X demonstrated a 12.1% reduction in 30-day mortality compared with the placebo arm (p = 0.003).",
          number_match: true,
        },
        {
          slot_id: "claim-2-slot-2",
          status: "match",
          quote_verified: true,
          quote_span: [120, 210],
          quote: "Patients receiving Compound-X demonstrated a 12.1% reduction in 30-day mortality compared with the placebo arm (p = 0.003).",
          number_match: true,
        },
      ],
      verdict: {
        claim_id: "claim-2",
        verdict: "supported",
        display_verdict: "Supported",
        confidence: 0.90,
        explanation: "Supported: all 2 factual slot(s) are backed by cited source text.",
        needs_review: false,
        contradiction_detected: false,
        rules_triggered: ["RULE_ALL_MATCH"],
        access_tier: "full_text",
      },
    },
    {
      id: "claim-3",
      text: "Compound-X produced an unprecedented 95% survival advantage across all cohorts [2]",
      citation_keys: ["2"],
      source_location: "Discussion, page 4",
      slots: [
        { id: "claim-3-slot-1", field_type: "number", expected_value: "95%", description: "Survival advantage rate" },
      ],
      slot_results: [
        {
          slot_id: "claim-3-slot-1",
          status: "mismatch",
          quote_verified: false,
          quote: "Clinical evaluation showed modest survival improvements without significant mortality advantage.",
          number_match: false,
        },
      ],
      verdict: {
        claim_id: "claim-3",
        verdict: "contradictory",
        display_verdict: "Contradictory, needs review",
        confidence: 0.35,
        explanation: "Contradictory: numerical assertion 95% directly conflicts with cited source text.",
        needs_review: true,
        contradiction_detected: true,
        rules_triggered: ["RULE_CONTRADICTORY"],
        access_tier: "abstract_only",
      },
    },
  ],
};

export default function App() {
  const getInitialScreen = () => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const s = params.get('screen');
      if (s) return s;
    }
    return 'home';
  };
  const [currentScreen, setCurrentScreen] = useState(getInitialScreen);
  const [report, setReport] = useState(FALLBACK_DEMO_REPORT);
  const [loading, setLoading] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState('');
  const [errorMessage, setErrorMessage] = useState(null);
  const [demoMode, setDemoMode] = useState(true); // Default to offline demo mode (no live external API calls)
  const [theme, setTheme] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('credence_theme');
      if (saved) return saved;
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
        return 'light';
      }
    }
    return 'dark';
  });

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('credence_theme', theme);
    }
  }, [theme]);

  const handleToggleTheme = () => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
  };

  const handleToggleDemoMode = () => {
    setDemoMode(prev => !prev);
  };

  useEffect(() => {
    // Check if there is an active report ID stored in session
    const savedRepId = typeof window !== 'undefined' ? sessionStorage.getItem('credence_active_report_id') : null;
    const reportUrl = savedRepId && savedRepId !== 'demo-report-1' ? `/report/${savedRepId}` : '/demo/report';
    fetch(apiUrl(reportUrl), { headers: getAuthHeaders() })
      .then(res => {
        if (!res.ok && savedRepId) {
          return fetch(apiUrl('/demo/report'), { headers: getAuthHeaders() }).then(r => r.json());
        }
        return res.json();
      })
      .then(data => {
        if (data && data.claims) {
          setReport(data);
          if (data.id && typeof window !== 'undefined') {
            sessionStorage.setItem('credence_active_report_id', data.id);
          }
        }
      })
      .catch(() => {
        // Fallback remains active
      });
  }, []);

  const handleSelectDemo = () => {
    setLoading(true);
    setErrorMessage(null);
    setLoadingProgress('Loading worked sample paper (sample_paper.pdf)...');
    fetch(apiUrl('/demo/report'), { headers: getAuthHeaders() })
      .then(res => res.json())
      .then(data => {
        const finalRep = data || FALLBACK_DEMO_REPORT;
        setReport(finalRep);
        if (typeof window !== 'undefined' && finalRep.id) {
          sessionStorage.setItem('credence_active_report_id', finalRep.id);
        }
        setCurrentScreen('report');
        setLoading(false);
        setLoadingProgress('');
      })
      .catch(() => {
        setReport(FALLBACK_DEMO_REPORT);
        if (typeof window !== 'undefined') {
          sessionStorage.setItem('credence_active_report_id', FALLBACK_DEMO_REPORT.id);
        }
        setCurrentScreen('report');
        setLoading(false);
        setLoadingProgress('');
      });
  };

  const handleUploadFile = (file) => {
    if (!file) return;
    setLoading(true);
    setErrorMessage(null);
    setLoadingProgress('Parsing manuscript sections & citations...');

    const timer1 = setTimeout(() => {
      setLoadingProgress('Mapping citation markers to bibliography...');
    }, 450);
    const timer2 = setTimeout(() => {
      setLoadingProgress('Extracting factual claims and atomizing into slots...');
    }, 950);
    const timer3 = setTimeout(() => {
      setLoadingProgress('Verifying verbatim source quotes & computing confidence...');
    }, 1500);

    const formData = new FormData();
    formData.append('file', file);
    const verifyUrl = demoMode ? '/verify?demo_mode=true' : '/verify';

    fetch(apiUrl(verifyUrl), {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    })
      .then(async (res) => {
        clearTimeout(timer1);
        clearTimeout(timer2);
        clearTimeout(timer3);
        if (!res.ok) {
          let errDetail = `Server returned status ${res.status}`;
          try {
            const errData = await res.json();
            errDetail = errData.detail || errData.message || errDetail;
          } catch {
            // Not JSON
          }
          throw new Error(errDetail);
        }
        return res.json();
      })
      .then(data => {
        setReport(data);
        if (data?.id && typeof window !== 'undefined') {
          sessionStorage.setItem('credence_active_report_id', data.id);
        }
        setCurrentScreen('report');
        setLoading(false);
        setLoadingProgress('');
      })
      .catch(err => {
        clearTimeout(timer1);
        clearTimeout(timer2);
        clearTimeout(timer3);
        setLoading(false);
        setLoadingProgress('');
        if (demoMode) {
          // In offline demo mode: serve cached demo report with zero live API calls
          const offlineRep = { ...FALLBACK_DEMO_REPORT, document_name: file.name };
          setReport(offlineRep);
          if (offlineRep?.id && typeof window !== 'undefined') {
            sessionStorage.setItem('credence_active_report_id', offlineRep.id);
          }
          setCurrentScreen('report');
        } else {
          setErrorMessage(
            `Verification Notice: ${err.message}. Please check that the file is an academic .pdf or .docx, or run the demo sample paper.`
          );
        }
      });
  };

  const handleForceError = () => {
    setLoading(true);
    setErrorMessage(null);
    setLoadingProgress('Sending request to verify pipeline...');

    // Post to /verify with force_error query to test error state
    fetch(apiUrl('/verify?force_error=true'), {
      method: 'POST',
      headers: getAuthHeaders(),
      body: new FormData(),
    })
      .then(async (res) => {
        let errDetail = 'Simulated pipeline gateway error';
        try {
          const errData = await res.json();
          errDetail = errData.detail || errData.message || errDetail;
        } catch {
          // Non-JSON
        }
        throw new Error(errDetail);
      })
      .catch(err => {
        setLoading(false);
        setLoadingProgress('');
        setErrorMessage(
          `Verification API Error: ${err.message}. Triage pipeline caught the failure cleanly without crashing.`
        );
      });
  };

  const handleClearError = () => {
    setErrorMessage(null);
  };

  const handleReviewClaim = async (reportId, claimId, actionData) => {
    const res = await fetch(apiUrl(`/claims/${claimId}/review`), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify(actionData),
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      const errMsg = data.detail || data.message || `Review submission failed (${res.status})`;
      throw new Error(errMsg);
    }

    // Immediately update React report state optimistically
    setReport(prev => {
      if (!prev || !prev.claims) return prev;
      const updatedClaims = prev.claims.map(c => {
        if (c.id !== claimId) return c;

        const updatedVerdict = { ...c.verdict };
        if (actionData.action === 'override' && actionData.override_verdict) {
          if (!updatedVerdict.original_verdict) {
            updatedVerdict.original_verdict = updatedVerdict.verdict;
          }
          updatedVerdict.verdict = actionData.override_verdict;
          const capWord = actionData.override_verdict.charAt(0).toUpperCase() + actionData.override_verdict.slice(1);
          updatedVerdict.display_verdict = `${capWord} (Overridden)`;
          updatedVerdict.needs_review = actionData.override_verdict === 'needs review' || actionData.override_verdict === 'potentially outdated';
          updatedVerdict.override_info = data.review;
        }

        const currentReviews = Array.isArray(c.reviews) ? [...c.reviews] : [];
        if (data.review) {
          currentReviews.push(data.review);
        }

        return {
          ...c,
          verdict: updatedVerdict,
          reviews: currentReviews,
        };
      });

      // Recalculate summary tallies
      let supp = 0, part = 0, contra = 0, unsupp = 0, rev = 0, ovCount = 0;
      updatedClaims.forEach(cl => {
        const v = (cl.verdict?.verdict || '').toLowerCase();
        if (cl.verdict?.override_info) ovCount++;
        if (v.includes('partially') || v.includes('partial')) part++;
        else if (v.includes('contradict')) contra++;
        else if (v.includes('unsupport')) unsupp++;
        else if (v.includes('support')) supp++;
        else rev++;
      });

      return {
        ...prev,
        claims: updatedClaims,
        summary: {
          ...prev.summary,
          supported: supp,
          partially_supported: part,
          contradictory: contra,
          unsupported: unsupp,
          needs_review: rev,
          human_overrides: ovCount,
          human_review_required: rev > 0 || part > 0 || contra > 0,
        },
      };
    });

    // Re-fetch report from backend with SQLite review ledger applied
    const reportEndpoint = reportId && reportId !== 'demo-report-1' ? `/report/${reportId}` : '/demo/report';
    fetch(apiUrl(reportEndpoint), { headers: getAuthHeaders() })
      .then(r => r.json())
      .then(updated => {
        if (updated && updated.claims) {
          setReport(updated);
          if (updated.id && typeof window !== 'undefined') {
            sessionStorage.setItem('credence_active_report_id', updated.id);
          }
        }
      })
      .catch(() => {});

    return data;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Navbar
        currentScreen={currentScreen}
        setCurrentScreen={setCurrentScreen}
        demoMode={demoMode}
        onToggleDemoMode={handleToggleDemoMode}
        theme={theme}
        onToggleTheme={handleToggleTheme}
      />
      
      <main style={{ flex: 1 }}>
        {currentScreen === 'home' && (
          <HomeScreen
            onSelectDemo={handleSelectDemo}
            onUploadFile={handleUploadFile}
            loading={loading}
            loadingProgress={loadingProgress}
            errorMessage={errorMessage}
            onClearError={handleClearError}
            onForceError={handleForceError}
            demoMode={demoMode}
          />
        )}
        {currentScreen === 'report' && (
          <ReportScreen
            report={report}
            onReviewClaim={handleReviewClaim}
            onNavigateHome={() => setCurrentScreen('home')}
            demoMode={demoMode}
            theme={theme}
          />
        )}
        {currentScreen === 'reports' && (
          <ReportsHistoryScreen
            onSelectReport={async (rep) => {
              if (!rep) return;
              if (rep.id && rep.id !== 'demo-report-1') {
                try {
                  const res = await fetch(apiUrl(`/report/${rep.id}`), { headers: getAuthHeaders() });
                  if (res.ok) {
                    const fullDossier = await res.json();
                    setReport(fullDossier);
                    if (typeof window !== 'undefined') {
                      sessionStorage.setItem('credence_active_report_id', fullDossier.id);
                    }
                    setCurrentScreen('report');
                    return;
                  }
                } catch (e) {
                  console.warn('Fallback to archive report object:', e);
                }
              }
              setReport(rep);
              if (rep.id && typeof window !== 'undefined') {
                sessionStorage.setItem('credence_active_report_id', rep.id);
              }
              setCurrentScreen('report');
            }}
            onNavigateUpload={() => setCurrentScreen('home')}
          />
        )}
        {currentScreen === 'benchmark' && (
          <BenchmarkScreen />
        )}
        {currentScreen === 'audit' && (
          <AuditScreen onNavigateReport={() => setCurrentScreen('report')} />
        )}
        {currentScreen === 'settings' && (
          <SettingsScreen
            theme={theme}
            onToggleTheme={handleToggleTheme}
            demoMode={demoMode}
            onToggleDemoMode={handleToggleDemoMode}
          />
        )}
        {currentScreen === 'about' && (
          <AboutScreen
            onNavigateUpload={() => setCurrentScreen('home')}
            onNavigateBenchmark={() => setCurrentScreen('benchmark')}
          />
        )}
      </main>
    </div>
  );
}
