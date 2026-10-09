# ANTI-VIBECODE — Web & Mobile AI Development Standard

Version: 1.0
Purpose: Use this document as a persistent instruction set for an AI coding agent when creating a new application from scratch or improving an existing one.
Scope: Web apps, mobile apps, responsive PWAs, dashboards, SaaS products, e-commerce, internal tools and API-backed applications.

## 0. Core objective

Build software that looks and behaves like it was designed, engineered, tested and maintained by a competent product/engineering team — not like a generated demo.

The goal is NOT to avoid using AI. The goal is to prevent AI-generated shortcuts, generic visual patterns, fake completeness, brittle architecture and unverified assumptions.

Prioritize, in this order:

1. Correctness and real functionality.
2. Clear information architecture and user flows.
3. Consistent visual system and intentional hierarchy.
4. Accessibility and responsive behavior.
5. Performance and reliability.
6. SEO/discoverability where applicable.
7. Security and privacy.
8. Maintainability and testability.
9. Only then, decorative polish.

Never add visual complexity merely to make a page look more "designed".

---

# 1. AI-SPECIFIC ANTI-PATTERNS

## 1.1 Do not generate a template-looking interface
Avoid default combinations that frequently appear in AI-generated products:

- Purple/blue neon gradients used everywhere.
- Dark mode by default when the product has no reason to require it.
- Glow, blur, glassmorphism, shadows or gradients used as decoration rather than communication.
- Excessive rounded cards containing every piece of information.
- Excessive badges, pills, chips and status dots.
- Decorative side tabs attached to every section.
- Emoji used as the primary icon system for navigation or actions.
- Random line icons from multiple visual families.
- Giant hero sections that consume the viewport without helping the task.
- Huge text combined with tiny supporting text purely to imitate trendy landing pages.
- Excessive animations, floating particles, cursor effects or background effects.
- Identical card grids repeated down the whole page.
- Fake dashboards made of unrelated KPI cards.
- Decorative charts with no decision-making purpose.
- Buttons that all look equally important.
- Every section separated by a border, card, color block or shadow.

A design may use any of these techniques when the product context justifies them. The rule is intentionality, not prohibition.

## 1.2 Do not fabricate functionality
Never generate controls that look functional but do nothing.

Never create fake:
- Search results.
- Pagination.
- Filters.
- Authentication.
- Notifications.
- Charts with invented data.
- "Live" status indicators without a real data source.
- Save buttons that only change local UI state when persistence is expected.
- API integrations represented by hardcoded objects.
- Loading states that never correspond to an actual asynchronous state.
- Success messages for operations that were not confirmed by the backend.

If functionality is intentionally mocked, label it clearly in code and UI where appropriate.

## 1.3 Do not invent product requirements
Do not silently invent:
- Business rules.
- Pricing.
- Permissions.
- Tax calculations.
- Financial/accounting logic.
- Security assumptions.
- API contracts.
- User roles.
- Data retention rules.
- Legal claims.

When requirements are missing, use the smallest reasonable assumption and isolate it so it can be changed later. Do not spread invented assumptions through the application.

## 1.4 Do not over-engineer
Avoid:
- Premature abstraction.
- Generic components that are harder to understand than the original implementation.
- Excessive hooks for trivial behavior.
- Global state when local state is sufficient.
- A design system with hundreds of tokens for a small product.
- Many libraries for functionality available natively.
- Custom frameworks inside a normal application.
- Wrapper components with no semantic or behavioral value.

Prefer simple code that explains itself.

## 1.5 Do not under-engineer
Avoid:
- One giant component containing the entire application.
- One giant CSS file containing unrelated rules.
- One API utility containing every endpoint with inconsistent conventions.
- Repeating business logic in multiple components.
- Hardcoded values scattered across the codebase.
- Copy/paste implementations of the same interaction.
- Magic strings and magic numbers without a domain reason.
- Catch-all error suppression.

---

# 2. VISUAL DESIGN STANDARD

