/**
 * Statistics Manager
 */
export class Statistics {
  constructor() {
    this.defaultStats = {
      total_captures: 0,
      session_captures: 0,
      total_size_bytes: 0,
      duplicate_detections: 0,
      documents_captured: [],
      captures_by_date: {},
      last_capture_time: null,
      first_run_date: null
    };
  }

  async load() {
    const result = await chrome.storage.local.get('statistics');
    this.stats = { ...this.defaultStats, ...(result.statistics || {}) };
    
    if (!this.stats.first_run_date) {
      this.stats.first_run_date = new Date().toISOString();
      await this.save();
    }
    
    return this.stats;
  }

  async save() {
    await chrome.storage.local.set({ statistics: this.stats });
  }

  async recordCapture(data) {
    if (!this.stats) await this.load();
    
    this.stats.total_captures++;
    this.stats.session_captures++;
    this.stats.last_capture_time = new Date().toISOString();
    this.stats.total_size_bytes += data.size || 0;

    const today = new Date().toISOString().split('T')[0];
    if (!this.stats.captures_by_date[today]) {
      this.stats.captures_by_date[today] = 0;
    }
    this.stats.captures_by_date[today]++;

    if (!this.stats.documents_captured.includes(data.docName)) {
      this.stats.documents_captured.push(data.docName);
      if (this.stats.documents_captured.length > 50) {
        this.stats.documents_captured = this.stats.documents_captured.slice(-50);
      }
    }

    await this.save();
  }

  async recordDuplicate() {
    if (!this.stats) await this.load();
    this.stats.duplicate_detections++;
    await this.save();
  }

  async getSummary() {
    if (!this.stats) await this.load();
    
    const totalSizeMB = this.stats.total_size_bytes / (1024 * 1024);
    const firstRun = new Date(this.stats.first_run_date);
    const daysActive = Math.floor((Date.now() - firstRun.getTime()) / (1000 * 60 * 60 * 24)) + 1;
    const avgPerDay = this.stats.total_captures / daysActive;

    return {
      total_captures: this.stats.total_captures,
      session_captures: this.stats.session_captures,
      total_size_mb: Math.round(totalSizeMB * 100) / 100,
      documents_count: this.stats.documents_captured.length,
      days_active: daysActive,
      avg_per_day: Math.round(avgPerDay * 10) / 10,
      duplicate_detections: this.stats.duplicate_detections
    };
  }
}

