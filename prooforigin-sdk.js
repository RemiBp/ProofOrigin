/**
 * ProofOrigin SDK - JavaScript/Node.js
 * SDK officiel pour l'intégration avec l'API ProofOrigin
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const FormData = require('form-data');
const fetch = require('node-fetch');

class ProofOriginClient {
    /**
     * Initialise le client ProofOrigin
     * @param {string} apiUrl - URL de l'API ProofOrigin
     * @param {string} apiKey - Clé API (optionnelle)
     */
    constructor(apiUrl = 'https://api.prooforigin.com', apiKey = null) {
        this.apiUrl = apiUrl.replace(/\/$/, '');
        this.apiKey = apiKey;
        this.headers = {
            'User-Agent': 'ProofOrigin-SDK-JS/1.0.0'
        };
        
        if (apiKey) {
            this.headers['Authorization'] = `Bearer ${apiKey}`;
        }
    }

    /**
     * Enregistre un fichier et crée une preuve d'authenticité
     * @param {string} filePath - Chemin vers le fichier
     * @param {Object} metadata - Métadonnées optionnelles
     * @returns {Promise<Object>} Informations de la preuve créée
     */
    async registerFile(filePath, metadata = null) {
        if (!fs.existsSync(filePath)) {
            throw new Error(`Fichier non trouvé: ${filePath}`);
        }

        try {
            const formData = new FormData();
            const fileStream = fs.createReadStream(filePath);
            const fileName = path.basename(filePath);
            
            formData.append('file', fileStream, fileName);
            
            if (metadata) {
                formData.append('metadata', JSON.stringify(metadata));
            }

            const response = await fetch(`${this.apiUrl}/api/register`, {
                method: 'POST',
                body: formData,
                headers: this.headers
            });

            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            throw new Error(`Erreur lors de l'enregistrement: ${error.message}`);
        }
    }

    /**
     * Vérifie l'authenticité d'un fichier
     * @param {string} filePath - Chemin vers le fichier
     * @returns {Promise<Object>} Résultats de la vérification
     */
    async verifyFile(filePath) {
        if (!fs.existsSync(filePath)) {
            throw new Error(`Fichier non trouvé: ${filePath}`);
        }

        try {
            const formData = new FormData();
            const fileStream = fs.createReadStream(filePath);
            const fileName = path.basename(filePath);
            
            formData.append('file', fileStream, fileName);

            const response = await fetch(`${this.apiUrl}/api/verify`, {
                method: 'POST',
                body: formData,
                headers: this.headers
            });

            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            throw new Error(`Erreur lors de la vérification: ${error.message}`);
        }
    }

    /**
     * Récupère les détails d'une preuve
     * @param {number} proofId - ID de la preuve
     * @returns {Promise<Object>} Détails de la preuve
     */
    async getProof(proofId) {
        try {
            const response = await fetch(`${this.apiUrl}/api/proofs/${proofId}`, {
                headers: this.headers
            });

            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            throw new Error(`Erreur lors de la récupération: ${error.message}`);
        }
    }

    /**
     * Liste les preuves disponibles
     * @param {number} limit - Nombre maximum de preuves
     * @param {number} offset - Décalage pour la pagination
     * @returns {Promise<Object>} Liste des preuves
     */
    async listProofs(limit = 100, offset = 0) {
        try {
            const params = new URLSearchParams({
                limit: limit.toString(),
                offset: offset.toString()
            });

            const response = await fetch(`${this.apiUrl}/api/proofs?${params}`, {
                headers: this.headers
            });

            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            throw new Error(`Erreur lors de la récupération: ${error.message}`);
        }
    }

    /**
     * Exporte une preuve au format .proof
     * @param {number} proofId - ID de la preuve
     * @param {string} outputPath - Chemin de sortie (optionnel)
     * @returns {Promise<string>} Chemin vers le fichier .proof
     */
    async exportProof(proofId, outputPath = null) {
        try {
            const response = await fetch(`${this.apiUrl}/export/${proofId}`, {
                headers: this.headers
            });

            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }

            if (!outputPath) {
                const contentDisposition = response.headers.get('content-disposition');
                if (contentDisposition && contentDisposition.includes('filename=')) {
                    outputPath = contentDisposition.split('filename=')[1].replace(/"/g, '');
                } else {
                    outputPath = `proof_${proofId}.proof`;
                }
            }

            const buffer = await response.buffer();
            fs.writeFileSync(outputPath, buffer);

            return outputPath;
        } catch (error) {
            throw new Error(`Erreur lors de l'export: ${error.message}`);
        }
    }

    /**
     * Vérifie un fichier avec sa preuve .proof
     * @param {string} filePath - Chemin vers le fichier original
     * @param {string} proofPath - Chemin vers le fichier .proof
     * @returns {Promise<Object>} Résultats de la vérification
     */
    async verifyProofFile(filePath, proofPath) {
        try {
            // Charger la preuve
            const proofData = JSON.parse(fs.readFileSync(proofPath, 'utf8'));

            // Calculer le hash du fichier
            const fileBuffer = fs.readFileSync(filePath);
            const fileHash = crypto.createHash('sha256').update(fileBuffer).digest('hex');

            // Vérifier l'intégrité
            const storedHash = proofData.hash.value;
            const integrityOk = fileHash === storedHash;

            return {
                verified: integrityOk,
                fileHash: fileHash,
                storedHash: storedHash,
                proofData: proofData,
                timestamp: proofData.timestamp?.readable || 'Unknown'
            };
        } catch (error) {
            throw new Error(`Erreur lors de la vérification: ${error.message}`);
        }
    }

    /**
     * Calcule le hash SHA-256 d'un fichier
     * @param {string} filePath - Chemin vers le fichier
     * @returns {Promise<string>} Hash SHA-256
     */
    async computeFileHash(filePath) {
        return new Promise((resolve, reject) => {
            const hash = crypto.createHash('sha256');
            const stream = fs.createReadStream(filePath);

            stream.on('data', (data) => hash.update(data));
            stream.on('end', () => resolve(hash.digest('hex')));
            stream.on('error', reject);
        });
    }
}

