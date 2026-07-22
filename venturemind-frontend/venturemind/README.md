# VentureMind AI — Frontend

A static, no-build frontend: plain HTML/CSS/JS, no bundler or framework
required. Open `index.html` in a browser, or serve the folder with any
static file server.

## Structure

```
venturemind/
├── index.html          Main marketing site (hero, What/How, pipeline wheel)
├── login.html          Login / sign up / account switcher
├── css/
│   ├── variables.css   Design tokens — light theme in :root, dark theme
│   │                   overrides under html[data-theme="dark"]
│   ├── base.css        Reset, body/background layers, type, shared
│   │                   animations (scroll reveal, ripple, glow)
│   ├── components.css  Nav pill, brand, buttons, dark-mode toggle,
│   │                   signed-in profile dropdown — shared by both pages
│   ├── home.css        Hero, index-nav, What/How sections, pipeline wheel
│   │                   — index.html only
│   └── login.css       Login card, glass blobs, forms, account view
│                       — login.html only
└── js/
    ├── account-store.js  Tiny localStorage wrapper for the mock "signed in"
    │                     state, shared by both pages (see below)
    ├── theme.js           Dark/light toggle, persisted to localStorage
    ├── effects.js         Click ripple + cursor splash trail — shared
    ├── home.js             Pipeline wheel, scroll reveal, hero network
    │                      canvas, index-nav scrollspy, nav profile dropdown
    │                      — index.html only
    └── auth.js             Login/signup forms + account switcher
                            — login.html only
```

## How sign-in works

There's no real backend here — it's a front-end mock. `login.html` writes
the "signed in" account to `localStorage` (`AccountStore` in
`account-store.js`) and then navigates to `index.html`, which reads the same
storage to decide whether to show the "Log in" button or the profile icon in
the nav. This is what lets the signed-in state survive an actual page
navigation between the two files — swap in a real API and `account-store.js`
is the one place that needs to change.

Theme choice (`vm-theme` in localStorage) works the same way, so switching
dark/light mode on one page is reflected on the other.

## Load order matters

Both pages load `account-store.js` before any script that uses
`AccountStore`, and `theme.js`/`effects.js` before the page-specific script.
If you add new files, keep that order in the `<script>` tags at the bottom
of `<body>`.

## Editing tips

- Colors, spacing tokens, and the dark-theme palette all live in
  `css/variables.css` — change a value once there rather than hunting for
  hardcoded colors elsewhere.
- The pipeline wheel's data (which agents, which order per company type)
  lives in `js/home.js`, inside `renderPipeline()`.
