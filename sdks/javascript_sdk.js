const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const fetch = require("node-fetch");

class ProofOriginClient {
  constructor({ baseUrl, apiKey }) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
    this.headers = {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    };
  }

  async _request(path, init = {}) {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: { ...this.headers, ...(init.headers || {}) },
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`HTTP ${response.status}: ${detail}`);
    }
    const text = await response.text();
    return text ? JSON.parse(text) : {};
  }

  async generateProof(filePath, { keyPassword, metadata } = {}) {
    const content = fs.readFileSync(filePath);
    const payload = {
      content: content.toString("base64"),
      filename: path.basename(filePath),
      mime_type: "application/octet-stream",
      metadata,
      key_password: keyPassword,
    };
    return this._request("/api/v1/proof", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async verifyHash(fileHash) {
    return this._request(`/api/v1/verify/${fileHash}`);
  }

  async getProof(proofId) {
    return this._request(`/api/v1/proofs/${proofId}`);
  }

  async listProofs({ page = 1, pageSize = 25 } = {}) {
    return this._request(`/api/v1/proofs?page=${page}&page_size=${pageSize}`);
  }

  async anchorProof(proofId) {
    return this._request(`/api/v1/anchor/${proofId}`, { method: "POST", body: "{}" });
  }

  async similaritySearch({ text, topK = 5 }) {
    return this._request("/api/v1/similarity", {
      method: "POST",
      body: JSON.stringify({ text, top_k: topK }),
    });
  }

  async fetchPublicStatus(fileHash) {
    return this._request(`/verify/${fileHash}`);
  }

  async fetchManifest(fileHash) {
    const response = await fetch(`${this.baseUrl}/verify/${fileHash}/manifest`, {
      headers: this.headers,
    });
    if (!response.ok) {
      throw new Error(`Manifest not found (${response.status})`);
    }
    return response.json();
  }

  static sha256(buffer) {
    return crypto.createHash("sha256").update(buffer).digest("hex");
  }

  static zeroTrustVerify({ filePath, ledger, manifest }) {
    const buffer = fs.readFileSync(filePath);
    const computedHash = ProofOriginClient.sha256(buffer);
    const normalizedHash = ledger?.normalized_hash;
    const manifestHash = manifest?.proof?.hash;
    return {
      computedHash,
      matchesLedger: normalizedHash ? normalizedHash === computedHash : null,
      matchesManifest: manifestHash ? manifestHash === computedHash : null,
      ledger,
      manifest,
    };
  }
}

module.exports = { ProofOriginClient };
