const showcaseItems = [
  {
    title: "Leonardo AI – Campagne Luxury",
    description:
      "Images générées et signées via le SDK ProofOrigin avec badge public + preuve blockchain Polygon.",
    hash: "0x9a4c…d12f",
    status: "Verified",
    chain: "Polygon",
  },
  {
    title: "Runway – Spot TV",
    description: "Vidéo 4K ancrée via batch Merkle + horodatage OpenTimestamps, log publique disponible.",
    hash: "0xbc3f…aa10",
    status: "Partially Proven",
    chain: "Polygon + OTS",
  },
  {
    title: "Photographe – Série NFT",
    description: "Preuves pHash + CLIP pour détecter les dérivés, badge Content Credentials intégré.",
    hash: "0x7fd8…93ab",
    status: "Verified",
    chain: "Polygon",
  },
];

export default function ShowcasePage() {
  return (
    <section className="page-section">
      <div className="page-header">
        <span className="badge">Showcase</span>
        <h1>Ils ancrent leurs créations avec ProofOrigin</h1>
        <p>
          Des studios de design aux plateformes IA : consultez des assets publics avec badge C2PA, reçus
          PolygonScan et export .proof prêts à embarquer dans vos workflows.
        </p>
      </div>
      <div className="showcase-grid">
        {showcaseItems.map((item) => (
          <article key={item.hash} className="glass-card">
            <header>
              <h2>{item.title}</h2>
              <span className={`status-tag status-${item.status.replace(/\s+/g, "-").toLowerCase()}`}>
                {item.status}
              </span>
            </header>
            <p>{item.description}</p>
            <dl>
              <div>
                <dt>Hash</dt>
                <dd className="mono">{item.hash}</dd>
              </div>
              <div>
                <dt>Anchors</dt>
                <dd>{item.chain}</dd>
              </div>
            </dl>
            <footer>
              <a className="btn btn-secondary" href={`/verify/${item.hash.replace("…", "")}`}>
                Voir la preuve
              </a>
            </footer>
          </article>
        ))}
      </div>
    </section>
  );
}