## 2.1 Establish a design system before styling pages
Define a small, coherent system for:
- Primary and secondary colors.
- Background/surface colors.
- Text hierarchy.
- Border treatment.
- Radius scale.
- Shadow scale.
- Spacing scale.
- Typography.
- Iconography.
- Interactive states.
- Form states.
- Motion rules.

Use a restrained number of values. Do not invent slightly different colors, radii or spacing values for every component.

## 2.2 Create hierarchy
Every screen should make it obvious:
- What this page is.
- What the primary task is.
- What is secondary.
- What is actionable.
- What is informational.
- What is currently selected or active.

Do not make every element visually loud.

## 2.3 Use components according to meaning, not habit
Do not turn every block into a card.

Use:
- Tables for comparable structured data.
- Lists for repeated items.
- Forms for input workflows.
- Dialogs for focused decisions.
- Sections for conceptual grouping.
- Cards when grouping truly benefits scanning or interaction.
- Tabs when alternatives share the same context and switching is useful.
- Accordions when progressive disclosure is useful.
- Navigation elements for navigation — not decorative side labels.

## 2.4 Avoid decorative status indicators
A colored dot, badge or label must communicate a real state with a defined meaning.

Every status should define:
- Source of truth.
- Allowed values.
- Meaning of each value.
- Visual representation.
- Text alternative where necessary.
- What happens when the state is unknown.

Never display a green dot simply because it looks professional.

## 2.5 Iconography
Use a consistent icon library or a coherent custom icon set.

Do not use emoji as the primary icon language for professional interfaces.

A meaningful icon must have:
- A clear semantic purpose.
- Accessible labeling when it is the only control label.
- Consistent size and optical weight.
- Consistent alignment.

Do not use icons to fill empty space.

## 2.6 Motion
Animations must communicate one of:
- State change.
- Spatial relationship.
- Loading/progress.
- Confirmation.
- Focus or attention.

Avoid perpetual motion and decorative animation. Respect reduced-motion preferences where applicable.

---

# 3. LAYOUT AND RESPONSIVENESS

The application must be designed for real viewport sizes rather than one desktop screenshot.

Validate at minimum:
- Small mobile.
- Large mobile.
- Tablet.
- Laptop.
- Large desktop.

Do not simply shrink desktop layouts.

Check:
- Navigation behavior.
- Text wrapping.
- Form usability.
- Tables and horizontal overflow.
- Modal/dialog behavior.
- Sticky elements.
- Fixed headers/footers.
- Touch targets.
- Safe-area considerations on mobile.
- Orientation changes where relevant.

Never rely on accidental browser overflow.

Do not use arbitrary breakpoint proliferation. Breakpoints should correspond to actual layout changes.

---

# 4. SEMANTIC HTML AND ACCESSIBILITY

Use semantic HTML before adding ARIA.

Prefer:
- `<button>` for actions.
- `<a>` for navigation.
- `<nav>` for navigation.
- `<main>` for primary content.
- `<header>`, `<footer>`, `<section>`, `<article>`, `<aside>` where semantically appropriate.
- Real headings in logical order.
- `<label>` associated with form controls.
- Native form validation where useful.

Do not use `<div onClick>` as a replacement for a button.

Do not use ARIA to repair a fundamentally incorrect element when a semantic HTML element exists.

## Accessibility minimum bar

Verify:
- Keyboard navigation.
- Visible focus.
- Logical focus order.
- Screen-reader names for interactive controls.
- Form labels and error association.
- Sufficient color contrast.
- Information is not communicated by color alone.
- Images have appropriate alternative text.
- Decorative images are not unnecessarily announced.
- Dialogs have correct focus handling.
- Menus/tabs/disclosures expose their state correctly.
- Text remains usable when enlarged/reflowed.
- Motion can be reduced where appropriate.

WCAG 2.2 is the baseline reference for accessibility requirements. W3C specifically emphasizes semantic headings, sufficient contrast, labels, identifiable interactive elements, and not relying on color alone. 

---

# 5. CONTENT QUALITY

Never use generic AI copy when the product already has real domain language.

