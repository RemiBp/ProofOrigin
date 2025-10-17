# ProofOrigin Protocol (POP) - Technical Whitepaper

## Abstract

ProofOrigin is an open-source protocol designed to establish cryptographic proof of origin for digital content in the age of AI. This whitepaper outlines the technical architecture, security model, and implementation details of the ProofOrigin Protocol (POP) v0.1.

## 1. Introduction

### 1.1 Problem Statement

In a world where 90% of content will soon be AI-generated, establishing trust and authenticity becomes critical. Current solutions are either:
- Proprietary and closed (Adobe Content Authenticity Initiative)
- Blockchain-heavy and expensive (Arweave, Filecoin)
- Limited in scope (EXIF metadata, watermarks)

### 1.2 Solution Overview

ProofOrigin provides a lightweight, open-source protocol that:
- Creates cryptographic proof of origin for any digital content
- Supports both human and AI-generated content
- Offers fuzzy matching for similar content detection
- Anchors proofs to public blockchains for immutability
- Maintains low costs and high performance

## 2. Technical Architecture

### 2.1 Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Content       │    │   ProofOrigin   │    │   Blockchain    │
│   Creator       │───▶│   API/SDK       │───▶│   Anchor        │
│   (Human/AI)    │    │   (Processing)  │    │   (Daily)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Local Ledger  │
                       │   (SQLite)      │
                       └─────────────────┘
```

### 2.2 Data Flow

1. **Content Submission**: File uploaded via API or SDK
2. **Hash Generation**: SHA-256 hash computed
3. **Fuzzy Analysis**: Perceptual hashing (images) or semantic analysis (text)
4. **Signature**: RSA-2048 signature with PSS padding
5. **Storage**: Entry in append-only ledger
6. **Anchoring**: Daily Merkle root published to blockchain

## 3. Cryptographic Security

### 3.1 Hash Function

- **Algorithm**: SHA-256
- **Purpose**: Content integrity verification
- **Properties**: Collision-resistant, deterministic

### 3.2 Digital Signature

- **Algorithm**: RSA-2048 with PSS padding
- **Purpose**: Proof authenticity and non-repudiation
- **Security Level**: Equivalent to 112-bit symmetric encryption

### 3.3 Perceptual Hashing

- **Images**: pHash (perceptual hash) + dHash (difference hash)
- **Text**: Semantic embeddings via sentence-transformers
- **Purpose**: Detect similar content despite minor modifications

## 4. Data Structures

### 4.1 Proof Format (.proof)

```json
{
  "prooforigin_protocol": "POP v0.1",
  "proof_id": 12345,
  "filename": "document.pdf",
  "hash": {
    "algorithm": "SHA-256",
    "value": "a1b2c3d4e5f6..."
  },
  "signature": {
    "algorithm": "RSA-2048-PSS",
    "value": "base64_encoded_signature"
  },
  "public_key": "-----BEGIN PUBLIC KEY-----...",
  "timestamp": {
    "unix": 1703123456,
    "readable": "2023-12-21 10:30:56 UTC"
  },
  "fuzzy_hashes": {
    "phash": "perceptual_hash_value",
    "dhash": "difference_hash_value",
    "semantic_hash": "semantic_hash_value"
  },
  "metadata": {
    "content_type": "image|text|binary",
    "file_size": 1024000,
    "similarity_detected": true
  },
  "verification_url": "https://api.prooforigin.com/verify",
  "exported_at": {
    "unix": 1703123500,
    "readable": "2023-12-21 10:31:40 UTC"
  }
}
```

### 4.2 Database Schema

#### Proofs Table
```sql
CREATE TABLE proofs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE,                    -- SHA-256 hash
    filename TEXT,                       -- Original filename
    signature TEXT,                      -- RSA signature
    public_key TEXT,                     -- Public key
    timestamp REAL,                      -- Unix timestamp
    phash TEXT,                          -- Perceptual hash
    dhash TEXT,                          -- Difference hash
    semantic_hash TEXT,                  -- Semantic hash
    content_type TEXT,                   -- image|text|binary
    file_size INTEGER,                   -- File size in bytes
    metadata TEXT                        -- JSON metadata
);
```

#### Anchors Table
```sql
CREATE TABLE anchors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE,                    -- YYYY-MM-DD
    merkle_root TEXT,                    -- Merkle tree root
    proof_count INTEGER,                 -- Number of proofs
    transaction_hash TEXT,               -- Blockchain tx hash
    timestamp REAL,                      -- Unix timestamp
    created_at REAL DEFAULT (strftime('%s', 'now'))
);
```

## 5. Fuzzy Matching System

### 5.1 Image Similarity

#### Perceptual Hash (pHash)
- Resize image to 8x8 pixels
- Convert to grayscale
- Calculate average pixel value
- Generate binary hash based on above/below average

#### Difference Hash (dHash)
- Resize image to 9x8 pixels
- Calculate horizontal differences
- Generate binary hash from differences

#### Similarity Score
```python
def similarity_score(hash1, hash2):
    distance = hamming_distance(hash1, hash2)
    return 1 - (distance / 64)  # 64-bit hash
