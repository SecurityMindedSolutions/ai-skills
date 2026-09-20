# Carved out for investigation

Raw canonical rows for every IP whose verdict was attention, malicious, unclear, one JSONL per IP, time-sorted, every field the source supplied. Attention rows first.

| IP | Category | Score | Band | Attention | Requests | Signals | Code signals | File |
|---|---|---:|---|---|---:|---|---|---|
| 194.26.29.4 | malicious | 87.7 | Attack | YES | 60 | exploit_payloads, app_aware, automated, enumeration | payloads, waf_denied, enumeration | `investigate/194.26.29.4.jsonl` |
| 2a02:4780:1:1::1 | malicious | 86.7 | Attack | YES | 24 | exploit_payloads, app_aware, automated | ua_script, payloads | `investigate/2a02_4780_1_1__1.jsonl` |
| 176.65.144.71 | malicious | 86.4 | Attack | YES | 30 | exploit_payloads, app_aware, automated | ua_script, payloads | `investigate/176.65.144.71.jsonl` |
| 23.129.64.1 | malicious | 85.0 | Attack | YES | 140 | exploit_payloads, automated, scanner_tool, app_aware, credential_attack | ua_scanner, payloads, waf_denied, burst | `investigate/23.129.64.1.jsonl` |
| 198.51.100.50 | malicious | 80.1 | Attack | YES | 200 | credential_attack, app_aware, automated | ua_script, waf_throttled, auth_volume | `investigate/198.51.100.50.jsonl` |
| 103.99.1.7 | malicious | 76.6 | Attack | YES | 300 | automated, app_aware, enumeration | ua_script, enumeration | `investigate/103.99.1.7.jsonl` |
| 141.98.11.5 | malicious | 76.0 | Attack | YES | 20 | exploit_payloads, generic_probing, app_aware, automated | probe_paths, payloads, waf_denied | `investigate/141.98.11.5.jsonl` |
| 5.188.86.2 | malicious | 73.8 | Concerning | YES | 420 | credential_attack, app_aware, automated | waf_throttled, auth_volume, burst | `investigate/5.188.86.2.jsonl` |
| 89.248.165.2 | malicious | 68.8 | Concerning | YES | 46 | app_aware, enumeration | enumeration | `investigate/89.248.165.2.jsonl` |
| 198.18.0.1 | unclear | 7.0 | Benign |  | 1 | app_aware |  | `investigate/198.18.0.1.jsonl` |