// Fonctions utilitaires pour une utilisation simple
/**
 * Enregistre un fichier (fonction simple)
 * @param {string} filePath - Chemin vers le fichier
 * @param {string} apiUrl - URL de l'API
 * @returns {Promise<Object>} Informations de la preuve
 */
async function registerFile(filePath, apiUrl = 'https://api.prooforigin.com') {
    const client = new ProofOriginClient(apiUrl);
    return await client.registerFile(filePath);
}

/**
 * Vérifie un fichier (fonction simple)
 * @param {string} filePath - Chemin vers le fichier
 * @param {string} apiUrl - URL de l'API
 * @returns {Promise<Object>} Résultats de la vérification
 */
async function verifyFile(filePath, apiUrl = 'https://api.prooforigin.com') {
    const client = new ProofOriginClient(apiUrl);
    return await client.verifyFile(filePath);
}

// Export pour Node.js
module.exports = {
    ProofOriginClient,
    registerFile,
    verifyFile
};

// Export pour les navigateurs (si utilisé avec un bundler)
if (typeof window !== 'undefined') {
    window.ProofOrigin = {
        ProofOriginClient,
        registerFile,
        verifyFile
    };
}

// Exemple d'utilisation
if (require.main === module) {
    async function example() {
        const client = new ProofOriginClient('http://localhost:5000'); // Pour les tests locaux

        try {
            // Enregistrer un fichier
            console.log('📝 Enregistrement d\'un fichier...');
            const result = await client.registerFile('example.txt');
            console.log('✅ Preuve créée:', result);

            // Vérifier le fichier
            console.log('\n🔍 Vérification du fichier...');
            const verification = await client.verifyFile('example.txt');
            console.log('✅ Vérification:', verification);

            // Lister les preuves
            console.log('\n📋 Liste des preuves...');
            const proofs = await client.listProofs();
            console.log(`✅ ${proofs.count} preuves trouvées`);

        } catch (error) {
            console.error('❌ Erreur:', error.message);
        }
    }

    example();
}
