# Touchgrass: competition contract

Moved out of PLAN.md in round 4 (one file, one responsibility). Sections keep their
original 14.x numbers so earlier references still resolve. Verified against the live
rules (C) and challenge page (F) on 9 Oct 2026, 22:40 CEST: new project and repository
inside the window, one entry, AI use allowed, post-deadline commits noted in README,
template adds #devchallenge and #hf26challenge, teams up to four, categories claimed by
listing them in the post. Note: the window opened Mon 5 Oct 18:00 CEST, so Friday
planning is already inside it.

### 14.1 Correct contest, sources and precedence

Target: **Hacktoberfest Open-Source AI Challenge: Week 1 — Touch Grass**, sponsored by
Major League Hacking PBC Inc. The earlier launch-weekend **Build for a Friend** contest
is closed and is not this entry. Use the Week 1 submission template and dashboard tile.

Sources reviewed on **9 October 2026**, using the supplied full rules/FAQ and live pages:

- [C — Week 1 contest announcement and specific rules](https://dev.to/page/hacktoberfest-week1-2026-10-05-contest-rules)
- [G — General Contest Official Rules, updated 25 February 2026](https://dev.to/page/official-hackathon-rules)
- [F — Week 1 challenge page, FAQ, categories and Submission Template](https://dev.to/challenges/hacktoberfest-week1-2026-10-05)
- [T — DEV Terms of Use, incorporated by the general rules](https://dev.to/terms)

This is an operational summary, not a replacement for the official terms. G controls
conflicts with C; G also controls conflicts with DEV terms for the contest. Recheck
the live sources before publication because organisers may change or suspend the contest.
Record the review date, source links, material changes and unresolved questions in
`docs/evidence/rules.md`. DEV terms still need the entrant's review; do not mark that
review complete merely because this summary links to them.

### 14.2 Entry window and originality — mandatory

| Event | Official PDT time | UTC | Europe/Stockholm (CEST) |
|---|---|---|---|
| Opens | 5 Oct 2026, 09:00 | 5 Oct, 16:00 | **Mon 5 Oct, 18:00** |
| Closes | 11 Oct 2026, 23:59 | 12 Oct, 06:59 | **Mon 12 Oct, 08:59** |
| Our submission target | — | 12 Oct, 06:30 | **Mon 12 Oct, 08:30** |

- The project **and repository** must start and be completed within this window. An
  existing application, an old repository relabelled as new, or a PR to an existing
  project is not a valid entry. Preserve truthful repository creation and commit dates.
- Friday 9 October is planning; implementation is planned for Saturday 10 October after
  Mats says **kör**. No fabricated/backdated evidence or claims about work not performed.
- Existing open-source components may be reused with sufficient original work and
  proper attribution. Credit non-trivial borrowed code, assets and adaptations in the
  repository **and submission**, and meet their licence obligations. Copying substantial
  private project code into the entry is not authorised by this plan.
- Claude Code and Codex are pre-existing AI development tools, not part of the submitted
  project. Using them to build Wiggle Outside is consistent with the explicit permission
  to use AI tools. Disclose the distinction and any reused code (TC-003).
- One entry per participant/team. If multiple entries are submitted, C says only the
  first is judged. Do not publish a placeholder contest entry or duplicate submissions.
- Later work must not be represented as finished by the deadline. F requires all
  post-deadline commits to be identified in the README. Record a submission commit/tag
  and keep the demonstrated version reproducible. The tag is our evidence practice.
- Missing this deadline does not automatically qualify this project for Week 2: each
  challenge has its own theme and new-project window. Continuing as a portfolio project
  is separate from entering a later contest. [C, F]

### 14.3 Entry and eligibility checklist — mandatory

Each item begins **PENDING** until evidence or the entrant's confirmation exists.

| ID | Requirement | Evidence / owner |
|---|---|---|
| C01 | Entrant meets age/majority and contractual-capacity requirements; active DEV account in good standing, active email and Internet access throughout the entry period | Mats confirms privately; no identity documents in the repo |
| C02 | No excluded residence, sanctions/restricted-party or sponsor-employment/household conflict; participation lawful and consistent with any employer policy | Mats reviews G and confirms eligibility; not automatically certified by this plan |
| C03 | New project and repository created and completed during the window | Repository creation record, first commit and submission commit |
| C04 | Open-source AI is central to the delivered project | Real Gemma execution demonstrated; model identity, prompts and evaluated output |
| C05 | Touch Grass theme: useful outdoor experience with little screen time | Working quiz-to-outing flow and explanation; actual outdoor trial is encouraged, not a formal eligibility prerequisite |
| C06 | Published DEV post using the current Week 1 template and its tags | Final post URL; `#devchallenge` and `#hf26challenge`; no launch-weekend template |
| C07 | English write-up for prize eligibility | Human-reviewed English post; F says non-English entries can earn completion badges but not prizes |
| C08 | Demonstration and project code-repository link | Working video or deployed demo plus accessible repository; check links while signed out |
| C09 | Explain why open innovation matters to this project | Evidence-based discussion of open-weight model use (Gemma, hosted; swappable for a local run), inspectability, model substitution and data control |
| C10 | Original, authorised, lawful material respecting IP, privacy and publicity rights; no prohibited content | Attribution/licence inventory and review of text, code, assets and recordings |
| C11 | One submission; team rules satisfied if relevant | Solo entry unless declared otherwise; up to four people, all DEV handles listed, one team post, all members eligible and agreeing to the rules |
| C12 | Entry published and received before closing | Check published post and available challenge confirmation before our 08:30 target; save URL/time and receipt evidence |

G's current excluded-residence list: Afghanistan, Belarus, Central African Republic,
Cuba, Equatorial Guinea, Iran, Iraq, Kosovo, Libya, Myanmar (Burma), North Korea, Russia,
South Sudan, Sudan, Syria, Tanzania, Venezuela and Yemen. Additional export-control and
restricted-party exclusions apply. France and Sweden are absent from that named list;
that alone does not establish every eligibility condition. G also excludes specified
sponsor-related workers, their immediate families and household members.

G prohibits obscene, lewd, profane, pornographic, disparaging or indecent entries and
descriptions of illegal, inappropriate or dangerous behaviour. Playful copy and outdoor
activities must remain consistent with those requirements. Plagiarism or an invalid
entry can lead to disqualification; F warns egregious plagiarism can lead to DEV suspension.

The organiser's clock is authoritative. A local screenshot or attempted submission is
not proof of receipt. [C, G, F]

### 14.4 Model, build tooling and claims

- **Application:** Gemma ranks eligible place/activity pairs and chooses reviewed story
  hooks and reason codes; it writes no displayed text. A fallback-only application is not our
  planned AI-centred entry. Show both genuine model use and honestly labelled fallback.
- **Development (TC-003):** built with **Claude Code as the integration owner** (it writes
  and merges the work and runs the gates) and **Codex as reviewer** of every integrated
  change, with **Mats approving product decisions, protected changes and the release** and
  making every commit, push and publication himself. Say exactly that, and no more: record
  the tool and model versions actually used, Mats's decisions, the tests and the
  corrections. Do not imply autonomous success where a person intervened, and do not claim
  an orchestration layer that this build does not have.
- **Evidence sharing:** DevRelay/agent-session sharing is optional. Publish only reviewed,
  redacted extracts. Keep secrets, other repositories, private family details and precise
  home coordinates out of public logs, screenshots and video.
- **Privacy:** demonstrate the real data flow. Typed town/area text is sent to Nominatim;
  provider requests disclose network metadata; in the hosted product the model prompt,
  including any interest text, goes through OpenRouter to the model provider
  (ARCHITECTURE §2 recipient table). Nothing is processed locally on the visitor's
  machine. Section 5's broad location statement is narrowed accordingly.
- **Offline:** distinguish an already loaded/saved card from fresh
  geocoding, places and weather requests. Verify any claimed offline behaviour.
- **Cost:** remove the absolute 'zero running cost' promise. Describe the hosted costs as
  estimates (DEPLOYMENT §1.5) with their remaining exposure, and the usage limits. Report actual costs if measured.
- **Safety/accessibility/security:** distinguish implemented controls, completed tests,
  targets, limitations and remaining risks. Never claim flawless safety, unbreakable
  security or WCAG AAA conformance without the required evaluation. [C, F; project policy]

### 14.5 Partner categories and judging

Target **Best Use of Gemma** if the shipped application meaningfully uses Gemma. The
overall prize does not require partner technology. C describes automatic consideration
for technologies meaningfully used; F additionally asks entrants to list their categories
in the post. Satisfy both: name each claimed category and show the actual integration.
Do not add services merely to accumulate category names. A project may enter multiple
supported categories but win only one prize.

| Category group | Categories open in Week 1 |
|---|---|
| Featured — $200 each | Render, TabPFN, Tinker, Arduino, DigitalOcean, Gemma |
| Partner — $100 each | Backboard, ElevenLabs, Entire, GitHub Copilot, Mastra, MongoDB Atlas, Sentry Agent Tracing, SerpApi, Temporal, Tiger Data |
| Overall — $250 | DEV++ membership and exclusive DEV badge |

F lists 17 winners in total (one overall and 16 categories), winner badges and a badge
for valid completion. Category examples are not interchangeable: local tooling use alone
is not Render use; ordinary local traces alone are not Sentry use; pandas/Polars/DuckDB
analysis alone is not TabPFN use. Verify the category-specific description before claiming it.

Writing carries the greatest judging weight, followed by assessment of theme relevance,
creativity, technical execution and meaningful partner use where applicable; no numeric
weights are stated. In a scoring tie, the rules use positive DEV-post reactions. Share
the work honestly; do not manufacture reactions or manipulate entry/judging processes.

Post outline: real problem → short demonstration → how it gets someone outside → why
open AI matters → design and build decisions → building with Claude Code and Codex, and
human review →
tests/measurements and limitations → actual outdoor feedback → credits and categories.
Draft with the humanise-text skill if useful; the final voice, facts and edits are Mats's.
Start collecting this evidence Saturday rather than leaving the story until release. [C, F]

### 14.6 Rights, general terms and prize follow-up

Mats retains ownership, but submission grants the organiser a worldwide, non-exclusive,
royalty-free, sublicensable, perpetual and irrevocable licence to use/display/distribute
entry materials for the contest and promotion; modification is limited to transmission
purposes. G also provides promotional use of entrant name, likeness, biography and true
attributed statements, except where prohibited. Submit only materials authorised for
that use. The organiser does not promise protection against third-party reuse or return
of materials, and may receive similar ideas from others.

G includes entrant responsibility for preparation costs and prize taxes, liability
limitations (including a stated $25 aggregate cap, subject to applicable restrictions),
release/indemnity obligations, California law and specified California courts, and
personal-information use for participation and as described in the rules. These terms
require the entrant's own review; this plan does not accept them on Mats's behalf.
The organiser may modify, suspend or terminate the contest and disqualify entries under
the rules; judging decisions are final.

Winners are expected to be announced in the week of 12 October. Watch the DEV account's
email: notification is within ten business days of selection, and requested eligibility,
release or tax paperwork may be due within seven business days of the first attempted
notification. Missing deadlines, ineligibility or incomplete documents can forfeit a
prize. Teams arrange their own prize split. G estimates delivery two to four weeks after
acceptance of completed paperwork. Never upload those personal documents to the code
repository; use the organiser's verified process. [G, F]

### 14.7 Evidence and publication gate

Planned files (create during the authorised build; none is assumed to exist yet):

| File | Contents |
|---|---|
| `docs/evidence/rules.md` | Source/date register, C01–C12 status, entrant confirmations without sensitive details, rule changes and unresolved questions |
| `docs/evidence/build-process.md` | Tool and model versions, truthful build history, who did what (Claude Code integrates, Codex reviews, Mats approves and commits), review and redaction record |
| `docs/evidence/submission.md` | Exact submitted commit/tag, demo/repo/post URLs, checks, timestamp and confirmation |
| `docs/evidence/attribution.md` | Code, data, model, font and asset provenance, licences, notices and reuse |
| `docs/evidence/wcag.md` | Criterion-level applicability, automated/manual evidence and unresolved failures |
| `docs/post/submission.md` | English draft following the official Week 1 template |

Before publication, Mats and the reviewer check:

- [ ] C01–C12 all satisfied with evidence; questions resolved rather than marked passed by assumption.
- [ ] Live official pages and DEV terms reviewed; correct Week 1 template and tags used.
- [ ] Real Gemma demonstration works; fallback is labelled; claims match the submitted version.
- [ ] Clean ZIP/extraction/build checks pass; repository, demo and post links are accessible.
- [ ] Credits cover reused code plus OSM, Open-Meteo, font, model and any other assets/services, with exact applicable licences verified.
- [ ] Security and accessibility evidence matches the claims; required project controls are not silently waived for the deadline.
- [ ] English post is complete and human-reviewed; category claims are supported.
- [ ] Public materials contain no secrets, unrelated private work or unnecessary personal data.
- [ ] Submission commit/tag and demo are recorded; subsequent changes will be documented.
- [ ] Mats publishes the single final entry by the 08:30 target and verifies available receipt/visibility evidence.

Actual outdoor use, video captions/transcript and a reproducible tagged release are our
planned evidence practices. Security, criterion-level AAA ambition and playful design
are project requirements, not invented contest eligibility rules. No entry is described
as fully compliant until the required checks are actually completed.
