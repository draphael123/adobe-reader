/**
 * Popup UI Logic
 */

let config = null;
let stats = null;

document.addEventListener('DOMContentLoaded', async () => {
  await loadData();
  setupEventListeners();
  updateUI();
  
  // Update every 2 seconds
  setInterval(updateUI, 2000);
});

async function loadData() {
  const [configData, statsData, tabInfo] = await Promise.all([
    chrome.runtime.sendMessage({ action: 'get_config' }),
    chrome.runtime.sendMessage({ action: 'get_stats' }),
    chrome.tabs.query({ active: true, currentWindow: true })
  ]);
  
  config = configData;
  stats = statsData;
  
  // Get page info from content script
  if (tabInfo[0]) {
    try {
      const pageInfo = await chrome.tabs.sendMessage(tabInfo[0].id, { action: 'get_page_info' });
      if (pageInfo) {
        document.getElementById('currentPage').textContent = pageInfo.page || '-';
        document.getElementById('docName').textContent = pageInfo.docName || '-';
      }
    } catch (e) {
      // Content script not available
    }
  }
}

function setupEventListeners() {
  document.getElementById('toggleBtn').addEventListener('click', toggleEnabled);
  document.getElementById('captureBtn').addEventListener('click', manualCapture);
  document.getElementById('settingsBtn').addEventListener('click', openSettings);
  document.getElementById('galleryBtn').addEventListener('click', openGallery);
}

async function toggleEnabled() {
  const newValue = !config.enabled;
  await chrome.runtime.sendMessage({
    action: 'update_config',
    key: 'enabled',
    value: newValue
  });
  config.enabled = newValue;
  updateUI();
}

async function manualCapture() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tabs[0]) {
    try {
      await chrome.tabs.sendMessage(tabs[0].id, { action: 'manual_capture' });
      // Show feedback
      const btn = document.getElementById('captureBtn');
      btn.textContent = '✓ Captured!';
      setTimeout(() => {
        btn.textContent = 'Capture Now';
      }, 2000);
    } catch (e) {
      alert('Please navigate to a PDF page first');
    }
  }
}

function openSettings() {
  chrome.runtime.openOptionsPage();
}

function openGallery() {
  // Open gallery window
  chrome.tabs.create({ url: chrome.runtime.getURL('gallery.html') });
}

function updateUI() {
  // Update status
  const statusDot = document.getElementById('statusDot');
  const statusText = document.getElementById('statusText');
  const toggleBtn = document.getElementById('toggleBtn');
  const toggleText = document.getElementById('toggleText');
  
  if (config && config.enabled) {
    statusDot.className = 'status-dot active';
    statusText.textContent = 'Active';
    toggleText.textContent = 'Disable';
    toggleBtn.className = 'btn btn-primary active';
  } else {
    statusDot.className = 'status-dot inactive';
    statusText.textContent = 'Inactive';
    toggleText.textContent = 'Enable';
    toggleBtn.className = 'btn btn-primary';
  }
  
  // Update stats
  if (stats) {
    document.getElementById('totalCaptures').textContent = stats.total_captures || 0;
    document.getElementById('sessionCaptures').textContent = stats.session_captures || 0;
    document.getElementById('duplicates').textContent = stats.duplicate_detections || 0;
  }
  
  // Reload data periodically
  loadData();
}

