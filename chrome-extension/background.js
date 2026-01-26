/**
 * Background service worker for PDF Screenshot Tool
 * Handles capture coordination, storage, and processing
 */

import { ConfigManager } from './modules/config.js';
import { HashStorage } from './modules/hash-storage.js';
import { Statistics } from './modules/statistics.js';
import { ExportManager } from './modules/export-manager.js';

class PDFScreenshotBackground {
  constructor() {
    this.config = new ConfigManager();
    this.hashStorage = new HashStorage();
    this.stats = new Statistics();
    this.exportManager = new ExportManager();
    this.activeCaptures = new Map(); // tabId -> capture info
    this.initialize();
  }

  async initialize() {
    await this.config.load();
    await this.hashStorage.initialize();
    await this.stats.load();
    
    // Set up listeners
    chrome.tabs.onUpdated.addListener(this.onTabUpdated.bind(this));
    chrome.tabs.onRemoved.addListener(this.onTabRemoved.bind(this));
    chrome.runtime.onMessage.addListener(this.onMessage.bind(this));
    
    console.log('PDF Screenshot Tool background initialized');
  }

  async onTabUpdated(tabId, changeInfo, tab) {
    if (changeInfo.status === 'complete' && tab.url) {
      // Check if this is a PDF
      if (tab.url.endsWith('.pdf') || tab.mimeType === 'application/pdf') {
        await this.setupPDFCapture(tabId, tab);
      }
    }
  }

  async onTabRemoved(tabId) {
    this.activeCaptures.delete(tabId);
  }

  async onMessage(message, sender, sendResponse) {
    // Handle async responses
    const handleAsync = async () => {
      try {
        switch (message.action) {
          case 'capture_page':
            return await this.handleCapture(message.data, sender);
          
          case 'get_config':
            return await this.config.getAll();
          
          case 'update_config':
            await this.config.set(message.key, message.value);
            return { success: true };
          
          case 'get_stats':
            return await this.stats.getSummary();
          
          case 'export_powerpoint':
            return await this.exportManager.exportToPowerPoint(message.data);
          
          case 'export_pdf':
            return await this.exportManager.exportToPDF(message.data);
          
          case 'clear_hashes':
            await this.hashStorage.clearDocument(message.docName);
            return { success: true };
          
          case 'get_current_tab':
            // Helper to get current tab from sender
            if (sender && sender.tab) {
              return { id: sender.tab.id };
            }
            return { id: null };
          
          default:
            return { error: 'Unknown action' };
        }
      } catch (error) {
        console.error('Message handler error:', error);
        return { error: error.message };
      }
    };

    // Return true to indicate we'll send response asynchronously
    handleAsync().then(response => sendResponse(response));
    return true; // Required for async sendResponse
  }

  async setupPDFCapture(tabId, tab) {
    try {
      // Inject content script if needed
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ['injected.js']
      });

      // Store capture info
      this.activeCaptures.set(tabId, {
        url: tab.url,
        title: tab.title,
        startTime: Date.now(),
        pageCount: 0
      });

      console.log(`PDF capture setup for tab ${tabId}`);
    } catch (error) {
      console.error('Error setting up PDF capture:', error);
    }
  }

  async handleCapture(data, sender) {
    const config = await this.config.getAll();
    
    if (!config.enabled) {
      return { skipped: true, reason: 'disabled' };
    }

    // Get the tab that sent the message
    let tab = null;
    if (sender && sender.tab) {
      tab = sender.tab;
    } else if (data.tabId) {
      try {
        tab = await chrome.tabs.get(data.tabId);
      } catch (e) {
        console.error('Error getting tab:', e);
      }
    }

    // Capture visible tab if imageData not provided
    let imageData = data.imageData;
    if (!imageData && tab) {
      try {
        imageData = await chrome.tabs.captureVisibleTab(tab.windowId, {
          format: 'png',
          quality: 100
        });
      } catch (error) {
        console.error('Error capturing tab:', error);
        return { error: 'Failed to capture tab' };
      }
    }

    if (!imageData) {
      return { error: 'No image data available' };
    }

    // Check for duplicates
    if (config.duplicate_detection_enabled && data.imageHash) {
      const isDuplicate = await this.hashStorage.hasHash(
        data.imageHash,
        data.docName
      );
      
      if (isDuplicate) {
        await this.stats.recordDuplicate();
        return { skipped: true, reason: 'duplicate' };
      }
      
      await this.hashStorage.addHash(data.imageHash, data.docName);
    }

    // Process image (skip watermark/crop in service worker - would need offscreen canvas)
    // For now, use image as-is. Image processing can be done in content script if needed.
    let processedImage = imageData;
    
    // Note: Watermark and crop processing requires DOM APIs which aren't available in service worker
    // These features would need to be implemented using offscreen canvas or done in content script
    // For now, we'll skip image processing in background and use the captured image directly

    // Convert to blob and download
    const filename = this.generateFilename(data.docName, data.pageNumber, config);
    
    // Convert data URL to blob
    let blob;
    try {
      const response = await fetch(processedImage);
      blob = await response.blob();
    } catch (error) {
      // If fetch fails, try direct download from data URL
      console.warn('Fetch failed, using data URL directly:', error);
      const downloadId = await chrome.downloads.download({
        url: processedImage,
        filename: filename,
        saveAs: false
      });
      
      await this.stats.recordCapture({
        filename,
        docName: data.docName,
        pageNumber: data.pageNumber,
        size: 0
      });
      
      if (tab) {
        const captureInfo = this.activeCaptures.get(tab.id);
        if (captureInfo) {
          captureInfo.pageCount++;
        }
      }
      
      if (config.show_notifications) {
        chrome.notifications.create({
          type: 'basic',
          title: 'PDF Screenshot Tool',
          message: `Captured page ${data.pageNumber || '?'}`
        });
      }
      
      return { success: true, downloadId, filename };
    }
    
    // Create object URL
    const blobUrl = URL.createObjectURL(blob);
    
    // Download file
    const downloadId = await chrome.downloads.download({
      url: blobUrl,
      filename: filename,
      saveAs: false
    });

    // Record statistics
    await this.stats.recordCapture({
      filename,
      docName: data.docName,
      pageNumber: data.pageNumber,
      size: blob.size
    });

    // Update active capture
    const captureInfo = this.activeCaptures.get(tab.id);
    if (captureInfo) {
      captureInfo.pageCount++;
    }

    // Show notification if enabled
    if (config.show_notifications) {
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon48.png',
        title: 'PDF Screenshot Tool',
        message: `Captured page ${data.pageNumber || '?'}`
      });
    }

    return { success: true, downloadId, filename };
  }

  generateFilename(docName, pageNumber, config) {
    const now = new Date();
    const template = config.filename_template || '{document}_{page}_{date}_{time}';
    
    let filename = template
      .replace('{document}', docName || 'PDF')
      .replace('{page}', pageNumber ? `Page_${String(pageNumber).padStart(3, '0')}` : 'Page')
      .replace('{date}', now.toISOString().split('T')[0].replace(/-/g, ''))
      .replace('{time}', now.toTimeString().split(' ')[0].replace(/:/g, ''))
      .replace('{datetime}', now.toISOString().replace(/[:.]/g, '-').split('.')[0]);
    
    // Clean filename
    filename = filename.replace(/[^a-zA-Z0-9._-]/g, '_');
    
    const extension = config.image_format === 'jpeg' ? 'jpg' : config.image_format || 'png';
    return `${config.save_folder || 'PDF Screenshots'}/${docName || 'PDF'}/${filename}.${extension}`;
  }

}

// Initialize background service
const background = new PDFScreenshotBackground();

