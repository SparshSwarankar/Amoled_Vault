// Enhanced Multiple File Upload JavaScript
document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.getElementById("file")
  const fileUploadArea = document.getElementById("file-upload-area")
  const filePreview = document.getElementById("file-preview")
  const uploadForm = document.getElementById("upload-form")
  const submitBtn = document.getElementById("submit-btn")

  let selectedFiles = []

  // Message system functions (use real UI if available)
  function showMessage(message, type = "info", duration = 3000) {
    const msgContainer = document.getElementById("message-container")
    if (msgContainer) {
      const msg = document.createElement("div")
      msg.className = `custom-message ${type}`
      msg.innerHTML = `<span class="message-text">${message}</span>`
      msgContainer.appendChild(msg)
      setTimeout(() => { if (msg.parentNode) msg.remove() }, duration)
    } else {
      console.log(`Message: ${message}, Type: ${type}, Duration: ${duration}`)
    }
  }

  function showToast(message, type = "info", duration = 3000) {
    const toastContainer = document.getElementById("toast-container")
    if (toastContainer) {
      const toast = document.createElement("div")
      toast.className = `toast ${type}`
      toast.textContent = message
      toastContainer.appendChild(toast)
      setTimeout(() => toast.classList.add("show"), 100)
      setTimeout(() => {
        toast.classList.remove("show")
        setTimeout(() => toast.remove(), 300)
      }, duration)
    } else {
      console.log(`Toast: ${message}, Type: ${type}, Duration: ${duration}`)
    }
  }

  // Drag and drop functionality
  fileUploadArea.addEventListener("dragover", (e) => {
    e.preventDefault()
    fileUploadArea.classList.add("drag-over")
  })

  fileUploadArea.addEventListener("dragleave", (e) => {
    e.preventDefault()
    fileUploadArea.classList.remove("drag-over")
  })

  fileUploadArea.addEventListener("drop", (e) => {
    e.preventDefault()
    fileUploadArea.classList.remove("drag-over")

    const files = Array.from(e.dataTransfer.files)
    handleMultipleFiles(files)
  })

  // File input change
  fileInput.addEventListener("change", (e) => {
    const files = Array.from(e.target.files)
    handleMultipleFiles(files)
  })

  // Handle multiple file selection with validation
  function handleMultipleFiles(files) {
    const maxFiles = 10
    // Prevent duplicates
    const existingNames = new Set(selectedFiles.map(f => f.name + f.size))
    const newFiles = files.filter(f => !existingNames.has(f.name + f.size))
    if (selectedFiles.length + newFiles.length > maxFiles) {
      showMessage(`Too many files selected. Maximum ${maxFiles} files allowed at once.`, "error", 4000)
      return
    }
    const errors = validateFiles([...selectedFiles, ...newFiles])
    if (errors.length > 0) {
      errors.forEach(err => showMessage(err, "error", 4000))
      return
    }
    const validFiles = []
    const allowedTypes = ["image/png", "image/jpeg", "image/jpg", "image/webp"]
    const maxSize = 10 * 1024 * 1024 // 10MB
    newFiles.forEach((file) => {
      if (!allowedTypes.includes(file.type)) {
        showMessage(`❌ Invalid file type: ${file.name}. Please select PNG, JPG, JPEG, or WEBP files.`, "error", 4000)
        return
      }
      if (file.size > maxSize) {
        showMessage(`⚠️ File too large: ${file.name}. Please select files under 10MB.`, "error", 4000)
        return
      }
      validFiles.push(file)
    })
    if (validFiles.length > 0) {
      selectedFiles = [...selectedFiles, ...validFiles]
      updateFilePreview()
      showToast(`${validFiles.length} file(s) selected successfully! 📁`, "success", 2000)
    }
  }

  // Update file preview for multiple files
  function updateFilePreview() {
    if (selectedFiles.length === 0) {
      filePreview.innerHTML = ""
      filePreview.classList.add("hidden")
      return
    }
    filePreview.innerHTML = `
      <div class="multiple-file-preview" id="multiple-preview">
        ${selectedFiles
          .map(
            (file, index) => `
              <div class="file-preview-item" data-index="${index}">
                  <img src="${URL.createObjectURL(file)}" alt="Preview" class="preview-image">
                  <button type="button" class="file-preview-remove" onclick="removeFile(${index})">×</button>
                  <div class="file-preview-info">
                      <p class="file-preview-name">${file.name}</p>
                      <p class="file-preview-size">${(file.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
              </div>
            `,
          )
          .join("")}
      </div>
      <div class="file-summary">
        <p style="color: #4ecdc4; text-align: center; margin-top: 1rem; font-weight: 500;">
          ${selectedFiles.length} file(s) ready for upload
        </p>
      </div>
    `
    filePreview.classList.remove("hidden")
    addClearAllButton()
  }

  // Remove individual file
  window.removeFile = (index) => {
    selectedFiles.splice(index, 1)
    updateFilePreview()
    updateFileInput()
    showToast("File removed 🗑️", "info", 1500)
  }

  // Clear all files
  window.clearAllFiles = () => {
    selectedFiles = []
    updateFilePreview()
    updateFileInput()
    showToast("All files cleared 🧹", "info", 2000)
  }

  // Update the actual file input with selected files
  function updateFileInput() {
    const dt = new DataTransfer()
    selectedFiles.forEach((file) => dt.items.add(file))
    fileInput.files = dt.files
  }

  // Form submission with progress tracking
  uploadForm.addEventListener("submit", (e) => {
    e.preventDefault()

    if (selectedFiles.length === 0) {
      showMessage("❌ Please select at least one file to upload.", "error", 3000)
      return
    }

    // Show loading state
    submitBtn.classList.add("loading")
    submitBtn.disabled = true

    const fileCount = selectedFiles.length
    const fileText = fileCount === 1 ? "wallpaper" : "wallpapers"

    showMessage(`📤 Uploading ${fileCount} ${fileText}... Please wait.`, "info", 3000)
    showToast(`Upload in progress... ⏳ (${fileCount} files)`, "info", 2000)

    // Show upload progress
    showUploadProgress()

    // Update file input and submit
    updateFileInput()

    setTimeout(() => {
      uploadForm.submit()
    }, 1000)
  })

  // Show upload progress for multiple files
  function showUploadProgress() {
    const progressContainer = document.createElement("div")
    progressContainer.className = "upload-progress-container"
    progressContainer.style.display = "block"

    progressContainer.innerHTML = `
            <h4 style="color: #fff; margin-bottom: 1rem;">📤 Upload Progress</h4>
            ${selectedFiles
              .map(
                (file, index) => `
                <div class="upload-progress-item">
                    <div class="progress-header">
                        <span class="progress-filename">${file.name}</span>
                        <span class="progress-status" id="status-${index}">Preparing...</span>
                    </div>
                    <div class="progress-bar-container">
                        <div class="progress-bar-fill" id="progress-${index}"></div>
                    </div>
                </div>
            `,
              )
              .join("")}
        `

    filePreview.appendChild(progressContainer)

    // Simulate progress for each file
    selectedFiles.forEach((file, index) => {
      setTimeout(() => {
        const statusEl = document.getElementById(`status-${index}`)
        const progressEl = document.getElementById(`progress-${index}`)

        if (statusEl && progressEl) {
          statusEl.textContent = "Uploading..."
          progressEl.style.width = "100%"

          setTimeout(
            () => {
              statusEl.textContent = "Complete ✅"
              statusEl.style.color = "#4caf50"
            },
            1000 + index * 200,
          )
        }
      }, index * 300)
    })
  }

  // Enhanced file validation
  function validateFiles(files) {
    const errors = []
    const allowedTypes = ["image/png", "image/jpeg", "image/jpg", "image/webp"]
    const maxSize = 10 * 1024 * 1024 // 10MB
    const maxFiles = 10 // Maximum 10 files at once

    if (files.length > maxFiles) {
      errors.push(`Too many files selected. Maximum ${maxFiles} files allowed at once.`)
    }

    files.forEach((file, index) => {
      if (!allowedTypes.includes(file.type)) {
        errors.push(`File ${index + 1} (${file.name}): Invalid file type.`)
      }

      if (file.size > maxSize) {
        errors.push(`File ${index + 1} (${file.name}): File too large (max 10MB).`)
      }
    })

    return errors
  }

  // Add clear all button to preview
  function addClearAllButton() {
  // Remove any existing clear button first
  const existing = filePreview.querySelector('.btn-secondary')
  if (existing) existing.remove()
  const clearBtn = document.createElement("button")
  clearBtn.type = "button"
  clearBtn.className = "btn-secondary"
  clearBtn.style.marginTop = "1rem"
  clearBtn.textContent = "🗑️ Clear All Files"
  clearBtn.onclick = window.clearAllFiles
  filePreview.appendChild(clearBtn)
  }
})
