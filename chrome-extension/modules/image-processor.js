/**
 * Image Processing Utilities
 */
export class ImageProcessor {
  applyWatermark(imageData, config) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext('2d');
        
        ctx.drawImage(img, 0, 0);
        
        if (config.watermark_enabled) {
          const watermark = this.createWatermark(canvas, config);
          ctx.drawImage(watermark, 0, 0);
        }
        
        resolve(canvas.toDataURL('image/png'));
      };
      img.src = imageData;
    });
  }

  createWatermark(canvas, config) {
    const watermarkCanvas = document.createElement('canvas');
    watermarkCanvas.width = canvas.width;
    watermarkCanvas.height = canvas.height;
    const ctx = watermarkCanvas.getContext('2d');
    
    ctx.fillStyle = 'rgba(255, 255, 255, 0)';
    ctx.fillRect(0, 0, watermarkCanvas.width, watermarkCanvas.height);
    
    let text = '';
    if (config.watermark_type === 'timestamp') {
      text = new Date().toLocaleString();
    } else if (config.watermark_type === 'text') {
      text = config.watermark_text || '';
    }
    
    if (text) {
      ctx.font = `${config.watermark_font_size || 14}px Arial`;
      ctx.fillStyle = `rgba(255, 255, 255, ${(config.watermark_opacity || 50) / 100})`;
      ctx.textAlign = 'right';
      ctx.textBaseline = 'bottom';
      
      const x = canvas.width - 10;
      const y = canvas.height - 10;
      ctx.fillText(text, x, y);
    }
    
    return watermarkCanvas;
  }

  applyCrop(imageData, config) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        const cropLeft = config.crop_left || 0;
        const cropRight = config.crop_right || 0;
        const cropTop = config.crop_top || 0;
        const cropBottom = config.crop_bottom || 0;
        
        canvas.width = img.width - cropLeft - cropRight;
        canvas.height = img.height - cropTop - cropBottom;
        
        ctx.drawImage(
          img,
          cropLeft, cropTop, canvas.width, canvas.height,
          0, 0, canvas.width, canvas.height
        );
        
        resolve(canvas.toDataURL('image/png'));
      };
      img.src = imageData;
    });
  }
}

