import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import HomeScreen from './components/HomeScreen';
import ReportScreen from './components/ReportScreen';
import BenchmarkScreen from './components/BenchmarkScreen';

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
    return 'report'; // Default to report screen so immediate view shows report
  };
  const [currentScreen, setCurrentScreen] = useState(getInitialScreen);
  const [report, setReport] = useState(FALLBACK_DEMO_REPORT);
  const [loading, setLoading] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState('');
  const [errorMessage, setErrorMessage] = useState(null);

  useEffect(() => {
    // Fetch live demo report from backend if available
    fetch('/demo/report')
      .then(res => res.json())
      .then(data => {
        if (data && data.claims) {
          setReport(data);
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
    fetch('/demo/report')
      .then(res => res.json())
      .then(data => {
        setReport(data || FALLBACK_DEMO_REPORT);
        setCurrentScreen('report');
        setLoading(false);
        setLoadingProgress('');
      })
      .catch(() => {
        setReport(FALLBACK_DEMO_REPORT);
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

    fetch('/verify', {
      method: 'POST',
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
        setErrorMessage(
          `Verification Notice: ${err.message}. Please check that the file is an academic .pdf or .docx, or run the demo sample paper.`
        );
      });
  };

  const handleForceError = () => {
    setLoading(true);
    setErrorMessage(null);
    setLoadingProgress('Sending request to verify pipeline...');

    // Post to /verify with force_error query to test error state
    fetch('/verify?force_error=true', {
      method: 'POST',
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

  const handleReviewClaim = (reportId, claimId, actionData) => {
    return fetch(`/claims/${claimId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(actionData),
    })
      .then(res => res.json())
      .then(data => {
        // Re-fetch report from backend with SQLite review ledger applied
        const reportUrl = reportId && reportId !== 'demo-report-1' ? `/report/${reportId}` : '/demo/report';
        fetch(reportUrl)
          .then(r => r.json())
          .then(updated => {
            if (updated && updated.claims) {
              setReport(updated);
            }
          })
          .catch(() => {});
        return data;
      })
      .catch(err => {
        console.error('Failed to submit review to ledger:', err);
      });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Navbar currentScreen={currentScreen} setCurrentScreen={setCurrentScreen} />
      
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
          />
        )}
        {currentScreen === 'report' && (
          <ReportScreen
            report={report}
            onReviewClaim={handleReviewClaim}
            onNavigateHome={() => setCurrentScreen('home')}
          />
        )}
        {currentScreen === 'benchmark' && (
          <BenchmarkScreen />
        )}
      </main>
    </div>
  );
}
