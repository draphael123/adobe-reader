/**
 * Hash Storage for Duplicate Detection
 */
export class HashStorage {
  constructor() {
    this.memoryCache = new Map();
    this.maxMemoryHashes = 1000;
  }

  async initialize() {
    // Load from storage if needed
    const result = await chrome.storage.local.get('hashStorage');
    if (result.hashStorage) {
      // Restore memory cache (limited)
      const hashes = result.hashStorage;
      const entries = Object.entries(hashes).slice(0, this.maxMemoryHashes);
      entries.forEach(([key, value]) => {
        this.memoryCache.set(key, value);
      });
    }
  }

  async addHash(hash, docName) {
    const key = `${docName}:${hash}`;
    
    // Add to memory cache
    this.memoryCache.set(key, {
      hash,
      docName,
      timestamp: Date.now()
    });

    // Limit memory cache
    if (this.memoryCache.size > this.maxMemoryHashes) {
      const firstKey = this.memoryCache.keys().next().value;
      this.memoryCache.delete(firstKey);
    }

    // Save to storage
    await this.saveToStorage();
  }

  async hasHash(hash, docName) {
    const key = `${docName}:${hash}`;
    
    // Check memory cache first
    if (this.memoryCache.has(key)) {
      return true;
    }

    // Check storage
    const result = await chrome.storage.local.get('hashStorage');
    if (result.hashStorage) {
      return result.hashStorage[key] !== undefined;
    }

    return false;
  }

  async clearDocument(docName) {
    // Clear from memory
    for (const [key, value] of this.memoryCache.entries()) {
      if (value.docName === docName) {
        this.memoryCache.delete(key);
      }
    }

    // Clear from storage
    const result = await chrome.storage.local.get('hashStorage');
    if (result.hashStorage) {
      Object.keys(result.hashStorage).forEach(key => {
        if (key.startsWith(`${docName}:`)) {
          delete result.hashStorage[key];
        }
      });
      await chrome.storage.local.set({ hashStorage: result.hashStorage });
    }
  }

  async saveToStorage() {
    const hashStorage = {};
    this.memoryCache.forEach((value, key) => {
      hashStorage[key] = value;
    });
    await chrome.storage.local.set({ hashStorage });
  }

  getStats() {
    return {
      memory_hashes: this.memoryCache.size,
      max_memory: this.maxMemoryHashes
    };
  }
}

