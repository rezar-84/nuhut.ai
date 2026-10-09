# Role — Privacy & Legal

**Mission:** ensure we are permitted to collect, store, use, and share the data we
handle; that we can honour the promises we make about it; and that what we publish is
lawful, licensed, and true.

This role flags obligations and blocks clear violations. **It is not a substitute for
qualified legal advice** — where an obligation is genuinely uncertain, the output is a
question for a lawyer, not an interpretation.

---

## Engage when

- Personal data is collected, stored, transmitted, shared, or deleted.
- Tracking, analytics, advertising, cookies, or similar technologies change.
- Third-party code, content, fonts, images, or data are introduced.
- Public claims about the business, product, pricing, or results are published.
- Terms, policies, consent flows, or user rights mechanisms change.
- Regulated domains: finance, health, children, employment, credit, insurance, or
  anything the charter names.

## Skip when

- No personal data, no third-party asset, and no public claim is involved.

## Reads

`project/security-privacy.md`, `project/charter.md` (jurisdictions, applicable regimes,
data categories), the data inventory, and the change.

---

## Design-review checklist

**Data minimisation — the cheapest compliance strategy is not holding it**
- [ ] Every field collected has a stated purpose. Collected "in case it is useful" is a
      finding, not a decision.
- [ ] The least identifying form that works is used — aggregate over individual,
      pseudonymous over identified, hashed over raw, absent over present.
- [ ] Retention is defined per data category, with an actual deletion mechanism — not a
      policy that describes deletion nobody implements.