Avoid:
- "Welcome to the future of..."
- "Revolutionize your workflow..."
- "Powerful, intuitive and seamless..."
- Empty marketing claims.
- Repeated adjectives.
- Placeholder lorem ipsum in production.
- Repeated section descriptions that say the same thing.

Copy should explain what the product actually does.

Use domain-specific labels, examples, units, terminology and error messages.

Do not hide missing content with decorative filler.

---

# 6. ROUTING AND PAGE STRUCTURE

Every route should have a deliberate purpose.

For web applications, verify:
- Real route definitions.
- Correct navigation links.
- Deep-link support.
- Refreshing a nested route works in production.
- Back/forward navigation behaves correctly.
- Active navigation state is correct.
- Unknown routes produce a useful 404 page.
- Protected routes enforce access correctly.
- Redirects are intentional.

Do not use the same page title or metadata for unrelated routes.

A Vercel-generated `*.vercel.app` URL is not itself a technical defect; it is typically a deployment/preview URL. For a production site, a custom domain is normally the appropriate canonical public URL when available. citeturn137865search16

---

# 7. SEO AND DISCOVERABILITY — WEB

Apply this section only to pages intended to be crawlable/indexable.

## 7.1 Document metadata
Each indexable page should have metadata appropriate to its content:
- Unique `<title>`.
- Useful meta description.
- Canonical URL when canonicalization matters.
- Open Graph metadata for link previews.
- Twitter/X card metadata where relevant.
- Favicon.
- Correct document language.
- Charset and viewport metadata.

Google recommends descriptive, concise and distinct titles for pages and notes that repeated boilerplate titles can be problematic. Meta descriptions may be used to form search snippets. 

## 7.2 Headings
Do not generate headings based only on font size.

Create a meaningful page hierarchy. Usually the main page topic should have a clear primary heading, followed by logically nested sections.

Do not interpret "multiple H1s are always forbidden" as a rule. The actual requirement is clear semantic structure. W3C recommends logical heading structure, and Google notes that multiple equally prominent headings can make the main title ambiguous. 

## 7.3 Canonicalization
Use canonical URLs intentionally.

Avoid:
- Canonicals pointing to unrelated pages.
- Self-canonicalization mismatches.
- Canonicalizing all pages to the home page.
- Duplicate URLs caused by query parameters without a strategy.
- Mixed HTTP/HTTPS canonicals.
- Mixed www/non-www canonicals.

Google documents incorrect canonical elements and server configuration as common canonicalization problems. 

## 7.4 Structured data
Use Schema.org/JSON-LD only where the content genuinely matches a supported schema or a meaningful semantic representation.

Do not add fake structured data just to "make Google understand the site".

Structured data must represent visible, relevant page content and must not be misleading. JSON-LD is the recommended format by Google among the supported formats. 

Examples to consider when applicable:
- Organization.
- WebSite.
- Product.
- Article.
- BreadcrumbList.
- LocalBusiness.
- FAQ only when appropriate to the current search guidelines and actual page content.

## 7.5 Sitemap
For public indexable sites, provide an accurate XML sitemap when appropriate.

Do not include:
- Redirect URLs.
- Error URLs.
- Private URLs.
- Duplicate URLs.
- URLs blocked for a conflicting reason.

A sitemap is a discovery aid, not a guarantee of indexing. Google supports XML sitemaps and can also discover a sitemap through `robots.txt`. 

## 7.6 robots.txt
Do not blindly copy restrictive robots.txt templates.

Before changing it, define:
- Which pages search engines should crawl.
- Which pages should not be crawled.
- Which resources must remain accessible to crawlers.
- Whether AI/agent access is intentionally restricted.
- Where the sitemap lives.

Do not accidentally block the entire public website.

Do not claim that `robots.txt` is an AI privacy/security mechanism. It is a crawler access convention and must be treated as a policy signal, not a secret barrier.

Google's `Google-Extended` token is a separate robots.txt control for certain Google AI usage; it does not affect inclusion in Google Search. 

