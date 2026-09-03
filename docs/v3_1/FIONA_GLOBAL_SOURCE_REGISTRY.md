# Fiona Global Source Registry

- Version: V3.1-alpha.2
- Status: Implemented / Shadow Candidate
- Owner: Fiona Engineering
- Updated: 2026-09-03

## 1. Purpose

`config/sources.json` is the single authoritative registry for legacy and Gate 2
sources. `app/wilson.py` no longer keeps a competing active RSS list. A source
being registered does not imply that it is healthy or production-qualified;
runtime health is measured separately.

## 2. Metadata Contract

Every source records a stable ID, publisher, publisher region, default event
region, language, tier, independence group, source type, markets, categories,
retrieval method, endpoint, status, legacy/shadow eligibility, authority
classification, expected update frequency, provenance capability, and access
notes. Unknown metadata remains explicit.

## 3. Source Inventory

| Source ID | Source | Default event region | Language | Tier | Independence group | Content | Status | Runtime role | Known limitation |
|---|---|---|---|---:|---|---|---|---|---|
| `fed_press` | Federal Reserve | US_EU | en-US | 1 | federal_reserve | Macro policy | Active | Legacy + Shadow | Event-driven feed |
| `yahoo_us` | Yahoo Finance US | US_EU | en-US | 2 | yahoo_finance | US markets | Active | Legacy + Shadow | Availability can vary |
| `cnbc_markets` | CNBC Markets | US_EU | en-US | 2 | nbcuniversal_cnbc | Markets / macro | Active | Legacy + Shadow | Publisher feed, not primary evidence |
| `yahoo_china` | Yahoo China proxy | GREATER_CHINA | en-US | 2 | yahoo_finance | China markets | Active | Legacy + Shadow | Proxy rather than official policy source |
| `scmp_china_economy` | SCMP China Economy | GREATER_CHINA | en-HK | 2 | scmp_group | China economy | Active | Legacy + Shadow | Publisher feed, not primary evidence |
| `cointelegraph` | Cointelegraph | GLOBAL | en-US | 3 | cointelegraph | Crypto / RWA | Active | Legacy + Shadow | Specialist evidence requires confirmation |
| `decrypt` | Decrypt | GLOBAL | en-US | 3 | decrypt_media | Crypto / RWA | Active | Legacy + Shadow | Specialist evidence requires confirmation |
| `sec_press` | U.S. SEC | US_EU | en-US | 1 | us_sec | Regulation | Active | Shadow only | Bounded official feed access |
| `ecb_press` | European Central Bank | US_EU | en-GB | 1 | european_central_bank | Macro policy | Active, health pending | Shadow only | Local validator saw TLS-chain failure; endpoint is publicly reachable |
| `boe_news` | Bank of England | US_EU | en-GB | 1 | bank_of_england | Macro policy | Active | Shadow only | Broad news feed requires materiality filtering |
| `hkma_press` | Hong Kong Monetary Authority | GREATER_CHINA | en-HK | 1 | hong_kong_monetary_authority | Macro / regulation | Active | Shadow only | JSON API often has title-only records |
| `hkex_news` | HKEX | GREATER_CHINA | en-HK | 1 | hkex | Market / regulation | Active | Shadow only | Broad exchange releases require filtering |
| `boj_whatsnew` | Bank of Japan | REST_OF_WORLD | en-JP | 1 | bank_of_japan | Macro policy | Active | Shadow only | Broad update feed requires freshness filtering |
| `rbi_press` | Reserve Bank of India | REST_OF_WORLD | en-IN | 1 | reserve_bank_of_india | Macro / regulation | Active | Shadow only | Low item count is normal between releases |
| `bok_press` | Bank of Korea | REST_OF_WORLD | en-KR | 1 | bank_of_korea | Macro policy | Active | Shadow only | Broad release history is capped per evaluation |
| `rba_media` | Reserve Bank of Australia | REST_OF_WORLD | en-AU | 1 | reserve_bank_of_australia | Macro policy | APPROVED GAP / disabled | None | Access controls rejected the bounded collector |

## 4. Approved Gaps

Not integrated in this wave: U.S. Treasury, BLS, BEA, CFTC, Eurostat and other
European regulators, PBOC/NBS/CSRC, Taiwan central bank/TWSE, Japan Ministry of
Finance, RBA, and MAS. Reasons are recorded in `config/sources.json`. Fiona does
not bypass authentication, paywalls, robots/access controls, or TLS validation.

## 5. Validation Snapshot

The local production-safe run on 2026-09-03 loaded 16 registry records, retained
the exact seven legacy sources, and evaluated 15 Shadow-eligible adapters. One
active adapter (ECB) reported a local TLS verification health error; this is a
degraded source, not “no news.” RBA remained disabled. Production health must be
measured again inside Railway.

## 6. Editorial Semantics

- Regional allocation uses `event_region`, never publisher headquarters alone.
- `source_count` and `independent_source_count` are separate.
- Multiple feeds in the same syndication/ownership group do not create multiple
  confirmations.
- Tier describes evidence authority, not automatic truth.
- Original language, title, URL, timestamps, and source identity remain in
  provenance; normalized English does not overwrite them.
