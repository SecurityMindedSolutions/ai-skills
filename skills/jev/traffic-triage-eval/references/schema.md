# Canonical request-event schema

This is the contract between whoever retrieves the logs and this skill. One
JSON object per HTTP request, one per line (JSONL). A JSON array or a CSV
with these column names is also accepted. Field names are exact; unknown
fields are ignored, not rejected. `scripts/schema.py` is the executable
version of this page and wins if they disagree.

The skill does not know or care where the rows came from. GCP load balancer,
AWS ALB, AWS WAF, CloudFront, nginx, an MCP server, a SIEM export: the
retrieving agent maps its source to these names however it likes.

## Required

| Field | Type | Meaning |
|---|---|---|
| `ts` | string or number | Request time. ISO 8601 with a zone (`2026-09-18T14:03:07.123Z`, `...+00:00`), or epoch seconds or milliseconds. A naive ISO string is taken as UTC. |
| `ip` | string | The client IP as the edge saw it: the real client, not the load balancer, CDN or proxy hop. IPv4 or IPv6. |
| `method` | string | HTTP method. |
| `path` | string | URL path only: no scheme, host or query. If you only have the full URL, send it as `url` instead and the validator splits it into `host`, `path` and `query`. |

## Recommended

Each of these adds a signal. The validator prints a coverage table so you
can see which signals the run will and will not have.

| Field | Type | Meaning |
|---|---|---|
| `status` | integer | HTTP response status. `0` if the edge closed the connection before a response. Omit it when the source does not have it: most WAF logs record the verdict, not the backend's answer. Without it the 404-rate and "mostly successful / mostly rejected" signals are absent and the profile says so; the WAF verdicts, paths, User-Agents and pacing still carry the judgment. |
| `host` | string | Host header or SNI as requested. Keep raw-IP hosts and hostnames that are not yours; they are a signal, not noise. |
| `query` | string | Raw query string without the leading `?`. Exploit payloads live here. |
| `ua` | string | User-Agent header. |
| `referer` | string | Referer header. Browsers send it, scripts do not. |
| `waf_action` | string | `allow`, `deny`, `throttle`, `count`, `challenge` or `none`. Aliases are normalized: `ACCEPT`, `BLOCK`, `ALLOW`, `COUNT`, `CAPTCHA`, `RATE_LIMIT`. |
| `waf_rule` | string | The rule or policy that produced `waf_action`. Free text. |
| `waf_labels` | list of strings | Labels the WAF attached to the request (AWS WAF `labels[].name`, e.g. `awswaf:managed:aws:core-rule-set:SQLi_QueryArguments`, `awswaf:managed:aws:bot-control:bot:name:googlebot`). A single space- or comma-separated string is accepted too. Attack-signature, bot-control and IP-reputation labels each become a code signal. |
| `asn` | integer | Client ASN if the edge records it. |
| `country` | string | ISO 3166 two-letter country code if the edge records it. |
| `ja3` / `ja4` | string | TLS fingerprints if the edge records them. |
| `bytes_in` / `bytes_out` | integer | Request and response bytes. |
| `latency_ms` | number | Backend or total latency in milliseconds. |
| `protocol` | string | `HTTP/1.1`, `HTTP/2`, ... |
| `target` | string | Backend, target group or function the LB routed to. |
| `source` | string | `gclb`, `alb`, `awswaf`, `cloudfront`, `nginx` or `other`. Informational. |

## Example line

```json
{"ts":"2026-09-18T14:03:07Z","ip":"203.0.113.10","method":"GET","host":"app.example.com","path":"/api/v1/auth/user_info","query":"","status":200,"ua":"Mozilla/5.0 ...","referer":"https://app.example.com/","waf_action":"allow","asn":7922,"ja4":"t13d1516h2_8daaf6152771_02713d6af862","bytes_in":412,"bytes_out":1180,"latency_ms":38.5,"protocol":"HTTP/2","target":"fn-prod-auth-backend","source":"gclb"}
```

## Where the fields usually come from

Hints for the mapping, not instructions for retrieval. Use whatever tool
you have (a CLI, an MCP server, Athena, a SIEM export, a log sink).

