/**
 * Options/Settings Page Logic
 */

document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  setupEventListeners();
});

async function loadSettings() {
  const config = await chrome.runtime.sendMessage({ action: 'get_config' });
  
  // Populate form
  document.getElementById('enabled').checked = config.enabled || false;
  document.getElementById('capture_delay').value = config.capture_delay || 300;
  document.getElementById('capture_on_scroll').checked = config.capture_on_scroll !== false;
  document.getElementById('duplicate_detection_enabled').checked = config.duplicate_detection_enabled !== false;
  document.getElementById('duplicate_similarity_threshold').value = config.duplicate_similarity_threshold || 5;
  document.getElementById('image_format').value = config.image_format || 'png';
  document.getElementById('jpeg_quality').value = config.jpeg_quality || 90;
  document.getElementById('save_folder').value = config.save_folder || 'PDF Screenshots';
  document.getElementById('show_notifications').checked = config.show_notifications !== false;
}

function setupEventListeners() {
  document.getElementById('saveBtn').addEventListener('click', saveSettings);
}

async function saveSettings() {
  const config = {
    enabled: document.getElementById('enabled').checked,
    capture_delay: parseInt(document.getElementById('capture_delay').value),
    capture_on_scroll: document.getElementById('capture_on_scroll').checked,
    duplicate_detection_enabled: document.getElementById('duplicate_detection_enabled').checked,
    duplicate_similarity_threshold: parseInt(document.getElementById('duplicate_similarity_threshold').value),
    image_format: document.getElementById('image_format').value,
    jpeg_quality: parseInt(document.getElementById('jpeg_quality').value),
    save_folder: document.getElementById('save_folder').value,
    show_notifications: document.getElementById('show_notifications').checked
  };

  // Save each setting
  for (const [key, value] of Object.entries(config)) {
    await chrome.runtime.sendMessage({
      action: 'update_config',
      key: key,
      value: value
    });
  }

  // Show success message
  const btn = document.getElementById('saveBtn');
  const originalText = btn.textContent;
  btn.textContent = '✓ Saved!';
  btn.style.background = '#4caf50';
  
  setTimeout(() => {
    btn.textContent = originalText;
    btn.style.background = '#4caf50';
  }, 2000);
}