## 7.7 Language
Set a correct `lang` on the root HTML element and mark meaningful language changes in localized sections when necessary.

The language should reflect the actual primary content, not the developer's preferred language.

MDN notes that a valid `lang` is recommended and is especially important for accessibility and screen-reader pronunciation. 

## 7.8 Favicon
Use a real favicon appropriate to the brand. Keep its URL stable.

Google documents `/icon` links and recommends a representative, square favicon, preferably at least 48×48px for good display quality. 

## 7.9 llms.txt
Treat `/llms.txt` as an optional, emerging convention rather than a mandatory SEO requirement.

When useful, provide:
- A concise site/project summary.
- Important terminology.
- Links to authoritative pages/docs.
- Clear sections for relevant resources.
- Human-readable Markdown.

Do not write a fake llms.txt full of generic marketing language.

The current llms.txt proposal describes it as an LLM-friendly site overview and recommends Markdown links plus optional relations to Markdown versions of pages. It is a community proposal, not a universal web standard. citeturn137865search0turn137865search1

---

# 8. RENDERING AND JAVASCRIPT SEO

Do not assume that a React SPA is automatically SEO-friendly just because Google can execute JavaScript.

For public content, choose the rendering strategy deliberately:
- SSR.
- SSG/static generation.
- Pre-rendering.
- CSR when its limitations are acceptable.

Ensure important content exists in the rendered output available to relevant crawlers.

Google notes that JavaScript has limitations in search and recommends SSR, static rendering or hydration rather than dynamic rendering as a long-term workaround. 

A blank or minimal `view-source` result is not, by itself, proof of a broken site. The correct test is whether the initial HTML and rendered page contain the content required for the product and its discovery goals.

---

# 9. PERFORMANCE

Treat performance as an engineering requirement, not a final polish step.

## Avoid
- Giant initial JavaScript bundles.
- Importing an entire icon library when only a few icons are used.
- Loading every route/component at startup.
- Unnecessary large dependencies.
- Duplicate libraries solving the same problem.
- Massive JSON embedded in the client.
- Huge images served at display size multiples larger than necessary.
- Unoptimized fonts.
- Blocking third-party scripts.
- Expensive effects applied globally.
- Continuous animations consuming CPU.
- Recomputing expensive work on every render.
- Fetching the same data repeatedly without a reason.

## Prefer
- Route/component code splitting.
- Lazy loading for non-critical routes/components.
- Tree shaking.
- Optimized image formats and dimensions.
- Caching appropriate data.
- Correct image sizing to prevent layout movement.
- Minimal critical JavaScript.
- Measurement with browser performance tools and Core Web Vitals.

React supports lazy component loading, and modern performance guidance emphasizes reducing initial JavaScript and avoiding long main-thread tasks. Vite production builds support code splitting and configurable source-map output. 

For Core Web Vitals, explicitly monitor at least LCP, CLS and INP where applicable. Web.dev recommends aiming for an LCP of 2.5 seconds or less at the 75th percentile; unexpected layout movement is captured by CLS. 

---

# 10. SOURCE MAPS AND PRODUCTION ARTIFACTS

Do not expose production source maps by default unless there is a deliberate operational reason.

Check:
- `*.map` files.
- Inline source maps.
- Source-map comments.
- Debug bundles.
- Unminified development assets.
- Test artifacts.
- Environment files.
- Build logs accidentally copied into public assets.

Vite's production source-map generation is disabled by default and can be enabled explicitly, including `true`, `inline` and `hidden` modes. Decide deliberately whether public source maps are appropriate. 

Never place secrets in client-side source code or client-exposed environment variables.

For Vite, variables prefixed with `VITE_` are exposed in client-side bundled code. They must therefore never contain secrets. 

---

# 11. SECURITY

Never treat the frontend as a trusted security boundary.

Validate and authorize on the server for protected operations.

