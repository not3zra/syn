---
name: syn
description: A calm security console that governs AI agent tool calls with deterministic, session-aware scoring.
colors:
  bg: "#0a0b0e"
  surface: "#121418"
  card: "#1a1d24"
  raised: "#22262f"
  border: "#2a2e38"
  ink: "#f0f1f3"
  ink-secondary: "#aeb3bf"
  ink-muted: "#7c8290"
  accent: "#2bb9b0"
  accent-hover: "#4fc9c0"
  approved: "#22c55e"
  escalated: "#eab308"
  blocked: "#ef4444"
  tier: "#8b93a3"
typography:
  display:
    fontFamily: "Inter, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "clamp(1.5rem, 3vw, 2.25rem)"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Inter, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "'JetBrains Mono', 'SF Mono', ui-monospace, Menlo, monospace"
    fontSize: "0.75rem"
    fontWeight: 500
    letterSpacing: "0.04em"
rounded:
  sm: "6px"
  md: "10px"
  lg: "14px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#06201e"
    rounded: "{rounded.sm}"
    padding: "12px 18px"
    fontWeight: 600
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  input:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "10px 12px"
---

# Design System: syn

## 1. Overview

**Creative North Star: "The Calm Watchtower"** — a security console that stays composed while everything around it is noisy. It reports exactly what an agent did, why it mattered, and what to do next, without raising its voice.

syn is a governance checkpoint for AI agents. Every tool call is intercepted, scored against six deterministic risk factors, checked for dangerous sequences across a session, and either approved, escalated, or blocked. The interface serves the reviewer, the compliance officer, and the hackathon judge equally: it must make the differentiator (session-pattern correlation) obvious and keep its composure when an action is escalated or blocked.

This system explicitly rejects the generic SaaS indigo dashboard, frosted-glass decoration, gradient text, all-caps eyebrow kickers, and marketing buzzwords. It is dark by design (a low-light security-operations scene), precise by typography, and restrained by color: one teal accent, four decision colors, everything else neutral ink on near-black.

**Key Characteristics:**
- Single teal accent, used sparingly; decision state carried by green / amber / red.
- Monospace reserved for scores, triggers, and codes; a clean grotesque for everything a human reads.
- Flat surfaces by default; depth comes from tonal layering, not shadows.
- Copy is verb-plus-object and specific; no jargon, no em dashes.

## 2. Colors

A restrained dark palette: near-black neutrals carry the surface, one teal accent carries the brand, and four semantic colors carry decision state. The accent appears on at most ~10% of any screen.

