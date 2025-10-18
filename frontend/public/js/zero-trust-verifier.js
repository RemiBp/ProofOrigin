(() => {
  async function sha256Hex(buffer) {
    const digest = await crypto.subtle.digest("SHA-256", buffer);
    return Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  async function fetchJson(url) {
    if (!url) return null;
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`Failed to load manifest: ${response.status}`);
    return response.json();
  }

  async function verify(options) {
    const { file, manifestUrl, ledger } = options;
    if (!file) throw new Error("file_required");
    const buffer = await file.arrayBuffer();
    const computedHash = await sha256Hex(buffer);
    const normalizedHash = ledger?.normalized_hash || ledger?.hash;
    const manifest = manifestUrl ? await fetchJson(manifestUrl) : null;
    const manifestHash = manifest?.proof?.hash;

    const results = {
      computedHash,
      matchesLedger: normalizedHash ? normalizedHash === computedHash : null,
      matchesManifest: manifestHash ? manifestHash === computedHash : null,
      ledger,
      manifest,
    };

    const receipts = ledger?.blockchain_receipts || [];
    results.receipts = receipts.map((entry) => ({
      chain: entry.chain,
      transaction_hash: entry.transaction_hash,
      anchored_at: entry.anchored_at,
    }));

    return results;
  }

  window.ProofOriginVerifier = {
    verify,
  };
})();