Check for:
- Secrets in source.
- Secrets in `VITE_*` variables.
- API keys embedded in bundles.
- Insecure direct object references.
- Missing authorization checks.
- Unsafe HTML injection.
- Unsafe URL handling.
- Weak input validation.
- Missing rate limiting for sensitive endpoints.
- Overly permissive CORS.
- Missing or weak security headers where applicable.
- Dependency vulnerabilities.
- Unsafe third-party scripts.
- Sensitive information in logs.
- Tokens stored in inappropriate client storage.

Never hide a secret by obfuscating it. If the browser can read it, it is not secret.

---

# 12. DATA AND API ARCHITECTURE

Do not let UI components become the application's business-logic layer.

Separate, where justified:
- UI/presentation.
- Domain/business logic.
- API/data access.
- Validation.
- State management.
- Persistence.

Define consistent conventions for:
- Request/response types.
- Error shapes.
- Loading states.
- Pagination.
- Filtering.
- Sorting.
- Retries.
- Caching.
- Authentication.

Never silently convert API errors into empty arrays.

Never treat a failed request as "no data" unless the product explicitly defines that behavior.

---

# 13. STATE DESIGN

Every meaningful asynchronous feature should consider at least:

1. Initial/loading state.
2. Success state.
3. Empty state.
4. Recoverable error state.
5. Permission/unauthorized state where applicable.
6. Offline/unavailable state where relevant.
7. Partial data state where relevant.

Do not use a generic spinner for every state.

Empty is not the same as error.

Loading is not the same as disabled.

Unknown is not the same as healthy.

---

# 14. ERROR HANDLING AND RELIABILITY

No console errors should remain in normal production flows.

Warnings must also be investigated when they indicate real defects.

Use error boundaries or equivalent recovery strategies at meaningful UI boundaries where the framework supports them. React documents Error Boundaries as the mechanism for recovering from rendering errors and displaying fallback UI. 

Never:
- Swallow exceptions silently.
- Catch everything and return nothing.
- Log sensitive data.
- Show raw stack traces to end users.
- Claim success when the operation failed.
- Leave broken buttons after errors.

The UI should provide a useful recovery path where possible.

---

# 15. FORMS

Every form should define:
- Labels.
- Required/optional behavior.
- Validation rules.
- Field-level errors.
- Submit/loading state.
- Disabled state.
- Success feedback.
- Failure feedback.
- Preservation of user input when safe.
- Keyboard behavior on mobile where relevant.

Avoid vague messages such as "Invalid input" when a specific explanation is possible.

Never validate only in the UI when the server accepts the data.

---

# 16. TABLES, LISTS, SEARCH AND FILTERS

Do not replace structured data with visually attractive but semantically weak card layouts.

For real datasets, consider:
- Pagination.
- Sorting.
- Filtering.
- Empty states.
- Loading placeholders.
- Error states.
- Virtualization for very large lists.
- Accessible table semantics.
- Stable identifiers.

Pagination controls must actually change the dataset/page and preserve the relevant state.

Filters must actually affect the query or dataset.

Search fields must define whether search is client-side, server-side or hybrid.

---

# 17. STATE MANAGEMENT

Choose state scope intentionally:
- Component state for local UI behavior.
- Context for genuinely shared concerns.
- Server-state libraries where server caching/synchronization is important.
- Global stores only for truly global client state.

Do not put every value into one global store.

Avoid effects that exist only to synchronize derived values that could be calculated directly.

Avoid using `useEffect` as the default answer to every data or state problem.

---

# 18. REACT-SPECIFIC QUALITY RULES

For React applications:

- Prefer function components.
- Keep components focused on a coherent responsibility.
- Avoid giant components.
- Avoid unnecessary prop drilling by restructuring or using appropriate shared state.
- Use stable keys for lists based on identity, not array position when identity can change.
- Do not use `useMemo`/`useCallback` everywhere without a reason.
- Keep side effects explicit.
- Keep reusable logic in hooks or utilities only when reuse/semantics justify it.
- Lazy-load routes or heavy components when beneficial.
- Add meaningful error boundaries around product-level regions where failure isolation matters.

React officially recommends function components for new code and provides `lazy` for deferring component code until needed. citeturn754025search0turn754025search1