### Primary
- **Signal Teal** (#2bb9b0): the only brand accent. Focus rings, the logo mark, the primary action, active nav, links. Never used as a background wash. Hover lightens to #4fc9c0.

### Neutral
- **Abyss** (#0a0b0e): app background. A true neutral near-black, not a warm tint.
- **Surface** (#121418): sidebar, top bar, panels.
- **Card** (#1a1d24): receipt, bootstrap review, timeline entries.
- **Raised** (#22262f): footer, nested regions.
- **Hairline** (#2a2e38): borders and dividers.
- **Ink** (#f0f1f3): primary text.
- **Ink Secondary** (#aeb3bf): supporting text, labels. Bumped from the old #9498a5 for AA.
- **Ink Muted** (#7c8290): small meta text. Bumped from the old #5c6070, which failed AA on the background.
- **Tier Slate** (#8b93a3): regulatory-tier badge, rendered as a neutral outline chip so it never collides with the teal accent.

### Semantic (decision state)
- **Approved** (#22c55e): auto-approved decisions.
- **Escalated** (#eab308): held for human review.
- **Blocked** (#ef4444): rejected or failed-closed.

### Named Rules
**The One Voice Rule.** The teal accent covers at most 10% of any screen. Its rarity is the point: when teal appears, it means "this is the brand or the primary action." Decision colors do the talking everywhere else.

**The Status Is Color, Not Decoration Rule.** Green, amber, and red mean approved, escalated, and blocked. They are never used for branding, links, or empty decoration.

## 3. Typography

**Display Font:** Inter (with -apple-system, Segoe UI, Roboto fallback).
**Body Font:** Inter (same stack).
**Label/Mono Font:** JetBrains Mono (with SF Mono, ui-monospace fallback).

**Character:** A single humanist grotesque carries the whole interface through weight contrast, not two competing sans-serifs. Monospace is reserved for machine-readable content: scores, trigger strings, agent IDs, timestamps, and YAML. This split makes "what the engine decided" visually distinct from "what a human is told."

### Hierarchy
- **Display** (600, clamp(1.5rem, 3vw, 2.25rem), line-height 1.1, -0.02em): page and receipt titles, the wordmark.
- **Headline** (600, 1.125rem, 1.2): section titles within a surface.
- **Title** (600, 0.9375rem, 1.4): component titles, list headers.
- **Body** (400, 0.9375rem, 1.6, max 70ch): explanations, remediation, prose.
- **Label** (500, 0.75rem mono, 0.04em, uppercase for short tags only): factor names, IDs, meta.

### Named Rules
**The Mono Boundary Rule.** If a string came from the engine (a score, a `session:pattern_matched` trigger, an `agent_id`, a timestamp, YAML), it is monospace. If a human reads it as prose, it is Inter. No exceptions for "style."

## 4. Elevation

This system is flat by default. Depth is conveyed by tonal layering (Abyss → Surface → Card → Raised) and a single hairline border, not by drop shadows. Shadows appear only as a subtle, low-blur response to state (focus, active panel), never as wide decorative glows.

### Shadow Vocabulary
- **Focus** (`0 0 0 2px rgba(43,185,176,0.5)`): teal focus ring on keyboard-focused controls. No offset blur, no ghost-card combo.
- **Active Panel** (`0 2px 8px rgba(0,0,0,0.4)`): the currently focused right-hand panel, used sparingly and at most 8px blur.

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat at rest. A shadow means state changed, not that the element is important. Never pair a 1px border with a wide soft shadow on the same element.

## 5. Components

### Buttons
- **Shape:** radius 6px (sm).
- **Primary:** Signal Teal background (#2bb9b0), near-black text (#06201e) for AA contrast, 12px 18px padding, weight 600. Used for the single most important action on a screen (send action, approve).
- **Hover / Focus:** lightens to #4fc9c0; focus shows the teal ring. No transform bounce.
- **Secondary / Ghost:** transparent background, Ink Secondary text, hairline border; used for reject, reset, and less important actions.

### Chips
- **Style:** 4px radius, uppercase 0.7rem mono label, tinted background at 8% alpha of the semantic color, 1px border at 20% alpha.
- **State:** approved / escalated / blocked / tier variants; never interactive unless explicitly a filter.

### Cards / Containers
- **Corner Style:** 14px (lg) for large surfaces (receipt, panels), 10px (md) for inner blocks.
- **Background:** Card (#1a1d24) on Surface (#121418).
- **Shadow Strategy:** flat; hairline border only.
- **Border:** 1px Hairline (#2a2e38).
- **Internal Padding:** 20–24px.

### Inputs / Fields
- **Style:** Card background, Ink text, Hairline border, 6px radius, 10px 12px padding.
- **Focus:** border shifts to Signal Teal, plus the teal focus ring.
- **Error / Disabled:** blocked-red border at 20% alpha for error; 50% opacity for disabled.

### Navigation
- **Style:** a slim left identity rail (logo + wordmark + live demo status) and a top bar carrying the primary action. No full nav menu; the console has one job.
- **Active state:** teal text or a 2px teal left marker on the active rail item. No wide tracking, no all-caps eyebrows.

### Signature Component: Trust Receipt
The hero. A centered card showing the decision badge (color + weight, not just a border tint), the six-factor breakdown, the exact deterministic trigger string in mono, regulatory-tier badges, the AI explanation, an audit hash, and a timestamp. It must read as a "receipt" for a governed action: precise, complete, calm.

## 6. Do's and Don'ts

### Do:
- Do use Signal Teal for the brand mark, focus rings, and the single primary action only.
- Do render decision state in green / amber / red with both color and weight.
- Do set body text to Ink (#f0f1f3) and small meta to at least Ink Muted (#7c8290) so contrast clears AA.
- Do keep the interface dark, flat, and tonally layered.
- Do write button labels as verb + object ("Approve tool", "Reject", "Reset demo").

### Don't:
- Don't use the default SaaS indigo (#6366f1) or any purple/indigo accent; the brand is teal.
- Don't use glassmorphism, frosted glass, or gradient text.
- Don't put an all-caps eyebrow kicker above every section.
- Don't use buzzwords ("seamless", "empower", "unleash", "next-gen", "world-class").
- Don't use em dashes in copy.
- Don't pair a 1px border with a wide soft shadow on the same element (no ghost-card).
- Don't use side-stripe accent borders (border-left greater than 1px as color) on cards, lists, or alerts.
- Don't make the regulatory-tier badge teal or blue; keep it a neutral slate outline so it never reads as the brand.
