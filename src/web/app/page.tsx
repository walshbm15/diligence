import type { ReactNode } from "react";

const CONTACT_EMAIL = "hello@diligenceos.example.com";
const EARLY_ACCESS_HREF = `mailto:${CONTACT_EMAIL}?subject=Diligence%20OS%20early%20access`;

/* ------------------------------------------------------------------ */
/* Content                                                             */
/* ------------------------------------------------------------------ */

const steps = [
  {
    title: "Upload the data room",
    body: "Statutory accounts, management P&L, bank statements, VAT returns and the lease — as they come, including scans and phone photos.",
  },
  {
    title: "Every fact extracted, with provenance",
    body: "AI reads each document into a structured fact table. Every figure carries its source document, page and a confidence score. Anything uncertain is routed to human verification — never guessed.",
  },
  {
    title: "Deterministic reconciliation",
    body: "Plain code — not a language model — cross-checks the facts: filings against the P&L, VAT boxes against revenue, deposits against declared takings. The maths is exact and repeatable.",
  },
  {
    title: "A cited Red Flag Report",
    body: "Each finding traced to its source page, ranked by severity, with the question to ask the seller and the SPA warranty or disclosure to request.",
  },
];

const checks = [
  {
    title: "The VAT triangle",
    body: "Box 6 outputs vs P&L revenue vs bank deposits, quarter by quarter. If the seller tells HMRC one number and you another, it shows up here — the single best fraud detector in a UK data room.",
    tag: "Fraud detection",
  },
  {
    title: "Charges Register cross-check",
    body: "Outstanding charges at Companies House compared against the debts the seller actually disclosed. Undisclosed security over the assets you're buying is a deal-changer.",
    tag: "Companies House",
  },
  {
    title: "Bank-to-books tie-out",
    body: "Do the deposits in the bank statements support the revenue in the accounts? Cash businesses drift; this measures by how much.",
    tag: "Reconciliation",
  },
  {
    title: "Statutory vs management accounts",
    body: "The audited filings and the numbers the seller shows buyers should tell the same story. Divergence is either sloppiness or salesmanship — both matter.",
    tag: "Reconciliation",
  },
  {
    title: "Lease reality check",
    body: "Term, break clauses and rent from the lease itself, checked against what the seller claims and what the P&L pays. For most cafés the lease is the business.",
    tag: "Contracts",
  },
  {
    title: "Insolvency & Gazette sweep",
    body: "The Gazette and public registers, checked for insolvency notices and proceedings against the company and its officers.",
    tag: "Public registers",
  },
];

const principles = [
  {
    title: "No citation, no finding",
    body: "Every finding in the report links to a source document and page. If we can't show you where it came from, we don't report it.",
  },
  {
    title: "Models read; code computes",
    body: "AI is used for what it's good at — reading messy documents. Every number is then reconciled by deterministic code. No language model ever does the arithmetic.",
  },
  {
    title: "Humans verify the uncertain",
    body: "When extraction confidence is low, the fact is quarantined for human review instead of being guessed. You see what was verified and what wasn't.",
  },
];

const reportContents = [
  {
    title: "Document sufficiency score",
    body: "The first thing you learn: is this data room even complete enough to diligence? Missing records are a finding, not a dead end.",
  },
  {
    title: "Findings with evidence",
    body: "Each discrepancy states the numbers that disagree, the periods affected, and the exact pages the figures came from.",
  },
  {
    title: "Questions for the seller",
    body: "Every red flag comes with the specific question to put to the seller before you go further.",
  },
  {
    title: "SPA warranty suggestions",
    body: "UK deals are often share purchases — you inherit the history. Findings map to the warranty or disclosure-letter item that protects you.",
  },
];

const roadmap = [
  {
    phase: "Available now — pilot",
    items: [
      "Café & hospitality acquisitions",
      "Five core document types: statutory accounts, management P&L, bank statements, VAT returns, lease",
      "Core reconciliation checks + Companies House and Gazette verification",
      "Cited Red Flag Report as PDF",
    ],
    current: true,
  },
  {
    phase: "In development",
    items: [
      "More business archetypes and document types",
      "Contract & lease clause risk analysis",
      "Seller call recordings — claims transcribed and checked against the numbers",
      "Wider public-register sweep: CCJs, Land Registry, FCA, food hygiene",
      "Adversarial review — a sceptic pass that challenges every finding before you see it",
    ],
    current: false,
  },
];

const navLinks = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#checks", label: "The checks" },
  { href: "#principles", label: "Principles" },
  { href: "#report", label: "The report" },
  { href: "#roadmap", label: "Roadmap" },
];