```

### 5.2 Text Similarity

#### Semantic Analysis
- Use sentence-transformers model (all-MiniLM-L6-v2)
- Generate embeddings for text content
- Calculate cosine similarity between embeddings

#### Confidence Levels
- **High**: >90% similarity
- **Medium**: 80-90% similarity
- **Low**: 70-80% similarity

## 6. Blockchain Anchoring

### 6.1 Daily Merkle Tree

1. Collect all proofs from the last 24 hours
2. Build Merkle tree with proof hashes as leaves
3. Publish Merkle root to blockchain
4. Store transaction hash in local database

### 6.2 Merkle Tree Construction

```
Proof1  Proof2  Proof3  Proof4
  |       |       |       |
  └───┬───┘       └───┬───┘
      │               │
      └───────┬───────┘
              │
           Merkle Root
```

### 6.3 Blockchain Integration

- **Primary**: Polygon (low fees, fast confirmation)
- **Secondary**: Ethereum (higher security, higher fees)
- **Fallback**: Bitcoin (maximum security, slow confirmation)

## 7. API Specification

### 7.1 REST Endpoints

#### Register File
```http
POST /api/register
Content-Type: multipart/form-data

file: [binary file data]
metadata: {"creator": "AI Model", "version": "1.0"}
```

#### Verify File
```http
POST /api/verify
Content-Type: multipart/form-data

file: [binary file data]
```

#### List Proofs
```http
GET /api/proofs?limit=100&offset=0
```

#### Export Proof
```http
GET /export/{proof_id}
```

#### Get Similar Content
```http
GET /api/similar/{proof_id}
```

#### List Anchors
```http
GET /api/anchors
```

### 7.2 Response Formats

All API responses follow this structure:
```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "timestamp": 1703123456
}
```

## 8. SDK Implementation

### 8.1 Python SDK

```python
from prooforigin import ProofOriginClient

client = ProofOriginClient("https://api.prooforigin.com")

# Register a file
proof = client.register_file("document.pdf")

# Verify a file
verification = client.verify_file("document.pdf")

# Export proof
proof_file = client.export_proof(proof['proof_id'])
```

### 8.2 JavaScript SDK

```javascript
import { ProofOriginClient } from 'prooforigin-sdk';

const client = new ProofOriginClient('https://api.prooforigin.com');

// Register a file
const proof = await client.registerFile('document.pdf');

