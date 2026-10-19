# Excel Text Browser — Content Add-in

Minimal text-only browsing directly inside Microsoft Excel.

The new UI is an Office Content Add-in, inspired by the existing
LamLongChart example under C:\phong\AI\finance\LamLongChart\examples\excel-content-addin.
It provides an address/search field, Back, Forward, Reload, History and clickable
links. No C4, no Excel-cell commands and no PowerShell while browsing.

Chrome Profile 3 is reused through its existing CDP Remote Debugging endpoint.
Web pages execute inside Chrome; Excel displays only text, no images or videos.
The add-in uses lightweight HTML, CSS and JavaScript for buttons and links;
Java (the programming language) is not used.

## First-time setup on this PC

1. Double-click Install Text Browser.cmd in the repository folder. This checks
   dependencies, starts the HTTPS backend hidden and configures automatic startup
   on Windows sign-in for the current user (HKCU Run). This is a one-time action.
2. In Excel select Home > Add-ins > My Add-ins > Manage My Add-ins > Upload My Add-in.
3. Select the manifest:
   C:\phong\AI\other\bs-in-excel\main\addin\manifest.xml
4. Choose Text Browser and insert it into your workbook. Save the workbook
   if you wish to keep the embedded content add-in.

The installer reuses the HTTPS certificate already installed for L2Chart.
Its observed expiry on this PC is November 4, 2026; renew it before then.
If you prefer not to enable automatic startup, you can run install_once.ps1
with -NoAutoStart and double-click Open Text Browser.vbs whenever needed.

## Daily use

Type directly in the add-in address bar.

- Siemens page: https://www.siemens.com/ja-jp/products/tia-portal/
- Google query: siemens tia portal
- Click a result or link to open it.
- Use Back, Forward, Reload, History buttons; no command syntax.

The backend runs locally at https://localhost:3010, hidden and without
a terminal window. The add-in doesn't touch workbook cells, formulas, or
other sheets. History stays under %LOCALAPPDATA%\bs-in-excel\, outside Git.

## Architecture

    Excel Content Add-in (HTML/CSS/JS)
        -> HTTPS loopback API (text_browser/service.py)
        -> one existing Chrome Profile 3 CDP session
        -> visible page text + clickable links + history

Browser startup is lazy: one dedicated Chrome tab is created on first browse
and reused. Image, media and font requests are blocked only for that tab.
The single-threaded HTTP server keeps sync Playwright calls on one thread.
All website content enters the add-in as textContent, never as raw HTML.

Files:
- addin/: Office manifest and minimal text-only UI
- text_browser/service.py: HTTPS loopback API
- text_browser/browser.py: Chrome CDP and text/link extraction
- text_browser/history.py: local history
- tests/: unit and HTTP tests
- Install Text Browser.cmd / install_once.ps1: one-time installer
- Open Text Browser.vbs: optional hidden launcher
- run_addin.pyw: backend Windows entry point

The old COM/C4 polling implementation has been removed. There is only one
supported integration path: the Excel Content Add-in.

## Tests

    python -m unittest discover -s tests -v
    node --check addin/app.js

The backend was tested live on this PC against the Siemens TIA Portal page
and Google search for "siemens tia portal". Actual Excel Office Add-in
integration still requires uploading the manifest once.

## Security and limits

- The HTTPS service listens only at 127.0.0.1 and validates POST Origin.
- Chrome remote debugging grants broad browser access. Trust only known tools.
- Cookies and credentials are not exported to the source repository.
- CAPTCHA, login gates and complex interactive websites may not yield text.
- Google may enforce its own automated-access restrictions.
- The localhost certificate must be renewed before it expires.
