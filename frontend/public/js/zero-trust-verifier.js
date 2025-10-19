(() => {
  async function sha256Hex(buffer) {
    const digest = await crypto.subtle.digest("SHA-256", buffer);
    return Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  async function fetchJson(url) {
    if (!url) return null;
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) throw new Error(`Failed to load manifest: ${response.status}`);
      return response.json();
    } catch (err) {
      console.warn("prooforigin_verifier_network_error", err);
      return null;
    }
  }

  function parseProofArtifact(input) {
    if (!input) return null;
    if (typeof input === "string") {
      try {
        return JSON.parse(input);
      } catch (error) {
        console.warn("prooforigin_verifier_artifact_parse_failed", error);
        return null;
      }
    }
    return input;
  }

  async function verify(options) {
    const { file, manifestUrl, ledger, proof, proofUrl } = options;
    if (!file) throw new Error("file_required");
    const buffer = await file.arrayBuffer();
    const computedHash = await sha256Hex(buffer);
    const normalizedHash = ledger?.normalized_hash || ledger?.hash;
    const manifest = (await fetchJson(manifestUrl)) || options.manifest || null;
    const proofArtifact = parseProofArtifact(
      proof || (await fetchJson(proofUrl)) || manifest?.proof_artifact
    );
    const manifestHash = manifest?.proof?.hash || proofArtifact?.hash?.value;

    const results = {
      computedHash,
      matchesLedger: normalizedHash ? normalizedHash === computedHash : null,
      matchesManifest: manifestHash ? manifestHash === computedHash : null,
      ledger,
      manifest,
      proof: proofArtifact,
    };

    const receipts = ledger?.blockchain_receipts || [];
    results.receipts = receipts.map((entry) => ({
      chain: entry.chain,
      transaction_hash: entry.transaction_hash,
      anchored_at: entry.anchored_at,
    }));

    if (proofArtifact?.transparency_log) {
      results.transparency = {
        namespace: proofArtifact.transparency_log.namespace,
        sequence: proofArtifact.transparency_log.sequence,
      };
    }

    if (proofArtifact?.normalized_hash?.value) {
      results.matchesProof = proofArtifact.normalized_hash.value === computedHash;
    }

    return results;
  }

  window.ProofOriginVerifier = {
    verify,
  };
})();
