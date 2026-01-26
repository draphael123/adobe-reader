/**
 * Content script for PDF Screenshot Tool
 * Detects PDFs and handles page navigation
 */

(function() {
  'use strict';

  let isPDF = false;
  let currentPage = 1;
  let totalPages = 0;
  let docName = '';
  let lastCaptureTime = 0;
  let captureCooldown = 500; // ms
  let config = null;

  // Initialize
  async function init() {
    // Check if this is a PDF
    if (window.location.href.endsWith('.pdf') || 
        document.contentType === 'application/pdf' ||
        document.querySelector('embed[type="application/pdf"]') ||
        document.querySelector('iframe[src*=".pdf"]')) {
      isPDF = true;
      await setupPDFCapture();
    }
  }

  async function setupPDFCapture() {
    // Get configuration
    const response = await chrome.runtime.sendMessage({ action: 'get_config' });
    config = response || {};
    
    // Extract document name
    docName = extractDocumentName();
    
    // Detect PDF viewer type and setup
    if (isChromePDFViewer()) {
      setupChromePDFViewer();
    } else if (isEmbeddedPDF()) {
      setupEmbeddedPDF();
    }
    
    // Listen for navigation
    setupNavigationListeners();
    
    console.log('PDF Screenshot Tool: PDF detected', { docName, currentPage });
  }

  function extractDocumentName() {
    const url = window.location.href;
    const filename = url.split('/').pop().split('?')[0];
    return filename.replace('.pdf', '') || 'PDF';
  }

  function isChromePDFViewer() {
    return document.querySelector('embed[type="application/pdf"]') !== null ||
           window.location.href.includes('chrome-extension://') ||
           document.querySelector('iframe[src*="pdf"]') !== null;
  }

  function isEmbeddedPDF() {
    return document.querySelector('embed[type="application/pdf"]') !== null ||
           document.querySelector('object[type="application/pdf"]') !== null;
  }

  function setupChromePDFViewer() {
    // Chrome's built-in PDF viewer
    const embed = document.querySelector('embed[type="application/pdf"]');
    if (embed) {
      // Monitor for page changes
      observePDFViewer();
    }
  }

  function setupEmbeddedPDF() {
    // Embedded PDF (iframe or embed)
    observePDFViewer();
  }

  function observePDFViewer() {
    // Use MutationObserver to detect page changes
    const observer = new MutationObserver(() => {
      detectPageChange();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    // Also listen to keyboard events
    document.addEventListener('keydown', handleKeyPress);
    document.addEventListener('wheel', handleScroll, { passive: true });
  }

  function setupNavigationListeners() {
    // Listen for keyboard navigation
    document.addEventListener('keydown', handleKeyPress);
    
    // Listen for scroll
    document.addEventListener('wheel', handleScroll, { passive: true });
    
    // Listen for touch (mobile)
    document.addEventListener('touchstart', handleTouch, { passive: true });
  }

  function handleKeyPress(event) {
    if (!config || !config.enabled) return;
    
    const navKeys = ['ArrowDown', 'ArrowUp', 'PageDown', 'PageUp', 'Home', 'End'];
    if (navKeys.includes(event.key)) {
      setTimeout(() => capturePage(), config.capture_delay || 300);
    }
  }

  function handleScroll(event) {
    if (!config || !config.enabled || !config.capture_on_scroll) return;
    
    // Debounce scroll
    clearTimeout(window.scrollTimeout);
    window.scrollTimeout = setTimeout(() => {
      capturePage();
    }, config.capture_delay || 300);
  }

  function handleTouch(event) {
    if (!config || !config.enabled) return;
    
    setTimeout(() => capturePage(), config.capture_delay || 300);
  }

  function detectPageChange() {
    // Try to detect current page number
    const pageInfo = extractPageInfo();
    if (pageInfo.page !== currentPage) {
      currentPage = pageInfo.page;
      totalPages = pageInfo.total || totalPages;
      
      if (config && config.enabled) {
        setTimeout(() => capturePage(), config.capture_delay || 300);
      }
    }
  }

  function extractPageInfo() {
    // Try multiple methods to get page number
    let page = currentPage;
    let total = totalPages;

    // Method 1: Chrome PDF viewer toolbar
    const toolbar = document.querySelector('.toolbar');
    if (toolbar) {
      const pageText = toolbar.textContent;
      const match = pageText.match(/(\d+)\s*\/\s*(\d+)/);
      if (match) {
        page = parseInt(match[1]);
        total = parseInt(match[2]);
      }
    }

    // Method 2: Look for page indicators in the DOM
    const pageIndicators = document.querySelectorAll('[class*="page"], [id*="page"]');
    for (const indicator of pageIndicators) {
      const text = indicator.textContent;
      const match = text.match(/(\d+)\s*\/\s*(\d+)/);
      if (match) {
        page = parseInt(match[1]);
        total = parseInt(match[2]);
        break;
      }
    }

    return { page, total };
  }

  async function capturePage() {
    const now = Date.now();
    if (now - lastCaptureTime < captureCooldown) {
      return; // Cooldown
    }
    lastCaptureTime = now;

    try {
      // Get current tab ID
      const tabs = await chrome.runtime.sendMessage({ action: 'get_current_tab' });
      const tabId = tabs?.id || null;
      
      // Calculate hash from current view (simplified)
      const hash = await calculateSimpleHash();
      
      // Send to background for processing
      // Background will handle the actual tab capture
      const result = await chrome.runtime.sendMessage({
        action: 'capture_page',
        data: {
          imageHash: hash,
          docName: docName,
          pageNumber: currentPage,
          timestamp: Date.now(),
          tabId: tabId
        }
      });

      if (result && result.success) {
        console.log('Page captured:', currentPage);
      } else if (result && result.skipped) {
        console.log('Page skipped:', result.reason);
      } else if (result && result.error) {
        console.error('Capture error:', result.error);
      }
    } catch (error) {
      console.error('Capture error:', error);
    }
  }

  async function captureCanvas() {
    // Create canvas from current view
    const canvas = document.createElement('canvas');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    
    const ctx = canvas.getContext('2d');
    
    // For PDFs, we need to capture the embed/iframe content
    // This is a simplified version - may need adjustment based on PDF viewer
    const pdfElement = document.querySelector('embed[type="application/pdf"]') ||
                      document.querySelector('iframe[src*=".pdf"]');
    
    if (pdfElement) {
      // Try to capture the PDF content
      // Note: This may have CORS limitations
      try {
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        // Draw PDF content if accessible
      } catch (e) {
        console.warn('Could not capture PDF content directly:', e);
      }
    }
    
    return canvas;
  }

  async function calculateSimpleHash() {
    // Simple hash based on page number and document name
    // In a real implementation, this would use perceptual hashing
    const data = `${docName}_${currentPage}_${window.scrollY}`;
    let hash = 0;
    for (let i = 0; i < data.length; i++) {
      const char = data.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return hash.toString();
  }

  // Listen for messages from popup/background
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'manual_capture') {
      capturePage().then(() => sendResponse({ success: true }));
      return true; // Async response
    }
    
    if (message.action === 'get_page_info') {
      sendResponse({ page: currentPage, total: totalPages, docName });
    }
  });

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

