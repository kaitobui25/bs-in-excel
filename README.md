# Text Browser in Excel

A minimal, text-only Excel Content Add-in. Open URLs, search, follow links,
Back / Forward / Reload and History. No images or videos are shown. No VBA,
Excel-cell polling or terminal is required for daily use.

## Current Windows PC: one-click startup

1. Double-click the **Text Browser Excel** desktop shortcut, or run
   `Open Text Browser.vbs` in this folder.
2. An Excel workbook opens with an embedded text browser. Hover over the
   area below the fixed reader menu to reveal the navigation bar, or select
   the menu's address button (☰). Type into the address field and press Enter,
   or click a navigation button. Move away to hide the bar, or click ☰ to
   toggle it. Keyboard Tab focus also reveals it.
   The reading view omits the load statistics and duplicate page URL; the URL
   remains available in the navigation bar. Errors still appear in the view.

The reader menu stays visible while scrolling. **↑ Đầu trang** scrolls the
current Excel reading pane back to the top, without navigating in BrowserOS
Neo. **EN** and **VI** translate the text currently displayed to English or
Vietnamese, while **Gốc** restores the original content. Translation keeps
clickable URLs, image placeholders and Facebook See more / See less controls;
the chosen language also applies to subsequently loaded content. The backend
uses Google's lightweight, unofficial dictionary translation endpoint in
bounded batches, without opening Neo tabs. Only selected visible page text is
sent to Google when translation is requested. This endpoint may reject or
rate-limit requests; the menu displays a translation error when it does.

The reusable workbook is `Text Browser.xlsx` next to this README. Its Office
Content Add-in manifest points to the local trusted catalog at
`\\localhost\C$\phong\AI\other\bs-in-excel\main\addin`. This path is specific
to the current PC; other PCs require their own catalog registration.

The launcher starts the backend hidden if it is not already running. The
backend is also configured to start automatically at Windows sign-in.
To reconfigure installation, run `Install Text Browser.cmd` once.

## Usage

- URL: `https://www.siemens.com/ja-jp/products/tia-portal/`
- Facebook: `https://www.facebook.com/` or public pages such as
  `https://www.facebook.com/Siemens/`
- Facebook home feed: posts appear as separate text cards; scroll to the bottom
  or select **Tải thêm bài viết** to fetch later posts without losing those loaded.
- Search phrase: `siemens tia portal`
- Click a result or one of the Back / Forward / Reload / History buttons.

**Search:** Google currently returns a redirect/interstitial rather than useful
text to automated requests on this PC, so the tool retrieves results from
Yahoo! Japan instead. It shows a neutral search title without a technical
fallback banner; the actual source remains visible in the address bar.
Results are not represented as if they came directly from Google.
Normal text links are clickable in their original reading positions.
Filtered image positions display small empty picture outlines, not image data.

**Page title filter:** only pages on `siemens.com` and its subdomains show the
large page title above the text. Facebook, social networks, news and other
websites show their URL and content without that page title. Browsing history
uses the URL instead of the title for those sites. Add new domains to
`TITLE_HOSTS` in `text_browser/title_filter.py` to extend the allow-list.
Page content headings and Facebook post authors remain visible.

## Architecture

    Excel Content Add-in (addin/index.html, app.js, style.css)
        -> HTTPS localhost jobs API (text_browser/service.py, jobs.py)
           -> independent HTTP + HTML streaming for ordinary sites
           -> serialized BrowserOS Neo MCP for Facebook
        -> progressive text and clickable links

**Navigation responsiveness:** `POST /api/jobs` responds immediately with a
random `job_id`. Excel polls `GET /api/jobs/<job_id>?since=<version>` every
260 ms while the task is active. Responses move through `pending`, `partial`
and `complete` (or `error`). The API stores only the latest page snapshot per
job, not an ever-growing stream. On slow, large HTTP pages, an initial text
snapshot is available after enough HTML arrives; small pages usually finish
before a partial snapshot is worthwhile. Facebook publishes already-filtered
posts from the first feed read before continuing its background scan.