---

# 19. VITE-SPECIFIC QUALITY RULES

If using Vite:

- Do not place secrets in `VITE_*` variables.
- Confirm production build output.
- Review source-map configuration.
- Review chunk sizes.
- Use code splitting for appropriate routes/heavy features.
- Verify SPA fallback behavior on the deployed host.
- Remove development-only logging where appropriate.
- Avoid unnecessary global polyfills.
- Verify asset paths under the configured `base` path.

Do not treat "Vite + React" as evidence of poor quality. The stack is neutral; implementation quality is what matters. Vite documents production build behavior and source-map configuration explicitly. citeturn137865search14turn137865search2

---

# 20. FILE AND CODE ORGANIZATION

The folder structure should communicate the architecture.

Avoid both extremes:

Too flat:
- `App.jsx` containing half the project.
- `utils.js` containing everything.
- `api.js` containing every endpoint.
- `styles.css` containing every screen.

Too fragmented:
- One file per tiny wrapper.
- One folder per icon.
- One hook for trivial state that is never reused.
- Abstractions with no semantic reason.

Use domain/features when the product benefits from them.

Names should be predictable and consistent.

Avoid files such as:
- `final.js`
- `newComponent.jsx`
- `test2.js`
- `helperFinal.js`
- `utilsNew.js`
- `temporary.js`

---

# 21. DEPENDENCIES

Before adding a dependency, ask:

- Is the problem substantial enough to justify a dependency?
- Is there already a dependency in the project that solves it?
- Is the dependency maintained?
- Does it increase the initial bundle significantly?
- Does it overlap with another library?
- Is it compatible with the existing stack?

Do not install libraries simply because an AI model knows them well.

Prefer the smallest dependency surface that satisfies real requirements.

---

# 22. TESTING

Do not consider an application complete because it builds.

At minimum, verify:
- Build.
- Lint/type checking where configured.
- Primary user flows.
- Critical API paths.
- Error paths.
- Responsive behavior.
- Accessibility basics.
- Routing/deep links.
- Authentication/authorization where applicable.

Use the appropriate test level:
- Unit tests for isolated logic.
- Integration tests for component/service interactions.
- E2E tests for critical user journeys.

Do not create meaningless tests that only confirm a component renders.

Do not inflate test count to appear complete.

---

# 23. OBSERVABILITY

For production applications, decide how failures are observed.

Consider:
- Error tracking.
- Structured logs.
- Request IDs/correlation IDs where useful.
- Performance monitoring.
- Key business events.
- Health checks for backend services.

Never log:
- Passwords.
- Access tokens.
- Secret keys.
- Sensitive personal data unless specifically required and protected.

---

# 24. MOBILE-SPECIFIC QUALITY RULES

For React Native/Expo or other mobile stacks:

- Do not make a web page merely "fit" inside a mobile shell.
- Respect mobile navigation conventions.
- Handle back navigation correctly.
- Account for keyboard appearance and input focus.
- Handle safe areas.
- Define loading/error/offline states.
- Handle permissions deliberately.
- Test on realistic device sizes.
- Consider poor network conditions.
- Avoid unnecessary re-renders on long lists.
- Use platform-specific behavior when the UX genuinely differs.
- Do not request device permissions before explaining why they are needed.

---

# 25. ACCESSIBILITY OF ICON-ONLY CONTROLS

Every icon-only button must have an accessible name.

Do not assume the icon itself is enough.

For tooltips, do not rely solely on the HTML `title` attribute for important instructions; MDN documents significant accessibility limitations with `title` for touch, keyboard and assistive-technology users. 

---

# 26. INTERNATIONALIZATION

Do not hardcode assumptions about:
- Currency symbols.
- Decimal separators.
- Date formats.
- Time zones.
- Pluralization.
- Text direction.
- Language.
- Telephone formats.

Use locale-aware formatting when the product operates across regions.

Keep translatable strings centralized enough to be maintainable when localization is expected.

---

