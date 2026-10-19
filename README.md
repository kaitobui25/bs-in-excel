# Text Browser in Excel

A minimal, text-only Excel Content Add-in. Open URLs, search, follow links,
Back / Forward / Reload and History. No images or videos are shown. No VBA,
Excel-cell polling or terminal is required for daily use.

## Current Windows PC: one-click startup

1. Double-click the **Text Browser Excel** desktop shortcut, or run
   `Open Text Browser.vbs` in this folder.
2. An Excel workbook opens with an embedded text browser. Type into its
   address bar, press Enter, or click the on-screen buttons.

The reusable workbook is `Text Browser.xlsx` next to this README. Its Office
Content Add-in manifest points to the local trusted catalog at
`\\localhost\C$\phong\AI\other\bs-in-excel\main\addin`. This path is specific
to the current PC; other PCs require their own catalog registration.

The launcher starts the backend hidden if it is not already running. The
backend is also configured to start automatically at Windows sign-in.
To reconfigure installation, run `Install Text Browser.cmd` once.

## Usage

- URL: `https://www.siemens.com/ja-jp/products/tia-portal/`
- Search phrase: `siemens tia portal`
- Click a result or one of the Back / Forward / Reload / History buttons.

**Google Search limitation:** Google currently returns a redirect/interstitial
instead of useful text to this PC's automated requests. In that case the tool
shows results from Yahoo! Japan with an explicit fallback label. A link labeled
"Mở Google trong trình duyệt ngoài" opens the real Google search in an external
browser. Yahoo! results must not be mistaken for Google results.

## Architecture

    Excel Content Add-in (addin/index.html, app.js, style.css)
        -> HTTPS localhost API (text_browser/service.py)
        -> HTML requests + parser (text_browser/http_browser.py)
        -> plain text and clickable links

HTTP is the fast default; it does not launch or control Chrome. If you need
client-rendered sites and are willing to approve Chrome Remote Debugging,
set environment variable `BS_EXCEL_BROWSER_MODE=cdp` before starting the
backend. That optional mode uses Playwright and Chrome Profile 3 and can be
limited by browser consent/permissions. No login or cookies are copied by
the default mode.

History and runtime logs are local under `%LOCALAPPDATA%\bs-in-excel\`.
The HTTPS server binds to `127.0.0.1:3010`; website text is rendered via
DOM textContent rather than inserting remote HTML. The same Chrome instance
used for personal browsing is never touched by default.

The Office localhost certificate was observed to expire on **2026-11-04**.
Renew the Office development certificate before that date if using the add-in
beyond the current development period.

## Development

    python -m pip install -r requirements.txt
    python -m unittest discover -s tests -v
    node --check addin/app.js

The Office Content Add-in was installed using a trusted **FileSystem** catalog
reference. The earlier dev-settings-generated workbook with the `Registry`
reference caused "only available during debugging" and should not be used.

This is a local development deployment, not a public Office marketplace add-in.
The starter workbook was generated with Microsoft's `office-addin-dev-settings`
development tooling (MIT licensed) and its web-extension reference was changed
to the local trusted `FileSystem` catalog for regular use.
