/* Shared image handling for citizen and field reports. */
window.WaterlineUpload = {
  async resize(file, config) {
    if (file.size > config.max_upload_bytes) throw Error('A photo is too large. Choose a smaller image.');
    const image = await createImageBitmap(file);
    try {
      if (image.width * image.height > config.max_image_pixels) throw Error('A photo is too large to process.');
      const ratio = Math.min(1, config.resize_px / Math.max(image.width, image.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(image.width * ratio); canvas.height = Math.round(image.height * ratio);
      canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', config.jpeg_quality / 100));
      if (!blob) throw Error('This photo could not be prepared. Try a JPEG or PNG.');
      return blob;
    } finally { image.close(); }
  },
  async send(url, data, config, onProgress, onStatus) {
    for (let attempt = 0; attempt < config.retry_attempts; attempt++) {
      try {
        return await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest(); xhr.open('POST', url); if (url === '/api/field/reports') xhr.setRequestHeader('X-Waterline-Request', '1'); xhr.timeout = 120000;
          xhr.upload.onprogress = event => {
            if (event.lengthComputable) {
              onProgress(event.loaded / event.total * 100);
              if (event.loaded === event.total) onStatus('Photos uploaded. Reviewing the report…');
            }
          };
          xhr.onload = () => {
            let value; try { value = JSON.parse(xhr.responseText); } catch { reject(Error('The server response could not be read.')); return; }
            if (xhr.status >= 200 && xhr.status < 300) resolve(value);
            else {
              const error = Error(typeof value.detail === 'string' ? value.detail : 'Check the report fields and try again.');
              error.permanent = xhr.status >= 400 && xhr.status < 500; reject(error);
            }
          };
          xhr.onerror = () => reject(Error('Connection lost. Keep this page open and try again.'));
          xhr.ontimeout = () => reject(Error('The report timed out. Please try again.'));
          xhr.send(data);
        });
      } catch (error) {
        if (error.permanent || attempt + 1 === config.retry_attempts) throw error;
        onStatus('Report held in this tab. Reconnecting…');
        await new Promise(resolve => setTimeout(resolve, 1000 * 2 ** attempt));
      }
    }
  },
  previews(input, container) {
    container.querySelectorAll('img').forEach(image => URL.revokeObjectURL(image.src));
    container.replaceChildren();
    for (const file of input.files) {
      const image = document.createElement('img'); image.alt = file.name;
      image.src = URL.createObjectURL(file); container.append(image);
    }
  }
};