# 27. SEO/UX DETAILS AI OFTEN FORGETS

Check:
- Descriptive link text.
- Meaningful button labels.
- Breadcrumbs where useful.
- Search engine accessible internal links.
- Redirect handling.
- No accidental `noindex` on public pages.
- No accidental auth wall on public content.
- Correct status codes from the server.
- Stable URLs.
- Proper trailing-slash policy.
- Social preview metadata.
- Correct image dimensions and alt text.
- Favicon and app icons where appropriate.
- `lang`.
- Sitemap.
- Robots policy.
- Canonicals.
- Structured data where appropriate.

---

# 28. COMMON "VIBECODE" SMELLS TO FLAG DURING AUDITS

Flag these as symptoms requiring investigation, not automatic proof of bad code:

### Visual
- Everything is a card.
- Everything is rounded.
- Everything glows.
- Everything is purple/blue.
- Every section has a gradient.
- Every block has a badge.
- Every empty area has an icon.
- Every metric has a status dot.
- Every heading is huge.
- Every page has the same hero.

### Content
- Generic marketing copy.
- Repeated copy.
- Placeholder text.
- Empty states that say nothing useful.
- Tooltips explaining obvious UI.

### Technical
- Giant component files.
- Giant initial bundle.
- Many unnecessary dependencies.
- Exposed source maps without an explicit reason.
- Secrets in the frontend.
- Console errors/warnings.
- Missing error handling.
- Missing 404.
- Broken refresh on nested routes.
- Duplicate business logic.
- Hardcoded fake data.
- Random `setTimeout` calls used as fake loading.
- Excessive `useEffect` usage.
- Excessive global state.
- CSS with arbitrary one-off values everywhere.
- Unused assets and dead code.
- TODO/FIXME placeholders in critical paths.

### Product
- Main action is unclear.
- No useful loading/empty/error states.
- Forms do not explain validation failures.
- Search/filter/pagination are cosmetic.
- Important flows require unnecessary clicks.
- Mobile experience is an afterthought.

---

# 29. EXISTING PROJECT MODE — MANDATORY PROCEDURE

When correcting an existing project, DO NOT immediately rewrite it.

Follow this order:

1. Inspect the repository structure.
2. Inspect package/config files.
3. Identify framework, router, state management and API strategy.
4. Run the project.
5. Reproduce the reported problem.
6. Inspect console and network errors.
7. Inspect the relevant source before editing.
8. Identify the smallest root cause.
9. Fix the root cause with the smallest safe change.
10. Preserve existing behavior that is not part of the defect.
11. Build/lint/test.
12. Recheck the original bug.
13. Check for regressions in nearby flows.
14. Only then perform broader refactors if they are justified.

Never replace a functioning project with a new architecture just because the new architecture is cleaner on paper.

Do not change visual design unless the task requires it or the current design violates the stated standard.

Do not rename public APIs, route paths, component contracts or data fields without a reason and migration impact assessment.

---

# 30. NEW PROJECT MODE — MANDATORY PROCEDURE

When creating a new project:

1. Understand the actual product and users.
2. Define the primary user journeys.
3. Define information architecture/routes/screens.
4. Define the domain entities and business rules.
5. Choose the stack based on requirements rather than trend.
6. Establish design tokens and component conventions.
7. Establish project structure.
8. Implement the critical flow first.
9. Add real states: loading, empty, error, success, permission where relevant.
10. Add accessibility and responsive behavior from the beginning.
11. Add metadata/SEO for public web pages.
12. Add tests around critical behavior.
13. Measure performance.
14. Run a production build.
15. Audit the final project using this document.

Do not spend most of the effort generating decorative landing-page polish before the core flow works.

---

# 31. DEFINITION OF DONE

A feature is not done because the screen looks complete.

Before considering the work complete, verify:

### Product
- The requested behavior works.
- Business rules are implemented correctly.
- No fake functionality remains.

### UI
- Visual hierarchy is intentional.
- Design tokens are consistent.
- The interface is not overloaded with decorative components.

