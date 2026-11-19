import React from 'react';

export default function AboutScreen({ onNavigateUpload, onNavigateBenchmark }) {
  return (
    <div style={{ padding: '48px 0 88px' }}>
      <div className="container" style={{ maxWidth: '880px' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '48px' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '5px 14px',
            borderRadius: '24px',
            background: 'var(--accent-orange-subtle)',
            border: '1px solid var(--accent-orange-border)',
            color: 'var(--accent-orange)',
            fontSize: '11.5px',
            fontWeight: '700',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            marginBottom: '16px'
          }}>
            Scholarly Epistemic Architecture
          </div>
          <h1 style={{ fontSize: '38px', marginBottom: '16px' }}>About Credence</h1>
          <p style={{ fontSize: '16px', maxWidth: '640px', margin: '0 auto', lineHeight: 1.6 }}>
            A rigorous scientific claim verification engine that bridges large language models with deterministic Python code proof.
          </p>
        </div>

        {/* The Epistemic Separation Manifesto */}
        <div className="panel" style={{ padding: '32px 36px', marginBottom: '32px' }}>
          <h2 style={{ fontSize: '22px', marginBottom: '14px' }}>The Problem: Black-Box Verification & Quote Hallucination</h2>
          <p style={{ fontSize: '14px', lineHeight: 1.7, marginBottom: '16px' }}>
            Traditional AI-assisted fact-checking typically feeds a claim and a document into a large language model and asks: 
            <em>"Does this source support the claim? (Yes/No)"</em>. This paradigm suffers from critical vulnerabilities:
          </p>
          <ul style={{ paddingLeft: '20px', fontSize: '13.5px', color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: '20px' }}>
            <li><strong>Quote Hallucination:</strong> Models generate paraphrased or synthetic "quotes" that do not physically exist in the cited paper.</li>
            <li><strong>Numerical Blindness:</strong> Models frequently overlook critical numerical nuances (e.g., asserting a 30% gain when the source reported 12.1% on a pilot cohort).</li>
            <li><strong>Hedge Stripping:</strong> Epistemic qualifications like <em>"may suggest in vitro"</em> are routinely stripped into definitive causal claims like <em>"proves efficacy in humans"</em>.</li>
            <li><strong>Arbitrary Confidence:</strong> Self-reported confidence scores from language models reflect linguistic assertiveness rather than actual empirical backing.</li>
          </ul>
          <p style={{ fontSize: '14px', lineHeight: 1.7 }}>
            <strong>Credence was architected to solve this fundamentally:</strong> by enforcing strict epistemic separation between semantic interpretation and deterministic fact verification.
          </p>
        </div>

        {/* The 6 Golden Rules */}
        <div style={{ marginBottom: '36px' }}>
          <h2 style={{ fontSize: '24px', marginBottom: '20px', textAlign: 'center' }}>The Six Golden Rules</h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {[
              {
                num: '1',
                title: 'LLMs Judge Meaning Only; Python Decides Every Deterministic Fact',
                desc: 'Verbatim quote character-level existence, number and unit equality, and epistemic hedge word stripping are checked by deterministic Python regular expressions. The model can never override a code check.'
              },
              {
                num: '2',
                title: 'Golden Rule 2: Verbatim Quote Proof or Discard',
                desc: 'If a candidate quote returned by the model cannot be found verbatim in the source paper after Unicode NFKC normalization and dehyphenation, that slot is discarded and triaged as "Needs review". In our gold benchmark, this caught 10 out of 10 fabricated quotes.'
              },
              {
                num: '3',
                title: 'Confidence is Computed Mathematically, Never Self-Reported',
                desc: 'Confidence = max(0.0, min(Cap, Cap - 0.15 * unverified_slots - 0.20 * pass_disagreement)). The cap is determined strictly by the access tier: 0.90 for full text, 0.60 for abstract only, 0.20 for metadata, and 0.00 for inaccessible papers.'
              },
              {
                num: '4',
                title: '"Not Found in Databases" is Never Conflated with Fabricated',
                desc: 'When a paper cannot be retrieved across Crossref, OpenAlex, Semantic Scholar, Unpaywall, arXiv, or PMC, Credence explicitly logs which databases were queried and triages the claim to human review rather than falsely accusing an author of fabrication.'
              },
              {
                num: '5',
                title: 'Verdicts are Derived from an Immutable State Machine',
                desc: 'Final verdicts are derived strictly from the deterministic rule matrix in credence/verify/verdict.py, never from a single LLM prompt label.'
              },
              {
                num: '6',
                title: 'Default Stance is Human Review',
                desc: 'Credence is an expert triage aid, not an autonomous academic judge. All triage verdicts are open to human review (Accept, Override, Comment), permanently recorded in an append-only SQLite ledger.'
              }
            ].map(rule => (
              <div key={rule.num} className="panel" style={{ padding: '20px 24px', display: 'flex', gap: '18px', alignItems: 'flex-start' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  background: 'var(--accent-orange-subtle)',
                  color: 'var(--accent-orange)',
                  fontWeight: '700',
                  fontSize: '14px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}>
                  {rule.num}
                </div>
                <div>
                  <h3 style={{ fontSize: '16px', marginBottom: '6px' }}>{rule.title}</h3>
                  <p style={{ fontSize: '13px', lineHeight: 1.6, margin: 0 }}>{rule.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Actions Strip */}
        <div className="panel" style={{ padding: '28px 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>
              Explore Empirical Validation
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              Inspect gold-standard precision, recall, and hallucination catch rates.
            </div>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button onClick={onNavigateBenchmark} className="btn btn-secondary btn-sm">
              View Benchmark
            </button>
            <button onClick={onNavigateUpload} className="btn btn-primary btn-sm">
              Verify a Manuscript
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
