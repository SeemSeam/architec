import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "FAQ",
  description: "Answers to the main questions about local execution, browser login, seats, trial length, and subscription shape."
};

const faqs = [
  {
    question: "Does Architec Cloud upload my repository?",
    answer:
      "The product is designed around a local-first boundary. The website manages registration, login, seats, and install approval. Analysis continues in the local CLI and skill workflow."
  },
  {
    question: "Why does the CLI use a browser login?",
    answer:
      "The browser gives the product a cleaner identity flow than collecting account credentials in the terminal. The browser confirms identity and returns a short-lived authorization code to the waiting CLI."
  },
  {
    question: "How many plans are there?",
    answer:
      "One. Every account starts on a 7-day free trial and then moves to $2/month. There is no separate free forever tier and no second paid tier."
  },
  {
    question: "Can I control which machines are using the account?",
    answer:
      "Yes. The account and admin surfaces track device seats, let you see active installs, and allow revocation of stale or unwanted devices."
  },
  {
    question: "What happens after I run `archi login`?",
    answer:
      "The CLI opens the browser approval page. Once approved, the CLI exchanges the returned auth code for local refresh credentials and a signed lease."
  },
  {
    question: "Do I need to log in every time?",
    answer:
      "No. The goal is a durable local session backed by renewable authorization state, not a fresh interactive login on every command."
  }
];

export default function FaqPage() {
  return (
    <section className="stack">
      <div className="card glass hero-copy">
        <div className="section-head">
          <p className="eyebrow">FAQ</p>
          <h1>Answer the trust and rollout questions before they become support tickets.</h1>
          <p className="page-lead">
            A product like this gets the same core questions every time: what stays local, why the browser is involved,
            how seats work, and what the subscription model actually is.
          </p>
        </div>
        <div className="hero-proof">
          <span className="status-pill ok">Trust boundary answers</span>
          <span className="status-pill">Rollout and billing clarity</span>
          <span className="status-pill">CLI authorization explained</span>
        </div>
      </div>

      <div className="faq-grid">
        {faqs.map((item) => (
          <section key={item.question} className="card faq-card">
            <div className="section-head tight">
              <p className="eyebrow">Question</p>
              <h2>{item.question}</h2>
            </div>
            <p className="muted">{item.answer}</p>
          </section>
        ))}
      </div>

      <section className="card glass cta-panel">
        <div className="section-head">
          <p className="eyebrow">Still deciding</p>
          <h2>Read the flow, review the boundary, then start the trial.</h2>
          <p className="page-lead">
            The public site should remove ambiguity before the user ever lands in the account console.
          </p>
        </div>
        <div className="button-row">
          <Link className="button" href="/how-it-works">How it works</Link>
          <Link className="button secondary" href="/register">Start trial</Link>
        </div>
      </section>
    </section>
  );
}
