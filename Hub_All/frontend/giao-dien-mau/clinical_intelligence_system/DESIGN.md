---
name: Clinical Intelligence System
colors:
  surface: '#faf9fe'
  surface-dim: '#dad9df'
  surface-bright: '#faf9fe'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f4f3f8'
  surface-container: '#eeedf3'
  surface-container-high: '#e9e7ed'
  surface-container-highest: '#e3e2e7'
  on-surface: '#1a1b1f'
  on-surface-variant: '#464554'
  inverse-surface: '#2f3034'
  inverse-on-surface: '#f1f0f5'
  outline: '#777585'
  outline-variant: '#c7c4d6'
  surface-tint: '#4f4ccd'
  primary: '#3f3bbd'
  on-primary: '#ffffff'
  primary-container: '#5856d6'
  on-primary-container: '#e7e4ff'
  inverse-primary: '#c2c1ff'
  secondary: '#0058bc'
  on-secondary: '#ffffff'
  secondary-container: '#0070eb'
  on-secondary-container: '#fefcff'
  tertiary: '#7c17ab'
  on-tertiary: '#ffffff'
  tertiary-container: '#9739c6'
  on-tertiary-container: '#f8deff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e2dfff'
  primary-fixed-dim: '#c2c1ff'
  on-primary-fixed: '#0c006a'
  on-primary-fixed-variant: '#3631b4'
  secondary-fixed: '#d8e2ff'
  secondary-fixed-dim: '#adc6ff'
  on-secondary-fixed: '#001a41'
  on-secondary-fixed-variant: '#004493'
  tertiary-fixed: '#f6d9ff'
  tertiary-fixed-dim: '#e8b3ff'
  on-tertiary-fixed: '#310048'
  on-tertiary-fixed-variant: '#7201a2'
  background: '#faf9fe'
  on-background: '#1a1b1f'
  surface-variant: '#e3e2e7'
typography:
  headline-xl:
    fontFamily: Manrope
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Manrope
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Manrope
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  headline-xl-mobile:
    fontFamily: Manrope
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  sidebar-width: 260px
  container-max: 1440px
  gutter: 24px
  margin-mobile: 16px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style

The design system is built on a foundation of **Professional Modernism**, specifically tailored for high-stakes healthcare administration and knowledge management. It prioritizes clarity, speed of cognition, and a sense of "Clinical Calm."

The personality is authoritative yet accessible, using a refined corporate aesthetic that avoids the sterility of traditional medical software. It leverages a "Tonal Layering" approach where content is organized on distinct planes to reduce cognitive load in data-heavy environments.

**Design Style: Modern Corporate**
- **Clarity First:** Generous whitespace ensures that medical data and wiki entries remain the primary focus.
- **Subtle Technicality:** Precise line-work and a systematic grid reflect the accuracy required in healthcare.
- **Trust-Driven:** A palette of deep indigos and balanced purples evokes reliability and modern technological capability.

## Colors

The palette is a sophisticated evolution of the source material, moving away from high-saturation vibrance toward a more "Professional Healthcare" spectrum.

- **Primary (Indigo-Violet):** Used for primary actions, active states in the sidebar, and key brand moments. It suggests intelligence and depth.
- **Secondary (Clinical Blue):** Reserved for information-dense elements like links, specific data tags, and "Sync" statuses to provide a familiar digital affordance.
- **Surface Scale:** The interface uses a multi-step gray scale (Slate/Zinc) to create hierarchy. The main background is a cool-tinted off-white (`#F8FAFC`), which allows pure white cards to "pop" effectively.
- **Semantic Colors:** Success, Warning, and Error states utilize slightly desaturated tones to maintain the professional atmosphere without being visually jarring.

## Typography

Typography focuses on maximum legibility for long-form medical documentation and complex data tables.

- **Headings (Manrope):** Chosen for its modern, geometric structure and excellent legibility at larger scales. It provides a contemporary "Tech-Health" feel.
- **Body & Data (Inter):** The industry standard for UI. Its tall x-height and neutral character make it ideal for reading dense lists of files, logs, and AI-generated responses.
- **Information Density:** Use `body-sm` for secondary metadata (e.g., file sizes, dates) to keep the primary visual path clear. `label-md` is reserved for navigation category headers and table headers.

## Layout & Spacing

The layout follows a **Fixed-Sidebar Fluid-Content** model. 

- **Structure:** A persistent left sidebar (260px) houses the primary navigation and organization switcher. The main content area utilizes a fluid grid that expands to a max-width of 1440px to ensure line lengths for text-heavy wiki pages remain readable.
- **Rhythm:** An 8px base grid is used for all internal component spacing.
- **Information Grouping:** Content is grouped into "Logical Buckets" using white surfaces with subtle 1px borders. 
- **Breakpoints:**
  - **Desktop (1280px+):** Full sidebar visible.
  - **Tablet (768px - 1279px):** Sidebar collapses to icons only or a hamburger menu. Gutters reduce to 16px.
  - **Mobile (<767px):** Single column flow. Header search becomes an icon-trigger.

## Elevation & Depth

This design system avoids heavy shadows, opting instead for **Tonal Elevation** and **Low-Contrast Outlines**.

- **Level 0 (Background):** `#F8FAFC` - The canvas.
- **Level 1 (Main Surfaces):** White (`#FFFFFF`) with a 1px border of `#E2E8F0`. No shadow. Used for the sidebar and secondary content blocks.
- **Level 2 (Active Cards/Modals):** White with a very soft, highly diffused ambient shadow (0px 4px 12px rgba(0,0,0,0.05)). This is used for the main data tables and AI response containers to make them feel "floating" and interactive.
- **Interactive States:** On hover, cards may transition to a slightly deeper shadow or a primary-tinted border to indicate clickability.

## Shapes

The shape language is "Softly Geometric." 

- **Standard Radius:** 8px (0.5rem) is the default for buttons, input fields, and cards. This strikes a balance between professional rigor and modern friendliness.
- **Large Radius:** 16px (1rem) is used for top-level layout containers or specific "AI Insights" banners to distinguish them from standard data.
- **Search Bars:** Utilize a fully pill-shaped (100px) radius to differentiate "Utility" elements from "Content" elements.

## Components

### Sidebar & Navigation
- **Active State:** A solid background of `primary-subtle` (a 10% opacity version of the primary color) with a 4px vertical "indicator bar" on the left or right edge.
- **Category Labels:** Use `label-md` with neutral-secondary color.

### Data Tables & Lists
- **Rows:** Minimum height of 56px. Rows should have a subtle hover state (`#F1F5F9`).
- **Icons:** Use consistent 20px line icons (e.g., Lucide or Phosphor) with a light gray-blue background for document types.

### Buttons
- **Primary:** Solid indigo background with white text.
- **Secondary/Ghost:** Transparent background with a 1px border of the primary color or neutral-slate.
- **Size:** Standard buttons are 40px high; Small buttons for table actions are 32px.

### Search & Inputs
- **Global Search:** Should feature a "K" shortcut hint. The background should be a very light gray (`#F1F5F9`) to sit recessed within the header.
- **Input Focus:** Focus states must use a 2px outer glow of the primary color with 20% opacity.

### AI Interaction
- **Chat Bubbles:** AI responses are housed in Level 2 cards with a distinct "Sparkle" icon to denote machine-generated content.
- **Source Citations:** Displayed as small, pill-shaped chips at the bottom of AI responses, using `body-sm` typography.