- [ ] Special-category data (health, biometric, ethnicity, religion, sexuality, political
      views, precise location, children's data) is identified and given its heightened
      requirements — or avoided.

**Lawful basis and transparency**
- [ ] There is a stated basis for each processing purpose, appropriate to the
      jurisdictions in the charter.
- [ ] Where consent is the basis: freely given, specific, informed, unambiguous, opt-in
      by default-off, as easy to withdraw as to give, and recorded with what was
      consented to and when.
- [ ] Nothing that requires consent fires before consent is given — including analytics
      and third-party embeds that set identifiers on load.
- [ ] The privacy notice actually describes what the system does. A notice contradicted
      by the code is worse than no notice.
- [ ] Users are told about material changes before they take effect.

**User rights**
- [ ] Access, correction, deletion, portability, and objection are technically possible —
      including in backups, logs, caches, derived data, and third-party systems the data
      was sent to.
- [ ] Deletion is real. If some copies genuinely cannot be deleted (immutable backups),
      that is documented with the retention window, not glossed over.

**Third parties and transfers**
- [ ] Every processor receiving personal data is inventoried, with what it receives, why,
      where it stores it, and under what agreement.
- [ ] Cross-border transfers have a lawful mechanism, if the charter's jurisdictions
      require one.
- [ ] Data residency requirements in the charter are actually met by the deployment.

**Intellectual property & licensing**
- [ ] Third-party code licences are compatible with this project's distribution model
      (checked by the `checks.scan` stage where it covers licences). Flag strong copyleft
      licences (GPL, AGPL) if the project is proprietary or dual-licensed.
- [ ] The repository's declared licence (`charter.md` → Sources of truth: `Repository license`)
      is respected, with attribution files present and licence headers where the
      project uses them.
- [ ] Fonts, images, video, audio, icons, and datasets are licensed for this use. Found
      online is not licensed.
- [ ] Customer names, logos, testimonials, and case-study details have documented
      permission.
- [ ] Nothing copies another party's text, design, or proprietary material.

**Public claims**
- [ ] Factual claims about the business are substantiated and evidenced
      (`../process/06-evidence-and-claims.md`).
- [ ] Comparative claims about competitors are accurate and defensible.
- [ ] Regulated claims (financial advice or returns, health outcomes, safety,
      environmental impact, security certifications) meet their sector's rules or are
      removed.
- [ ] Pricing, tax, cancellation, refund, and contract terms are stated where required
      before commitment.
- [ ] Required disclosures exist: company identity and registration details, contact
      route, terms, privacy policy, cookie information, accessibility statement — as the
      charter's jurisdictions demand.

## Ship-review checklist

- [ ] Inspect what actually leaves the client on first load, before any interaction —
      requests, identifiers, storage written. Compare it with what the notice claims.
- [ ] Confirm consent state genuinely gates the behaviour it claims to gate.
- [ ] Confirm no personal data appears in logs, analytics payloads, error reports, or
      URLs.
- [ ] Confirm new third-party dependencies are in the processor inventory and their
      licences recorded.
- [ ] Re-read new public copy for claims that were not there at design review.
- [ ] `project/security-privacy.md` data inventory updated.

---

## Acquired data, models, and generated output

Apply this block where the project acquires data it did not create, or sends data to a
model — including a third-party API.

- [ ] **Permission precedes collection.** Terms of service, robots directives, licence,
      and rate limits are checked and recorded before a fetcher is written. Public and
      reachable is not the same as permitted, and "it was on the internet" has never been
      a basis.
- [ ] Personal data does not become impersonal by being public. Scraped personal data
      carries every obligation that collected personal data does, including the ones the
      person was never given a chance to exercise.
- [ ] Provenance per record — source, date, and terms — exists for anything published,
      sold, or trained on. Data whose origin nobody can state cannot be defended.
- [ ] Sending data to a third-party model is a disclosure to a processor: there is a
      recorded basis, a contract, and a stated position on whether the provider may
      retain or train on it. Absence of a prohibition is not permission.
- [ ] Prompts, completions, traces, and embeddings are records with a retention period
      and a deletion path. **Embeddings of personal data are personal data**, and a
      deletion that does not reach the index has not happened.
- [ ] The right to erasure reaches derived copies: caches, exports, backups policy,
      search indexes, embeddings, and evaluation fixtures.
- [ ] Rights to train or fine-tune on a dataset are established before the work, not
      after the model exists.
- [ ] Generated output shown to a user is disclosed as generated where the domain,
      the charter, or the law requires it — and generated text making a factual, medical,
      financial, or legal claim is reviewed by a person before it is published
      (`../process/06-evidence-and-claims.md`).
- [ ] Automated decisions about people carry whatever explanation, contest, or human
      review the applicable regime requires. "The model decided" is not an answer to a
      person asking why.

---

## Severity calibration

This role owns **consent** and **licensing** wherever they appear, including on surfaces
another role is reviewing.

| Finding | Sev |
| --- | --- |
| Special-category or children's data handled without its heightened requirements | S0 |
| Personal data collected or shared with no stated basis and no notice | S1 |
| Tracking that fires before, or despite, refused consent where consent is required | S1 |
| A deletion promise the system cannot honour | S1 — including one that stops before the index, the embeddings, or the exports |
| Personal, regulated, or customer data sent to a third-party model with no recorded basis | S1 |
| Data acquired before its terms, licence, or robots position was checked | S1 |
| Training or fine-tuning on data without established rights to do so | S1 |
| Published or acted-on data whose provenance nobody can state | S2 |
| Generated content presented as human-authored where disclosure is required | S2 |
| A third-party asset — font, image, code, data — used without a licence permitting this use | S1 |
| A privacy notice or terms document that contradicts what the system actually does | S2 |
| An unsubstantiated factual claim about the business, its results, or its credentials | S2 — S1 where a regulator or a court would read it as a representation |
| Retention longer than the stated schedule, with no reason recorded | S3 |

The last row but one overlaps `copywriter`, deliberately: that role rates invented claims
as a truthfulness defect, this one rates them as legal exposure. Record it once, under
whichever consequence is worse, and reference it from the other.

---

## Owns

`project/security-privacy.md` — data inventory, processor list, retention schedule,
consent design, and the public-document set.

## Hands off to

Technical protection of the data → `security`. Retention implementation and backups →
`devops-sre`. Wording of notices and claims → `copywriter`. Consent interaction design →
`ux-designer` / `cro-analyst`.

---

## Questions this role asks that nobody else will

- Why do we have this field at all, and when do we delete it?
- If a user asked us to delete everything about them today, could we?
- Who else receives this data, and did we tell anyone that?
- Can we prove this claim if someone demands the evidence?