/* ------------------------------------------------------------------ */
/* Small building blocks                                               */
/* ------------------------------------------------------------------ */

function Wordmark() {
  return (
    <span className="font-display text-xl font-semibold tracking-tight text-ink-950">
      Diligence<span className="text-verify-700"> OS</span>
    </span>
  );
}

function SectionHeading({
  id,
  eyebrow,
  title,
  lede,
}: {
  id: string;
  eyebrow: string;
  title: string;
  lede?: string;
}) {
  return (
    <div className="max-w-2xl">
      <p className="text-sm font-semibold uppercase tracking-widest text-verify-700">
        {eyebrow}
      </p>
      <h2
        id={id}
        className="font-display mt-3 text-3xl font-semibold tracking-tight text-ink-950 sm:text-4xl"
      >
        {title}
      </h2>
      {lede ? (
        <p className="mt-4 text-lg leading-relaxed text-ink-600">{lede}</p>
      ) : null}
    </div>
  );
}

function CtaLink({
  href,
  children,
  variant = "primary",
}: {
  href: string;
  children: ReactNode;
  variant?: "primary" | "secondary";
}) {
  const base =
    "inline-flex items-center justify-center rounded-md px-5 py-3 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-verify-700";
  const styles =
    variant === "primary"
      ? "bg-ink-950 text-paper hover:bg-ink-800"
      : "border border-ink-300 text-ink-900 hover:border-ink-500 hover:bg-ink-50";
  return (
    <a href={href} className={`${base} ${styles}`}>
      {children}
    </a>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function Home() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Diligence OS",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
    description:
      "AI due-diligence engine for UK small-business acquisitions. Reads a seller's data room and produces a cited Red Flag Report: every discrepancy traced to a source page.",
    offers: {
      "@type": "Offer",
      availability: "https://schema.org/PreOrder",
      price: "0",
      priceCurrency: "GBP",
      description: "Pilot programme — early access by request.",
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-ink-100 bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <a href="#top" aria-label="Diligence OS — home">
            <Wordmark />
          </a>
          <nav aria-label="Primary" className="hidden items-center gap-8 md:flex">
            {navLinks.map((l) => (
              <a
                key={l.href}
                href={l.href}
                className="text-sm font-medium text-ink-600 transition-colors hover:text-ink-950"
              >
                {l.label}
              </a>
            ))}
          </nav>
          <CtaLink href={EARLY_ACCESS_HREF}>Request early access</CtaLink>
        </div>
      </header>

      <main id="top" className="flex-1">
        {/* Hero */}
        <section aria-labelledby="hero-heading" className="relative overflow-hidden">
          <div className="mx-auto max-w-6xl px-6 pb-20 pt-20 sm:pt-28">
            <div className="max-w-3xl">
              <p className="text-sm font-semibold uppercase tracking-widest text-verify-700">
                AI due diligence for UK small-business acquisitions
              </p>
              <h1
                id="hero-heading"
                className="font-display mt-5 text-4xl font-semibold leading-tight tracking-tight text-ink-950 sm:text-6xl"
              >
                Due diligence that reconciles the numbers —{" "}
                <span className="text-verify-700">not summarises the documents.</span>
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-relaxed text-ink-600">
                The same revenue must appear in the tax filings, the P&amp;L, the
                VAT returns and the bank deposits. Diligence OS reads the
                seller&apos;s data room and hunts for the places they{" "}
                <em className="font-medium not-italic text-ink-900">disagree</em> —
                then hands you a Red Flag Report where every finding is cited to
                its source page.
              </p>
              <div className="mt-9 flex flex-wrap items-center gap-4">
                <CtaLink href={EARLY_ACCESS_HREF}>Join the pilot</CtaLink>
                <CtaLink href="#how-it-works" variant="secondary">
                  See how it works
                </CtaLink>
              </div>
              <p className="mt-4 text-sm text-ink-500">
                Built for sub-£2M deals — cafés, shops, trades and other
                owner-managed businesses.
              </p>
            </div>

            {/* Eval strip */}
            <dl className="mt-16 grid max-w-3xl grid-cols-1 gap-px overflow-hidden rounded-lg border border-ink-200 bg-ink-200 sm:grid-cols-3">
              {[
                { stat: "9 / 10", label: "planted discrepancies caught" },
                { stat: "0", label: "false positives on a clean data room" },
                { stat: "0", label: "hallucinated citations" },
              ].map((s) => (
                <div key={s.label} className="flex flex-col bg-paper px-6 py-5">
                  <dd className="font-display order-first text-3xl font-semibold text-ink-950">
                    {s.stat}
                  </dd>
                  <dt className="mt-1 text-sm text-ink-600">{s.label}</dt>
                </div>
              ))}
            </dl>
            <p className="mt-3 max-w-3xl text-xs text-ink-500">
              Measured on our evaluation suite: synthetic data rooms with known,
              deliberately planted discrepancies, re-run on every change.
            </p>
          </div>
        </section>

        {/* Thesis / VAT triangle */}
        <section
          aria-labelledby="thesis-heading"
          className="border-y border-ink-100 bg-ink-50/60"
        >
          <div className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-20 lg:grid-cols-2">
            <div>
              <SectionHeading
                id="thesis-heading"
                eyebrow="Why reconciliation"
                title="One business, four versions of the truth"
                lede="Summarising documents tells you what the seller wrote. Reconciling them tells you whether it's true. Each source is a transformation of the same underlying business — so when two of them can't be tied back together, something is wrong: an error, an omission, or a fraud."
              />
              <p className="mt-6 text-lg leading-relaxed text-ink-600">
                The clearest example is the{" "}
                <strong className="font-semibold text-ink-900">VAT triangle</strong>:
                what the seller told HMRC (Box 6), what the P&amp;L claims, and
                what actually landed in the bank — compared quarter by quarter.
              </p>
            </div>

            {/* Triangle diagram */}
            <figure aria-label="The VAT triangle: VAT returns, P&L revenue and bank deposits must agree">
              <div className="rounded-xl border border-ink-200 bg-paper p-8 shadow-sm">
                <div className="grid gap-4">
                  {[
                    { doc: "VAT return", figure: "Box 6 · outputs", quarter: "Q3" },
                    { doc: "Management P&L", figure: "Revenue", quarter: "Q3" },
                    { doc: "Bank statements", figure: "Deposits", quarter: "Q3" },
                  ].map((row, i) => (
                    <div
                      key={row.doc}
                      className="flex items-center justify-between rounded-md border border-ink-200 bg-ink-50/50 px-4 py-3"
                    >
                      <div>
                        <p className="text-sm font-semibold text-ink-900">{row.doc}</p>
                        <p className="text-xs text-ink-500">
                          {row.figure} · {row.quarter}
                        </p>
                      </div>
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-semibold ${
                          i === 2
                            ? "bg-flag-600/10 text-flag-700"
                            : "bg-verify-50 text-verify-700"
                        }`}
                      >
                        {i === 2 ? "−£8,400 short" : "ties"}
                      </span>
                    </div>
                  ))}
                </div>
                <figcaption className="mt-5 border-t border-ink-100 pt-4 text-sm leading-relaxed text-ink-600">
                  <span className="font-semibold text-flag-700">Red flag.</span>{" "}
                  Declared takings exceed banked deposits for the quarter — ask
                  the seller to explain the difference before you rely on the
                  revenue figure.{" "}
                  <span className="text-ink-400">(Illustrative example.)</span>
                </figcaption>
              </div>
            </figure>
          </div>
        </section>

        {/* How it works */}
        <section aria-labelledby="how-heading" id="how-it-works" className="scroll-mt-20">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <SectionHeading
              id="how-heading"
              eyebrow="How it works"
              title="From data room to red flags in four steps"
            />
            <ol className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {steps.map((step, i) => (
                <li key={step.title} className="relative">
                  <div className="flex h-full flex-col rounded-lg border border-ink-200 bg-paper p-6">
                    <span
                      aria-hidden="true"
                      className="font-display text-sm font-semibold text-verify-700"
                    >
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <h3 className="mt-3 text-base font-semibold text-ink-950">
                      {step.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-ink-600">
                      {step.body}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Checks */}
        <section
          aria-labelledby="checks-heading"
          id="checks"
          className="scroll-mt-20 border-y border-ink-100 bg-ink-950"
        >
          <div className="mx-auto max-w-6xl px-6 py-20">
            <p className="text-sm font-semibold uppercase tracking-widest text-verify-100">
              The checks
            </p>
            <h2
              id="checks-heading"
              className="font-display mt-3 max-w-2xl text-3xl font-semibold tracking-tight text-paper sm:text-4xl"
            >
              Purpose-built for how UK small businesses actually go wrong
            </h2>
            <p className="mt-4 max-w-2xl text-lg leading-relaxed text-ink-300">
              Not generic document Q&amp;A — a catalogue of specific,
              deterministic cross-checks, each one designed around a way sellers
              overstate, omit or obscure.
            </p>
            <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {checks.map((check) => (
                <article
                  key={check.title}
                  className="flex flex-col rounded-lg border border-ink-700 bg-ink-900 p-6"
                >
                  <span className="self-start rounded-full border border-ink-600 px-3 py-1 text-xs font-medium text-ink-300">
                    {check.tag}
                  </span>
                  <h3 className="mt-4 text-base font-semibold text-paper">
                    {check.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink-300">
                    {check.body}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Principles */}
        <section aria-labelledby="principles-heading" id="principles" className="scroll-mt-20">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <SectionHeading
              id="principles-heading"
              eyebrow="Built to be trusted"
              title="Three rules the engine never breaks"
              lede="A due-diligence tool is only useful if an accountant can stand behind its output. The architecture enforces that, not a disclaimer."
            />
            <div className="mt-12 grid gap-6 lg:grid-cols-3">
              {principles.map((p) => (
                <article
                  key={p.title}
                  className="rounded-lg border-l-4 border-verify-700 bg-verify-50/50 p-6"
                >
                  <h3 className="font-display text-lg font-semibold text-ink-950">
                    {p.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink-700">{p.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* The report */}
        <section
          aria-labelledby="report-heading"
          id="report"
          className="scroll-mt-20 border-y border-ink-100 bg-ink-50/60"
        >
          <div className="mx-auto max-w-6xl px-6 py-20">
            <SectionHeading
              id="report-heading"
              eyebrow="The deliverable"
              title="A report you can take to your accountant — and your solicitor"
              lede="The output isn't a chat window. It's a structured Red Flag Report, designed to slot straight into how UK deals are actually done."
            />
            <div className="mt-12 grid gap-6 sm:grid-cols-2">
              {reportContents.map((item) => (
                <article
                  key={item.title}
                  className="rounded-lg border border-ink-200 bg-paper p-6"
                >
                  <h3 className="text-base font-semibold text-ink-950">{item.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink-600">
                    {item.body}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Roadmap */}
        <section aria-labelledby="roadmap-heading" id="roadmap" className="scroll-mt-20">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <SectionHeading
              id="roadmap-heading"
              eyebrow="Where this is going"
              title="Starting narrow, on purpose"
              lede="We're proving the engine on one archetype end-to-end before widening. Depth over breadth is what makes the findings trustworthy."
            />
            <div className="mt-12 grid gap-6 lg:grid-cols-2">
              {roadmap.map((phase) => (
                <article
                  key={phase.phase}
                  className={`rounded-lg border p-6 ${
                    phase.current
                      ? "border-verify-600 bg-verify-50/40"
                      : "border-ink-200 bg-paper"
                  }`}
                >
                  <h3
                    className={`text-sm font-semibold uppercase tracking-widest ${
                      phase.current ? "text-verify-700" : "text-ink-500"
                    }`}
                  >
                    {phase.phase}
                  </h3>
                  <ul className="mt-4 space-y-3">
                    {phase.items.map((item) => (
                      <li
                        key={item}
                        className="flex gap-3 text-sm leading-relaxed text-ink-700"
                      >
                        <span
                          aria-hidden="true"
                          className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${
                            phase.current ? "bg-verify-600" : "bg-ink-300"
                          }`}
                        />
                        {item}
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* CTA band */}
        <section aria-labelledby="cta-heading" className="border-t border-ink-100 bg-ink-950">
          <div className="mx-auto max-w-6xl px-6 py-20 text-center">
            <h2
              id="cta-heading"
              className="font-display mx-auto max-w-2xl text-3xl font-semibold tracking-tight text-paper sm:text-4xl"
            >
              Buying a business? Let the numbers argue first.
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-lg text-ink-300">
              We&apos;re running a small pilot with buyers of UK cafés and
              hospitality businesses. If that&apos;s you — or your client — get
              in touch.
            </p>
            <div className="mt-8">
              <a
                href={EARLY_ACCESS_HREF}
                className="inline-flex items-center justify-center rounded-md bg-paper px-6 py-3 text-sm font-semibold text-ink-950 transition-colors hover:bg-ink-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-verify-100"
              >
                Request early access
              </a>
            </div>
            <p className="mt-4 text-sm text-ink-500">{CONTACT_EMAIL}</p>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-ink-100">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-10 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Wordmark />
            <p className="mt-1 text-sm text-ink-500">
              Due diligence that reconciles, not summarises.
            </p>
          </div>
          <p className="max-w-md text-xs leading-relaxed text-ink-400">
            Diligence OS assists with financial due diligence. It is not
            accounting, tax or legal advice; findings should be reviewed with
            your professional advisers. © {new Date().getFullYear()} Diligence
            OS.
          </p>
        </div>
      </footer>
    </>
  );
}