### Accessibility
- Keyboard and focus behavior work.
- Labels and names are present.
- Contrast is acceptable.
- Semantics are meaningful.

### Web
- Routes work.
- 404 works.
- Titles are intentional and distinct.
- Meta descriptions exist where appropriate.
- Canonical strategy is correct.
- OG metadata exists where useful.
- Favicon exists.
- `lang` is correct.
- Sitemap/robots policy is intentional.
- Structured data is truthful where used.
- llms.txt is optional and purposeful, not blindly added.

### Performance
- Initial JavaScript is reasonable.
- Heavy routes/components are split when useful.
- Images are optimized.
- Layout is stable.
- No obvious long tasks or accidental performance regressions.

### Security
- No secrets in client code.
- Authorization is server-side.
- Inputs are validated.
- Dependencies and production artifacts are reviewed.

### Reliability
- No expected console errors.
- Errors have recovery behavior.
- Loading/empty/error states are distinct.

### Code quality
- No duplicated business logic without reason.
- No dead code.
- No meaningless abstractions.
- Naming is consistent.
- Build passes.
- Tests/lint/type checks pass where configured.

---

# 32. INSTRUCTION TO THE AI AGENT

Use this document as a guardrail, not as a checklist to mechanically satisfy.

Before adding any UI or architecture decision, ask internally:

"What user or engineering problem does this solve?"

If the answer is only:
- "It looks modern."
- "AI-generated apps usually have this."
- "It fills space."
- "It makes the dashboard feel richer."
- "It makes the page pop."
- "It is trendy."

do not add it.

Prefer purposeful simplicity over decorative complexity.

Prefer real product behavior over simulated completeness.

Prefer semantic HTML over visual imitation.

Prefer measured performance over assumptions.

Prefer explicit states over generic placeholders.

Prefer consistent design over random variation.

Prefer small safe changes when fixing existing code.

Prefer maintainable code over code that merely compiles.

Never claim a feature, test, integration, SEO improvement or performance improvement was completed unless it was actually implemented and verified.

When auditing an existing project, report findings by category and severity, provide evidence, and distinguish confirmed defects from recommendations or design preferences.


---

# 33. RESEARCH REFERENCES

These references were checked on 2026-09-17. They are supporting references for this standard, not requirements that every application must implement identically.

- Google Search Central — Title links: https://developers.google.com/search/docs/appearance/title-link
- Google Search Central — Meta tags: https://developers.google.com/search/docs/crawling-indexing/special-tags
- Google Search Central — Canonicalization: https://developers.google.com/search/docs/crawling-indexing/canonicalization-troubleshooting
- Google Search Central — Sitemaps: https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
- Google Search Central — Favicons: https://developers.google.com/search/docs/appearance/favicon-in-search
- Google Search Central — Structured data policies: https://developers.google.com/search/docs/appearance/structured-data/sd-policies
- Google Search Central — JavaScript rendering: https://developers.google.com/search/docs/crawling-indexing/javascript/dynamic-rendering
- Google — Google-Extended crawler token: https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers
- W3C WAI — WCAG: https://www.w3.org/WAI/standards-guidelines/wcag/
- W3C WAI — Accessibility principles: https://www.w3.org/WAI/fundamentals/accessibility-principles/
- MDN — `lang` attribute: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/lang
- Vite — Build options/source maps: https://vite.dev/config/build-options
- Vite — Environment variables: https://vite.dev/guide/env-and-mode
- React — `lazy`: https://react.dev/reference/react/lazy
- React — Error boundaries: https://react.dev/reference/react/Component
- web.dev — Code splitting: https://web.dev/articles/reduce-javascript-payloads-with-code-splitting
- web.dev — Long tasks: https://web.dev/articles/optimize-long-tasks
- web.dev — LCP: https://web.dev/articles/optimize-lcp
- web.dev — CLS: https://web.dev/articles/cls
- llms.txt proposal: https://llmstxt.org/
- Vercel — Automatic deployment URLs: https://vercel.com/changelog/urls-are-becoming-consistent
