/**
 * Configuration Manager for Chrome Extension
 */
export class ConfigManager {
  constructor() {
    this.defaultConfig = {
      enabled: true,
      capture_delay: 300,
      capture_cooldown: 500,
      capture_on_scroll: true,
      duplicate_detection_enabled: true,
      duplicate_similarity_threshold: 5,
      image_format: 'png',
      jpeg_quality: 90,
      save_folder: 'PDF Screenshots',
      filename_template: '{document}_{page}_{date}_{time}',
      watermark_enabled: false,
      watermark_type: 'timestamp',
      watermark_text: '',
      watermark_position: 'bottom-right',
      watermark_opacity: 50,
      crop_enabled: false,
      crop_top: 0,
      crop_bottom: 0,
      crop_left: 0,
      crop_right: 0,
      show_notifications: true,
      auto_copy_clipboard: false,
      organize_by_document: true,
      organize_by_date: false,
      use_page_numbers: true,
      toast_notifications: true
    };
  }

  async load() {
    const result = await chrome.storage.sync.get('config');
    this.config = { ...this.defaultConfig, ...(result.config || {}) };
    return this.config;
  }

  async save() {
    await chrome.storage.sync.set({ config: this.config });
  }

  async get(key) {
    if (!this.config) await this.load();
    return this.config[key] !== undefined ? this.config[key] : this.defaultConfig[key];
  }

  async set(key, value) {
    if (!this.config) await this.load();
    this.config[key] = value;
    await this.save();
  }

  async getAll() {
    if (!this.config) await this.load();
    return { ...this.config };
  }
}

