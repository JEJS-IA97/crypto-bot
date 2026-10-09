# ANTI-VIBECODE — AI CODING PROMPT

Use these instructions whenever you create a new application or modify an existing one.

Your goal is to produce software that looks and behaves as if it was intentionally designed, engineered, tested and maintained by a real product team. Do not optimize for the appearance of an AI-generated demo.

## Absolute rules

Do not add UI, architecture, dependencies, animations, metadata or abstractions unless they solve a real user, product or engineering problem.

Do not fabricate functionality. Search, filters, pagination, authentication, notifications, live states, charts, persistence, API calls and success messages must reflect real behavior or be explicitly marked as mocked.

Do not invent business rules, security rules, API contracts, permissions, financial calculations, prices or legal claims. Isolate reasonable assumptions so they are easy to change.

Prefer purposeful simplicity over decorative complexity.

Do not make every section a card. Do not use neon gradients, purple gradients, glow, glassmorphism, badges, status dots, emoji icons or decorative tabs merely because they are common in generated interfaces. Use them only when the product context justifies them.

Create a coherent design system before styling the entire application: typography, colors, spacing, radii, borders, shadows, icons, states and interaction patterns must be consistent.

Use semantic UI. Buttons perform actions; links navigate; lists represent lists; tables represent structured comparable data; forms represent input workflows.

Every meaningful async flow must distinguish loading, success, empty and error states. Add permission, offline or partial-data states when relevant.

Do not hide errors. Do not turn failed requests into empty data unless that is an explicit product rule. Do not claim success without confirmation.

## Accessibility

Target WCAG 2.2 principles.

Use semantic HTML where applicable, meaningful heading hierarchy, associated labels, visible focus, keyboard support, accessible names for icon-only controls, appropriate alt text, sufficient contrast, and information that does not depend on color alone.

Do not use `<div>` as an action control when a native button is appropriate.

Do not rely on the HTML `title` attribute as the only important tooltip/instruction mechanism.

## Web SEO and discoverability

For public indexable web pages, use intentional page metadata:
- unique descriptive title;
- useful meta description;
- canonical strategy;
- Open Graph metadata when useful;
- favicon;
- correct `lang`;
- meaningful heading structure;
- truthful structured data when applicable;
- sitemap when appropriate;
- intentional robots policy;
- stable public URLs.

Do not treat these as universal requirements for private applications.

Do not blindly add `llms.txt`. It is an emerging convention/proposal, not a universal mandatory standard. Add it only when it provides real, useful guidance for agents.

Do not assume a React/Vite SPA is automatically SEO-ready. Choose CSR, SSR, SSG or pre-rendering according to the content and discovery requirements.

Do not assume an empty `view-source` response automatically means the site is broken. Verify the rendered HTML, crawlability and required content.

Do not assume multiple `<h1>` elements are automatically a defect. Ensure the document has a clear semantic hierarchy and an unambiguous primary page topic.

Do not assume a `vercel.app` hostname is itself a defect. For production, use the intended public/canonical domain when available.

## Performance

Keep the initial JavaScript payload reasonable.

Use route/component code splitting for appropriate heavy or non-critical features. Lazy-load expensive non-critical components when beneficial. Avoid unnecessary dependencies, duplicate libraries, huge images, excessive third-party scripts, unnecessary global animations and expensive work on the main thread.

Optimize images, fonts and layout stability. Measure performance rather than guessing.

For web apps, monitor Core Web Vitals where appropriate, especially LCP, CLS and INP.

## Security

The frontend is not a trusted security boundary.

Never ship secrets to the browser. For Vite, anything exposed through `VITE_*` is client-side data and must not contain secrets.

Perform authorization on the server. Validate inputs on the server. Review XSS/injection paths, CORS, security headers, dependencies, rate limiting for sensitive operations, and sensitive data in logs.

Do not rely on obfuscation to hide secrets.

## Production artifacts

Review source maps, unminified bundles, debug artifacts, environment files and build output before release.

Do not expose production source maps by default without an explicit operational reason.

## React quality

Prefer function components.

Avoid giant components, giant utility files, giant API modules, duplicate business logic and premature abstractions.

Do not use `useEffect` as the default solution for every state/data problem.

Do not add `useMemo` or `useCallback` everywhere without a reason.

Use stable list keys based on item identity.

Use lazy loading and meaningful error boundaries when they provide real value.

## Mobile quality

A mobile application must not be treated as a desktop web page placed inside a phone.

Handle navigation/back behavior, keyboard interaction, safe areas, network failures, permissions and long lists deliberately. Test realistic device sizes and poor network conditions where relevant.

## Existing-project mode

When modifying an existing project:

1. Inspect the repository before editing.
2. Inspect package/config files.
3. Identify framework, routing, state, data and API architecture.
4. Run the application.
5. Reproduce the issue.
6. Inspect console/network errors.
7. Inspect relevant source.
8. Find the root cause.
9. Make the smallest safe fix.
10. Preserve unrelated working behavior.
11. Build/lint/test.
12. Reproduce the original issue again.
13. Check nearby regressions.
14. Refactor only when justified.

Do not rewrite a functioning application merely because a different architecture looks cleaner.

Do not redesign unrelated UI when fixing a functional bug.

## New-project mode

When creating from zero:

1. Understand the product and users.
2. Define primary user journeys.
3. Define routes/screens and information architecture.
4. Define entities and business rules.
5. Choose technology based on requirements.
6. Establish design tokens and component conventions.
7. Establish a maintainable project structure.
8. Build the critical user flow first.
9. Add realistic loading/empty/error/success states.
10. Add accessibility and responsive behavior from the beginning.
11. Add web SEO metadata where applicable.
12. Test critical behavior.
13. Measure performance.
14. Run the production build.
15. Perform an anti-vibecode audit before declaring completion.

## Audit mode

When auditing, classify findings as:
- CRITICAL: security, data integrity, broken core functionality or release blocker.
- HIGH: major UX, accessibility, reliability, SEO or performance problem.
- MEDIUM: meaningful quality issue with limited scope.
- LOW: minor defect or cleanup opportunity.
- RECOMMENDATION: improvement or preference, not a confirmed defect.

For every confirmed defect, provide evidence. Never present a design preference as a technical defect.

## Definition of done

The task is not complete merely because the UI renders.

Confirm that requested behavior works, business rules are correct, no fake functionality remains, responsive behavior is intentional, accessibility basics work, routes work, web metadata is intentional where applicable, security boundaries are respected, performance is reasonable, errors are handled, and the production build/tests pass where configured.

Do not claim that an integration, test, SEO fix, performance improvement or security improvement was completed unless it was actually implemented and verified.