| Field | GCP HTTP(S) LB (`resource.type="http_load_balancer"`) | AWS ALB access log | AWS WAF log |
|---|---|---|---|
| `ts` | `timestamp` | column 2 `time` | `timestamp` (epoch milliseconds; accepted as-is) |
| `ip` | `jsonPayload.remoteIp` (or `httpRequest.remoteIp`) | `client:port` (strip the port) | `httpRequest.clientIp` |
| `method` | `httpRequest.requestMethod` | `request` field, first token | `httpRequest.httpMethod` |
| `host` / `path` / `query` | split `httpRequest.requestUrl` (or send it as `url`) | `request` field, second token (send as `url`) | `Host` in `httpRequest.headers[]`, `httpRequest.uri`, `httpRequest.args` |
| `status` | `httpRequest.status` | `elb_status_code` (or `target_status_code`) | not logged. `responseCodeSent` is set only for a custom response. Reasonable inference: `BLOCK` -> 403 (the default), `CAPTCHA`/`Challenge` terminating -> 405, `ALLOW` -> omit. Or join to the ALB / CloudFront log on `requestId` / trace id |
| `ua` | `httpRequest.userAgent` | `user_agent` | `User-Agent` in `httpRequest.headers[]` |
| `referer` | `httpRequest.referer` | not logged | `Referer` in `httpRequest.headers[]` |
| `waf_action` | `jsonPayload.enforcedSecurityPolicy.outcome` (`ACCEPT`/`DENY`); `THROTTLE` with `rateLimitAction.outcome` ending `EXCEED` means `throttle` | `actions_executed` contains `waf` = deny | `action`: `BLOCK` -> `deny`, except `terminatingRuleType == "RATE_BASED"` -> `throttle`; `ALLOW` -> `allow`, or `count` when `nonTerminatingMatchingRules[]` has a `COUNT` match; `CAPTCHA` / `CHALLENGE` -> `challenge` |
| `waf_rule` | `enforcedSecurityPolicy.name` + `priority` | not logged | `terminatingRuleId`; for a managed group also `ruleGroupList[].terminatingRule.ruleId`; for a count match `nonTerminatingMatchingRules[].ruleId` |
| `waf_labels` | not available | not available | `labels[].name` (first 100 are logged) |
| `asn` | `jsonPayload.securityPolicyRequestData.remoteIpInfo.asn` | not logged | not logged |
| `country` | `securityPolicyRequestData.remoteIpInfo.regionCode` | not logged | `httpRequest.country` (`-` when unknown; omit) |
| `ja3` / `ja4` | `securityPolicyRequestData.tlsJa3Fingerprint` / `tlsJa4Fingerprint` | not logged | `ja3Fingerprint` / `ja4Fingerprint` (CloudFront and ALB sources only) |
| `bytes_in` / `bytes_out` | `httpRequest.requestSize` / `responseSize` | `received_bytes` / `sent_bytes` | not logged (`requestBodySize` exists on newer records, body only) |
| `latency_ms` | `httpRequest.latency` (`"0.365s"` -> 365) | `request_processing_time + target_processing_time + response_processing_time` (seconds) | not logged |
| `protocol` | `httpRequest.protocol` | `request` field, third token | `httpRequest.httpVersion` |
| `target` | `resource.labels.backend_service_name` | `target_group_arn` | `httpSourceName` + `httpSourceId` (`ALB`, `CF`, `APIGW`, `APPSYNC`, `COGNITOIDP`, `APPRUNNER`, `VERIFIED_ACCESS`) |

GCLB tips: `enforcedSecurityPolicy` is only present on backend services with
request logging enabled; a missing field means `none`, not `allow`. The
origin endpoints behind Cloudflare log Cloudflare's IP as the client, so
group those separately or drop them.

AWS WAF tips: a regional (ALB / API Gateway) web ACL and a CloudFront web ACL
log the same record shape; only `httpSourceName` differs. A WAF-only export
has no `status` for allowed requests, and that is fine: the profile says so
and the verdicts, labels, paths, User-Agents and pacing carry the judgment.
Do send `labels`: the managed rule groups (core rule set, known bad inputs,
bot control, IP reputation, anonymous IP list) label matches even in COUNT
mode, so they surface attack signatures and bot identities the terminating
action alone hides. An ALB log and a WAF log for the same request are two
rows in two places; send one, or join them on `requestId` (the ALB trace
id) in Athena and emit one row with both sets of columns. With Athena,
`SELECT ... AS ts, ... AS ip` straight into these names and export as JSON
lines or CSV.

## Size guidance

The skill aggregates per IP before anything reaches Jev, so raw volume is a
local CPU cost, not an API cost. A million rows is fine. What matters per IP
is the sample lists (top paths, error paths, payload examples); those are
trimmed to the token budget automatically.
