# Security policy

This repository is a reference implementation and the bundled corpus is fictional. Do not expose it to confidential enterprise documents without adding organizational identity, authorization, tenant isolation, encryption, malware scanning, audit retention, and deletion controls.

## Reporting a vulnerability

Do not open a public issue containing exploit details or sensitive data. Report vulnerabilities through the private security channel configured by the deploying organization. Include the affected version, reproduction steps, impact, and any suggested mitigation.

## Supported configuration

Keep Python, Node.js, containers, model-provider SDKs, parsing libraries, and vector-database dependencies patched. Production deployments should pin image digests, scan software bills of materials, run as non-root, terminate TLS at a trusted gateway, and retrieve secrets from a secrets manager.

## RAG-specific threats

Retrieved documents are untrusted data. Instructions found in a document must never override system policy. Enforce collection-level authorization before retrieval; post-filtering a passage after generation is too late. Treat citations as provenance pointers, not proof that source content itself is safe or correct.