The localhost server accepts concurrent requests. Independent HTTP fetches do
not wait for a slow Neo command. Neo operations targeting the same background
tab remain serialized; this protects the browser session but means a new Neo
operation can still wait for the old command's timeout. A newer navigation
supersedes the previous task, preventing stale results from overwriting the
current view or browser history. In-progress HTTP downloads stop at the next
chunk after cancellation; an already-running Neo command cannot be forcibly
aborted. Back, Forward, Reload, History and Facebook load-more are supported.
The original synchronous `/api/browse` route remains for compatibility.
The backend logs time to first content and completion in `addin.log`.

HTTP is the fast default for normal sites. Facebook rejects plain HTTP
requests, so opening Facebook connects to **BrowserOS Neo** through its local
MCP endpoint `http://127.0.0.1:9010/mcp`. **Start BrowserOS Neo before using
Facebook in Excel.** The backend lazily creates one Neo background tab and
reuses it, including after a backend restart or an expired MCP session. It
remembers that tab's `tabId` and `groupId` locally in
`%LOCALAPPDATA%\bs-in-excel\neo-facebook-tab.json`. If the tab was closed,
the next visit creates one replacement. The tab is left open when the backend
stops, so later launches can reuse it. Older duplicate agent tabs from
previous versions are not automatically closed. Personal tabs are never
selected for reuse. The Neo session/profile owns its own login state; no
cookies, tokens, or profile files are copied from other browsers.

**First-time Facebook setup:** sign in to Facebook in the BrowserOS Neo app
once, then open/reload Facebook in the Excel add-in. The login is kept by
BrowserOS Neo, subject to Facebook's login policy. Facebook access remains
limited by account permissions; CAPTCHA/authentication are not bypassed.

Facebook uses its rendered DOM to collect posts in short batches, then sends
only text, links, and image placeholders to Excel. Common video file URLs are
blocked on the add-in's Neo tab through page-scoped CDP where supported;
some network media requests may still occur inside Neo. No media is shown in
Excel. The reader caps a feed at 80 posts and 3,500 characters per post for
responsiveness. The Neo `run` API has a 30-second limit per batch.
Facebook posts initially show up to four visual lines. **See more** expands a
long post and **See less** collapses it; short posts do not show a toggle.
Expanded posts stay open when additional feed posts are loaded. This applies
only to post bodies, not ordinary webpages or search results.
When present, `[data-ad-preview="message"]` supplies post body text, excluding
Facebook's obfuscated timestamp links near the author. Shared preview links
and whole-card ad metadata are still considered; older layouts without a
message element fall back to the card text.
The reader skips posts explicitly marked as sponsored (including Vietnamese,
English and Japanese labels) and unlabelled commercial promotions, identified
using a combination of sales calls to action (inbox/order/contact), price,
discounts, service/product descriptions, business-page names and shop links.
The extractor also detects contact/purchase buttons on Facebook Page cards;
the local filter recognizes enrollment promotions in Japanese, business/shop
posts in Chinese, and brand-product descriptions without an explicit price.
It normalizes styled Unicode only for classification, so stylized WiFi sales
text is detected without altering the displayed post. It also recognizes
branded free-trial calls to action, promotional follow/share giveaways,
property listings with phone contacts, and plugin-download pitches. A brand
name alone is not enough to hide a post.
Rejected posts are excluded from feed pagination targets so scrolling can
continue to the next regular post. The filter is local and rule-based;
Facebook does not expose a stable advertising flag for all promotional posts,
so some ads may still pass through and some borderline commercial posts may be
hidden. Adjust the patterns in `text_browser/facebook_ads.py` as needed. The
filter does not change Facebook or Neo account settings.
If Neo expires its MCP session, opening a URL automatically reconnects once
in a new add-in-owned tab. Scrolling/loading more is not silently replayed.

For other client-rendered sites, set `BS_EXCEL_BROWSER_MODE=neo` before starting
the backend to use Neo on all sites. The old `cdp` mode name is accepted as an
alias for compatibility. The MCP URL can be configured via
`BS_EXCEL_NEO_MCP_URL` if necessary; keep the service restricted to a trusted
local environment.

History and runtime logs are local under `%LOCALAPPDATA%\bs-in-excel\`.
The HTTPS server binds to `127.0.0.1:3010`; website text is rendered via
DOM textContent rather than inserting remote HTML. The Python backend talks
to Neo directly over HTTP JSON-RPC with a reused MCP session; no Playwright,
Chrome remote-debugging setup, or PowerShell/curl browser calls are required.

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
