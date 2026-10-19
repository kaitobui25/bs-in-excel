# Excel Text Browser

A compact text-only web browser that runs inside an already-open Microsoft Excel workbook.
The Python process attaches to a Chrome instance via its existing Chrome DevTools Protocol (CDP) endpoint. It creates one dedicated tab in the existing browser session and never reads or changes other tabs.

## Requirements

- Windows + desktop Excel (tested with Office 64-bit)
- Chrome running with Remote Debugging enabled via chrome://inspect/#remote-debugging
- Python 3.12+ and packages from requirements.txt

## Install and start

Open the workbook in Excel. From this directory run the following PowerShell commands:

    python -m pip install -r requirements.txt
    powershell -ExecutionPolicy Bypass -File .\start.ps1

The launcher starts one Python process without a visible console. It creates a "Text Browser" sheet in the active workbook, without touching your other sheets. **The workbook is not saved automatically.**

## How to use it

Enter a URL or a search query into **C4**, then press Enter.

| Input | Result |
| --- | --- |
| https://www.siemens.com/ja-jp/products/tia-portal/ | Visit Siemens TIA Portal |
| siemens tia portal | Search on Google |
| :open 1 | Open displayed link number 1 |
| :back | Go back |
| :forward | Go forward |
| :reload | Reload page |
| :history | Show recently visited pages |
| :help | Show help |

The tool writes the page title, URL, extracted visible text, and numbered links into Excel. It does not embed a web view or display images/video. Chrome can execute JavaScript required by the website, but Excel shows only text.

## Organization

- text_browser/navigation.py: pure command parsing, URL and Google query detection
- text_browser/browser.py: CDP connection and DOM text/link extraction
- text_browser/excel_ui.py: formatted worksheet and bulk COM range updates
- text_browser/history.py: local, atomic JSON history
- text_browser/__main__.py: application coordinator and polling loop
- tests/: isolated unit tests

Test:

    python -m unittest discover -s tests -v

## Performance

Excel is polled every 450 ms, and page output is written in one rectangular COM assignment, not thousands of individual cell calls. Only one existing Chrome instance and one app-owned tab are used. Images, media, and web fonts are blocked for that tab. The app waits for DOM content, not network idle, so third-party advertising calls do not hold up the UI.

## Storage and security

History and logs are stored in %LOCALAPPDATA%\bs-in-excel\, outside this Git checkout.
The tool does not export cookies, credentials, browsing history from Chrome, or Chrome's user-data directory. The project uses Chrome's localhost-only CDP port and creates a dedicated tab.

Remote Debugging allows extensive browser control and should be enabled only for trusted local applications. The tool does not bypass CAPTCHA or restricted pages. Google search may show consent, anti-automation checks, or localized results. Excel is responsive while a page loads, but the Python worker processes one navigation command at a time.

## Troubleshooting

- Nothing appears in Excel: ensure an ordinary workbook is active (not PERSONAL.XLSB) before starting; check stderr.log under %LOCALAPPDATA%\bs-in-excel\.
- Chrome disconnected: verify Chrome Remote Debugging is enabled and DevToolsActivePort exists in the Chrome User Data directory. If Chrome shows "Allow remote debugging?", you must personally approve the trusted connection before relaunching the app.
- Web page incomplete: dynamic sites may need more time or interaction; the parser uses visible DOM text, not pixel rendering.
- To stop: end the specific Python process shown by start.ps1 or exit that process normally.