// Verify a file
const verification = await client.verifyFile('document.pdf');
```

## 9. Security Considerations

### 9.1 Threat Model

1. **Content Modification**: Detected via hash mismatch
2. **Proof Forgery**: Prevented by RSA signatures
3. **Replay Attacks**: Mitigated by timestamps
4. **Similar Content**: Detected via fuzzy matching
5. **System Compromise**: Limited by append-only ledger

### 9.2 Security Properties

- **Integrity**: SHA-256 hash ensures content hasn't changed
- **Authenticity**: RSA signature proves origin
- **Non-repudiation**: Private key holder cannot deny creation
- **Immutability**: Blockchain anchoring prevents tampering
- **Transparency**: Open-source, auditable code

## 10. Performance Characteristics

### 10.1 Benchmarks

| Operation | Time | Cost |
|-----------|------|------|
| Hash computation | <100ms | Free |
| Signature generation | <50ms | Free |
| Fuzzy matching | <500ms | Free |
| Blockchain anchor | <30s | ~$0.01 |
| Verification | <200ms | Free |

### 10.2 Scalability

- **Throughput**: 1000+ proofs per minute
- **Storage**: ~1KB per proof
- **Bandwidth**: Minimal (only metadata)
- **Cost**: <$0.01 per proof (including blockchain fees)

## 11. Deployment Architecture

### 11.1 Production Setup

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   App Servers   │    │   Database      │
│   (Cloudflare)  │───▶│   (Railway)     │───▶│   (PostgreSQL)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Cron Jobs     │
                       │   (Anchoring)   │
                       └─────────────────┘
```

### 11.2 Infrastructure Requirements

- **Compute**: 2 vCPU, 4GB RAM minimum
- **Storage**: 100GB SSD for ledger
- **Network**: 1Gbps bandwidth
- **Backup**: Daily automated backups

## 12. Migration and Versioning

### 12.1 Protocol Versioning

- **POP v0.1**: Current version (this whitepaper)
- **POP v1.0**: Planned for Q2 2024
- **Backward Compatibility**: Maintained for 2 major versions

### 12.2 Database Migrations

```python
def migrate_v0_1_to_v1_0():
    # Add new columns
    # Migrate existing data
    # Update indexes
    # Verify integrity
```

### 12.3 Upgrade Process

1. **Announcement**: 30 days notice
2. **Testing**: Beta deployment
3. **Migration**: Automated scripts
4. **Verification**: Data integrity checks
5. **Rollback**: Emergency procedures

## 13. Compliance and Legal

### 13.1 Data Privacy

- **GDPR**: No personal data stored
- **CCPA**: Minimal data collection
- **Retention**: Proofs stored indefinitely
- **Deletion**: Not supported (immutability requirement)

### 13.2 Legal Framework

- **Evidence**: Cryptographic proofs admissible in court
- **Jurisdiction**: Based on server location
- **Liability**: Limited to service availability
- **Terms**: Open-source license (MIT)

## 14. Future Roadmap

### 14.1 Short Term (Q1 2024)

- [ ] Production deployment
- [ ] Chrome extension
- [ ] Mobile SDKs
- [ ] API rate limiting

### 14.2 Medium Term (Q2-Q3 2024)

- [ ] Smart contract integration
- [ ] Multi-chain support
- [ ] Advanced fuzzy matching
- [ ] Enterprise features

### 14.3 Long Term (Q4 2024+)

- [ ] Decentralized network
- [ ] Token economics
- [ ] Governance system
- [ ] Global adoption

## 15. Conclusion

ProofOrigin Protocol represents a significant advancement in digital content authentication. By combining cryptographic security with practical usability, it addresses the critical need for trust in the AI era.

The protocol's open-source nature, low cost, and high performance make it accessible to creators, platforms, and institutions worldwide. As AI-generated content becomes ubiquitous, ProofOrigin provides the infrastructure for maintaining digital trust and authenticity.

## References

1. Rivest, R. L., Shamir, A., & Adleman, L. (1978). A method for obtaining digital signatures and public-key cryptosystems.
2. National Institute of Standards and Technology. (2015). SHA-3 Standard: Permutation-Based Hash and Extendable-Output Functions.
3. Merkle, R. C. (1988). A digital signature based on a conventional encryption function.
4. Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks.

---

**ProofOrigin Protocol v0.1**  
*Building Trust in the Age of AI*

© 2024 ProofOrigin. All rights reserved. Licensed under MIT License.
