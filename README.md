# Mapstalk

**Mapstalk** is a Python-based local-business prospecting tool that collects business information from Google Maps and enriches it with website checks, email extraction, and optional website-relevance and contact research.

It supports local-business research for the **Italian** and **US/English** markets. Run a single search from the PyQt5 desktop interface or command line, or process multiple cities from a CSV file.

> **Project status:** This documentation reflects the current repository as inspected. Google Maps markup, browser behaviour, and third-party services can change. Results and extraction completeness are not guaranteed.

## Contents

- [Features](#features)
- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Desktop application](#desktop-application)
- [Command-line usage](#command-line-usage)
- [Batch mode](#batch-mode)
- [Configuration and options](#configuration-and-options)
- [Output fields](#output-fields)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Responsible use](#responsible-use)

## Features

### Business discovery
- Search Google Maps using predefined business niches in Italian and English.
- Collect available business details: name, address, phone number, website, review count, and Maps URL.
- Apply minimum and maximum review filters.
- Limit results per search and configure maximum scroll attempts.
- Use city/state context and geocoding to focus searches geographically.

### Website and lead enrichment
- Check whether a listed website responds and record the HTTP status/check outcome.
- Extract publicly displayed email addresses from accessible business websites.
- Optionally analyse website relevance and classify businesses.
- Optionally search for an administrator/contact name using configured search and AI integrations.
- Filter selected large-company names and exclude social profiles, directories, and website-builder URLs where applicable.

### Execution and data handling
- PyQt5 desktop interface.
- Single-city CLI runner (run.py).
- Multi-city batch runner (run_batch.py).
- Incremental CSV output, duplicate checks against existing output, and batch resume support.
- Configurable logging and optional screenshots for debugging.
- English/US and Italian/Italy language-market settings.

## How it works

1. Expands selected niche labels into search phrases defined in src/niches.py.
2. Geocodes the target city where possible and builds Google Maps search URLs.
3. Uses Selenium with Chrome to inspect search results and collect available business details.
4. Applies filters, checks websites when enabled, and runs optional enrichment steps.
5. Appends collected records to a CSV file.

Google Maps may return different results depending on location, language, browser state, query, and changes to its interface. Mapstalk is not a complete or authoritative business directory.

## Requirements

- Python 3.10 or newer is recommended.
- Google Chrome installed locally.
- Internet connection.
- Python packages listed in requirements.txt.
- API credentials/configuration for optional integrations that require them.

The current requirements include Selenium, undetected-chromedriver, webdriver-manager, PyQt5, pandas, requests, geopy, Beautiful Soup, html2text, OpenAI-related packages, and other utilities. Compatibility can depend on the operating system, Python version, and installed Chrome version.

## Installation

Clone the repository and create a virtual environment:

~~~bash
git clone https://github.com/Kaildin/Mapstalk.git
cd Mapstalk
python -m venv .venv
~~~

Activate it:

**macOS / Linux**
~~~bash
source .venv/bin/activate
~~~

**Windows (PowerShell)**
~~~powershell
.\.venv\Scripts\Activate.ps1
~~~

Install dependencies:

~~~bash
python -m pip install --upgrade pip
pip install -r requirements.txt
~~~

Before using optional AI-based analysis or administrator search, inspect the relevant modules and configure any required credentials using the method expected by those modules. Never commit API keys or secrets to Git.

## Desktop application

Launch the desktop interface from the repository root:

~~~bash
python app.py
~~~

The interface provides controls for single searches and batch processing, including target city, niche selection, review filters, language, result/scroll limits, browser mode, website-check settings, logging, and debug screenshots. Available controls may vary by version.

Select the desired settings, choose an output CSV path, and start the run. The application streams process output in its terminal/log panel. Use the stop control to request that a running task stop.

## Command-line usage

### Single-city search

The CLI accepts **niche labels**, not arbitrary raw keywords. Labels must match entries in src/niches.py.

Example: search for plumbers in Austin, Texas.

~~~bash
python run.py \
  --comune "Austin" \
  --nicchie "Plumber" \
  --lang en \
  --min-reviews 1 \
  --max-reviews 100 \
  --max-results 20 \
  --output output/austin_plumbers.csv
~~~

Example: search for electricians in Rome.

~~~bash
python run.py \
  --comune "Roma" \
  --nicchie "Elettricista" \
  --lang it \
  --min-reviews 1 \
  --max-reviews 100 \
  --max-results 20 \
  --output output/elettricisti_roma.csv
~~~

### Selecting multiple niches

Pass one or more valid niche labels after --nicchie:

~~~bash
python run.py \
  --comune "Miami" \
  --nicchie "Plumber" "Landscaper" "Auto Detailer" \
  --lang en \
  --output output/miami_prospects.csv
~~~

The selected labels are expanded into phrases configured in src/niches.py. An unrecognised label will not produce search phrases.

### Useful CLI flags

| Flag | Default | Description |
|---|---:|---|
| --comune | Required | Target city or locality |
| --nicchie | Required | One or more labels defined in src/niches.py |
| --lang | en | Language/market setting: en or it |
| --min-reviews | 1 | Minimum review count |
| --max-reviews | 15 | Maximum review count |
| --max-results | 20 | Maximum results per search |
| --scroll-times | 30 | Maximum scroll attempts |
| --headless | Off | Run Chrome headlessly when supplied |
| --no-http-check | Off | Skip website availability checks |
| --no-email | Off | Disable email extraction |
| --no-relevance | Off | Disable website relevance analysis |
| --admin-search | Off | Enable optional administrator/contact search |
| --debug-screenshot | Off | Save screenshots for debugging |
| --log-level | INFO | DEBUG, INFO, WARNING, or ERROR |
| --output | output/debug_run.csv | Destination CSV path |

Inspect all options supported by your checkout:

~~~bash
python run.py --help
~~~

## Batch mode

Batch mode reads a CSV of cities and processes selected niches for each city. It supports English/US and Italian input schemas.

### US/English input

Create data/us_cities.csv:

~~~csv
city,state,population
Austin,TX,961855
Dallas,TX,1304379
Houston,TX,2304580
~~~

Run the batch:

~~~bash
python run_batch.py \
  --input data/us_cities.csv \
  --nicchie "Plumber" "Electrician" \
  --lang en \
  --output output/us_leads.csv
~~~

### Italian input

Create data/cities_it.csv:

~~~csv
comune,provincia,popolazione
Roma,RM,2750000
Milano,MI,1370000
Napoli,NA,910000
~~~

Run the batch:

~~~bash
python run_batch.py \
  --input data/cities_it.csv \
  --nicchie "Idraulico / Termoidraulico" "Elettricista" \
  --lang it \
  --output output/italian_leads.csv
~~~

### Batch options

| Flag | Default | Description |
|---|---:|---|
| --input | Required | Input CSV path |
| --nicchie | Required | One or more niche labels |
| --lang | en | en or it |
| --state | All | Filter by exact state/province value in the input |
| --min-reviews | 1 | Minimum review count |
| --max-reviews | 100 | Maximum review count |
| --max-results | Automatic | Override the per-search result limit |
| --scroll-times | 30 | Maximum scroll attempts |
| --headless | Off | Run Chrome headlessly when supplied |
| --no-http-check | Off | Skip website availability checks |
| --pause-min | 5.0 | Minimum pause between cities, in seconds |
| --pause-max | 15.0 | Maximum pause between cities, in seconds |
| --debug-screenshot | Off | Save screenshots for debugging |
| --log-level | INFO | Logging verbosity |
| --output | output/batch_results.csv | Destination CSV path |

When --max-results is omitted, the batch runner estimates a result limit from the population value and selected language. If the output file already exists, Mapstalk attempts to avoid reprocessing existing business/city records and completed city/keyword combinations. Resume behaviour depends on the existing CSV contents and format.

Inspect the exact options for your checkout:

~~~bash
python run_batch.py --help
~~~

## Configuration and options

### Languages and niche labels

- en sets English/US-oriented Google Maps language and region parameters.
- it sets Italian/Italy-oriented parameters.
- Supported niche labels and search phrases are defined in src/niches.py.

Use the exact labels in that file. Keep the labels displayed in the desktop interface and accepted by the CLI in sync when adding or changing niches.

### Optional enrichment

- **Email extraction** reads publicly accessible website content and filters candidate addresses.
- **Website relevance analysis** analyses a business website and returns fields such as relevance, category, and confidence.
- **Administrator/contact search** uses web-search results and an AI extraction integration when enabled.

These steps can increase runtime and may depend on external services, network access, and valid credentials. Check the relevant modules for provider configuration and current behaviour. Treat AI-generated classifications and contact names as suggestions that require verification.

### Debugging

Enable --debug-screenshot to save browser screenshots under the debug output directory. Use --log-level DEBUG for more detailed diagnostics. Debug files may contain business or browser information; review them before sharing.

## Output fields

CSV output contains core business fields and, when enrichment is enabled, additional fields.

| Field | Description |
|---|---|
| city | City used for the search |
| state | State/province supplied to the search |
| keyword | Search phrase associated with the result |
| nome | Business name |
| indirizzo | Extracted address |
| telefono | Extracted phone number |
| sito_web | Website URL, when available |
| ha_sito_web | Website check outcome |
| website_status_code | HTTP status code, when available |
| website_check_reason | Reason/status returned by the website checker |
| num_recensioni | Google Maps review count |
| maps_url | Google Maps listing/search URL |
| email | Candidate email addresses found on the website |
| linkedin | Optional enrichment field; may be empty |
| pertinenza | Website relevance result, when analysis runs |
| categoria | Analysed business category |
| categoria_id | Category identifier when available |
| confidenza_analisi | Analysis confidence value when available |
| contatto | Optional administrator/contact name |
| industry | Industry/niche context used for enrichment |

Not every field will be populated for every record. The exact columns written depend on which enrichment options are enabled and on the output path's existing schema. Use a new output filename when changing between basic and enriched output modes.

## Project structure

~~~text
Mapstalk/
├── app.py                   # PyQt5 desktop interface
├── run.py                   # Single-city CLI runner
├── run_batch.py             # Multi-city CSV batch runner
├── requirements.txt         # Python dependencies
├── data/                    # Niche/category data and input datasets
└── src/
    ├── scraper.py           # Search orchestration, filters, enrichment, CSV output
    ├── selenium_scraper.py  # Selenium-based Google Maps extraction
    ├── driver_utils.py      # Browser setup and cleanup utilities
    ├── niches.py            # Niche labels and search phrases
    ├── website_checker.py   # Website and domain checks
    ├── text_utils.py        # Text cleaning helpers
    ├── email_utils.py       # Email filtering and website relevance analysis
    ├── search_utils.py      # Search and optional contact extraction helpers
    └── category_manager.py  # Category data loading/validation
~~~

The repository may contain additional helper modules and data files beyond this overview. Refer to the checked-out source for the authoritative implementation.

## Troubleshooting

### Chrome or Selenium fails to start
- Confirm that Google Chrome is installed and can be launched.
- Update dependencies in the virtual environment.
- Check compatibility among Python, Chrome, Selenium, and undetected-chromedriver.
- Try running without headless mode to inspect browser behaviour.

### Few or no results are returned
- Verify the city spelling and niche label.
- Try a different review range or a higher --max-results value.
- Enable debug screenshots and DEBUG logging.
- Google Maps results can vary and may be limited by its interface or access controls.

### Website checks or enrichment fields are empty
- Some businesses do not list a website or email publicly.
- Websites may block automated requests, redirect, or time out.
- Optional analysis and contact research may require credentials or third-party services.
- Validate extracted contact details manually before using them.

### Batch does not process a city
- Check that the input CSV uses the correct headers for the selected language.
- Check --state against the exact state/province values in the file.
- Review the existing output CSV: resume logic may skip previously processed records or combinations.

## Responsible use

Use Mapstalk only in ways that comply with applicable laws, privacy and data-protection requirements, and the terms and access restrictions of the services you use. Collect only information you have a legitimate reason to process, respect opt-outs and deletion requests, and avoid excessive request rates. Public accessibility does not automatically mean information is unrestricted for every use case.

This project is provided as-is, without guarantees of accuracy, completeness, availability, or fitness for a particular purpose. You are responsible for validating results and for how collected data is used.

---

**Repository:** [Kaildin/Mapstalk](https://github.com/Kaildin/Mapstalk)
