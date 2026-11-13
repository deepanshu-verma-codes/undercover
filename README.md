# UnderCover: Autonomous Travel Insurance Claims Platform

![UnderCover](assets/undercover.jpg)

## About the Project

**UnderCover** is an enterprise-grade AI-powered claims platform built for travel insurance operations. It combines autonomous AI decision agents with human-in-the-loop workflows to process, review, and decide claims with speed, security, and precision.

Claims handlers manage an interactive queue where claims are audited by the UnderCover Agent, evaluated against policy rules, checked for adversarial manipulation, and escalated to supervisors when necessary.

### Key Highlights

- **Autonomous Agent Decision Loop:** A LangChain-powered reasoning agent equipped with domain tools to inspect policy wordings, evaluate covered perils, and recommend decisions (Approve, Decline, or Refer) with calculated payouts.
- **Enterprise Security & Guardrails:** Pre-execution prompt injection defense that detects adversarial system prompt override attempts (such as malicious customer stories like `CLM-1901`), alongside input sanitization and financial PII masking.
- **Human-in-the-Loop & RBAC:** Built-in safeguards requiring supervisor-level sign-offs for high-value payouts (> $1,000) and complex referrals before payment processing.
- **Claim Ingestion & Bulk Upload:** Supports both manual single-claim submission with immediate agent audit and high-throughput bulk CSV ingestion with downloadable templates.
- **Interactive Handler Dashboard:** A modern React + TypeScript dashboard featuring real-time queue polling, status filtering, execution stream modals, and claim detail breakdowns.
- **Full-Stack Architecture & Verification:** Built on a FastAPI backend, SQLite persistence, and validated by comprehensive unit tests and automated Playwright end-to-end (E2E) suites.

---

## Original Repository & Course Reference

This project was built during Ed Donner's course, **"AI FDE: The Forward Deployed Engineer & Agentic AI Architect"**.

- **Original Course Repository:** [github.com/ed-donner/undercover](https://github.com/ed-donner/undercover)

---

## Author & Project Contributions

**Built by Deepanshu Verma**

### My Background & The Evolution to Agentic AI
Prior to this project, my work primarily centered around traditional RAG (Retrieval-Augmented Generation) pipelines and foundational LLM applications. While standard RAG is powerful for informational queries, real-world enterprise operations require autonomous decision-making, resilience, deterministic guardrails, and human oversight.

Through this project and Ed Donner's **AI FDE: Forward Deployed Engineer & Agentic AI Architect** curriculum, I expanded my focus into next-generation agentic systems:

- **LangChain & Harness Engineering:** Designing autonomous agent reasoning harnesses equipped with domain tools (policy lookup, decision logic, payout rules) instead of brittle prompt chains.
- **LangGraph & Durable State:** Orchestrating cyclical agent workflows, checkpointing, and human-in-the-loop escalation paths for high-value claims.
- **Evals & Observability:** Benchmarking agent accuracy against human handler ground-truth labels and tracking operational metrics.
- **Agent Swarms & Multi-Agent Systems:** Structuring dispatcher swarms for parallel claim resolution and high-volume workloads.
- **Enterprise Security & Guardrails:** Implementing pre-execution prompt injection detection (defending against adversarial inputs like `CLM-1901`), financial PII masking, and API key authentication.
- **Production Full-Stack Architecture:** Integrating an asynchronous FastAPI backend, a real-time React + TypeScript claims dashboard, automated bulk CSV ingestion, and automated Playwright E2E test suites.

This repository reflects my hands-on implementation of the core claims platform, autonomous agent decision loop, security middleware, and interactive handler dashboard.
