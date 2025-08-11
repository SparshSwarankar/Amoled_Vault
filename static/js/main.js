// Global variables
let currentSlide = 0
let currentCategory = "all"
let currentDeviceType = "mobile"

// DOM elements
const carousel = document.getElementById("carousel")
const gallery = document.getElementById("gallery")
const loading = document.getElementById("loading")
const messageContainer = document.getElementById("message-container")
const toastContainer = document.getElementById("toast-container")
const downloadModal = document.getElementById("download-modal")
const loadingOverlay = document.getElementById("loading-overlay")
const welcomeBanner = document.getElementById("welcome-banner")
const mobileHint = document.getElementById("mobile-hint")
const noResults = document.getElementById("no-results")
const networkStatus = document.getElementById("network-status")

// Mobile detection and vibration support
const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
const supportsVibration = "vibrate" in navigator

// Show a blocking message if on mobile
document.addEventListener('DOMContentLoaded', function() {
  if (isMobile) {
    document.body.innerHTML = `
      <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;text-align:center;background:#111;color:#fff;">
        <div style="font-size:3rem;">⚠️</div>
        <h2 style="margin:1rem 0;">Mobile Not Supported</h2>
        <p style="font-size:1.2rem;max-width:400px;">This website is not available on mobile devices.<br>Please use a desktop or laptop for the best experience.</p>
      </div>
    `;
    document.body.style.background = '#111';
    document.body.style.color = '#fff';
  }
});

// Vibration patterns - reduced frequency
const vibrationPatterns = {
  light: 30,
  medium: 50,
  success: [50, 30, 50],
  error: [100, 50, 100],
  download: [80, 40, 80],
}

// Utility functions
function vibrate(pattern) {
  if (isMobile && supportsVibration) {
    navigator.vibrate(pattern)
  }
}

function showMessage(message, type = "info", duration = 3000) {
  const messageEl = document.createElement("div")
  messageEl.className = `custom-message ${type}`
  messageEl.innerHTML = `
    <div class="message-content">
      <span class="message-text">${message}</span>
      <button class="message-close" onclick="this.parentElement.parentElement.remove()">×</button>
    </div>
  `

  messageContainer.appendChild(messageEl)

  // Auto remove after duration
  setTimeout(() => {
    if (messageEl.parentNode) {
      messageEl.remove()
    }
  }, duration)

  // Reduced vibration - only for important messages
  if (type === "success" || type === "error") {
    switch (type) {
      case "success":
        vibrate(vibrationPatterns.success)
        break
      case "error":
        vibrate(vibrationPatterns.error)
        break
    }
  }
}

function showToast(message, type = "info", duration = 3000) {
  const toast = document.createElement("div")
  toast.className = `toast ${type}`
  toast.textContent = message

  toastContainer.appendChild(toast)

  // Show toast
  setTimeout(() => toast.classList.add("show"), 100)

  // Remove after duration
  setTimeout(() => {
    toast.classList.remove("show")
    setTimeout(() => toast.remove(), 300)
  }, duration)
}

function showDownloadModal(title) {
  const titleEl = document.getElementById("download-title")
  const progressBar = document.getElementById("progress-bar")

  titleEl.textContent = `Downloading ${title}`
  progressBar.style.width = "0%"

  downloadModal.classList.remove("hidden")

  // Animate progress bar
  setTimeout(() => {
    progressBar.style.width = "100%"
  }, 100)

  // Hide modal after 3 seconds
  setTimeout(() => {
    downloadModal.classList.add("hidden")
  }, 3000)
}

function showLoadingOverlay(text = "Loading amazing wallpapers...") {
  const loadingText = document.getElementById("loading-text")
  loadingText.textContent = text
  loadingOverlay.classList.remove("hidden")
}

function hideLoadingOverlay() {
  loadingOverlay.classList.add("hidden")
}

function updateGalleryCount(count) {
  const galleryCount = document.getElementById("gallery-count")
  if (galleryCount) {
    galleryCount.textContent = count
  }
}

function updateFilterBadge(category) {
  const filterBadge = document.getElementById("filter-badge")
  if (filterBadge) {
    filterBadge.textContent =
      category === "all" ? "All categories" : `${category.charAt(0).toUpperCase() + category.slice(1)} category`
  }
}

function updateDeviceInfo(deviceType, count) {
  const deviceIcon = document.querySelector(".device-icon")
  const deviceText = document.querySelector(".device-text h3")
  const deviceSubtext = document.querySelector(".device-text p")
  const deviceCount = document.getElementById("current-device-count")
  const totalDeviceCount = document.getElementById("device-count")

  if (deviceType === "pc") {
    deviceIcon.textContent = "💻"
    deviceText.textContent = "PC Wallpapers"
    deviceSubtext.textContent = "Optimized for desktops and laptops"
  } else {
    deviceIcon.textContent = "📱"
    deviceText.textContent = "Mobile Wallpapers"
    deviceSubtext.textContent = "Optimized for smartphones and tablets"
  }

  if (deviceCount) deviceCount.textContent = count
  if (totalDeviceCount) totalDeviceCount.textContent = count
}

function closeWelcomeBanner() {
  welcomeBanner.classList.add("hidden")
}

function closeMobileHint() {
  mobileHint.classList.add("hidden")
}

// Device Type Switching
function switchDeviceType(deviceType) {
  if (currentDeviceType === deviceType) return

  currentDeviceType = deviceType

  // Update active button
  document.querySelectorAll(".device-btn").forEach((btn) => {
    btn.classList.remove("active")
  })
  document.querySelector(`[data-device="${deviceType}"]`).classList.add("active")

  // Show loading
  showLoadingOverlay(`Loading ${deviceType.toUpperCase()} wallpapers...`)

  // Update URL without page reload
  const url = new URL(window.location)
  url.searchParams.set("device", deviceType)
  window.history.pushState({}, "", url)

  // Load wallpapers for the new device type
  loadWallpapersByDevice(deviceType)

  // Show device switch message
  const deviceName = deviceType === "pc" ? "PC" : "Mobile"
  showMessage(`Switched to ${deviceName} wallpapers! 🔄`, "success", 3000)
  showToast(`Now showing ${deviceName} wallpapers 📱💻`, "info", 2000)
}

async function loadWallpapersByDevice(deviceType) {
  try {
    const [wallpapersResponse, popularResponse, statsResponse] = await Promise.all([
      fetch(`/api/wallpapers?device=${deviceType}&category=${currentCategory}`),
      fetch(`/api/popular?device=${deviceType}`),
      fetch(`/api/stats?device=${deviceType}`),
    ])

    const wallpapers = await wallpapersResponse.json()
    const popularWallpapers = await popularResponse.json()
    const stats = await statsResponse.json()

    // Update gallery
    updateGallery(wallpapers)

    // Update popular section
    updatePopularSection(popularWallpapers)

    // Update carousel
    updateCarousel(wallpapers.slice(0, 5))

    // Update statistics
    updateStatistics(stats)

    // Update device info
    updateDeviceInfo(deviceType, wallpapers.length)

    // Update categories for this device type
    updateCategories(wallpapers)

    hideLoadingOverlay()

    if (wallpapers.length === 0) {
      gallery.style.display = "none"
      noResults.classList.remove("hidden")
      showMessage(`No ${deviceType.toUpperCase()} wallpapers found 😔`, "error", 3000)
    } else {
      gallery.style.display = "grid"
      noResults.classList.add("hidden")
      showToast(`Found ${wallpapers.length} ${deviceType.toUpperCase()} wallpapers 🔍`, "success", 2000)
    }
  } catch (error) {
    console.error("Error loading wallpapers:", error)
    hideLoadingOverlay()
    showMessage("Failed to load wallpapers 😞", "error", 3000)
  }
}

function updateGallery(wallpapers) {
  const gallery = document.getElementById("gallery")

  gallery.innerHTML = wallpapers
    .map(
      (wallpaper, index) => `
    <div class="wallpaper-card" data-category="${wallpaper.category}" data-device="${wallpaper.device_type}" style="animation-delay: ${index * 0.05}s">
      <div class="image-container">
        <img src="/static/wallpapers/${wallpaper.filename}" 
             alt="${wallpaper.title}" 
             loading="lazy"
             class="wallpaper-image wallpaper-preview-img"
             data-filename="${wallpaper.filename}"
             data-title="${wallpaper.title}"
             data-category="${wallpaper.category}"
             data-downloads="${wallpaper.download_count || 0}"
             data-id="${wallpaper.id}"
             data-device="${wallpaper.device_type}">
        <div class="device-badge device-${wallpaper.device_type}">
          ${wallpaper.device_type.toUpperCase()}
        </div>
        <div class="image-overlay">
          <h3>${wallpaper.title}</h3>
          <div class="overlay-tags">
            <span class="category-tag">${wallpaper.category}</span>
          </div>
          <button class="download-btn wallpaper-download-btn"
                  data-filename="${wallpaper.filename}"
                  data-title="${wallpaper.title}"
                  data-id="${wallpaper.id}">
            📥 Download
          </button>
        </div>
      </div>
    </div>
  `,
    )
    .join("")

  updateGalleryCount(wallpapers.length)
}

function updatePopularSection(wallpapers) {
  const popularGrid = document.getElementById("popular-grid")

  popularGrid.innerHTML = wallpapers
    .map(
      (wallpaper) => `
    <div class="popular-card" data-device="${wallpaper.device_type}">
      <div class="popular-image-container">
        <img src="/static/wallpapers/${wallpaper.filename}" 
             alt="${wallpaper.title}" 
             loading="lazy"
             class="popular-image wallpaper-preview-img"
             data-filename="${wallpaper.filename}"
             data-title="${wallpaper.title}"
             data-category="${wallpaper.category}"
             data-downloads="${wallpaper.download_count || 0}"
             data-id="${wallpaper.id}"
             data-device="${wallpaper.device_type}">
        <div class="download-badge">
          <span class="download-count">${wallpaper.download_count || 0}</span>
          <span class="download-label">downloads</span>
        </div>
        <div class="device-badge device-${wallpaper.device_type}">
          ${wallpaper.device_type.toUpperCase()}
        </div>
        <div class="popular-overlay">
          <h4>${wallpaper.title}</h4>
          <div class="overlay-tags">
            <span class="category-tag">${wallpaper.category}</span>
          </div>
          <button class="download-btn wallpaper-download-btn"
                  data-filename="${wallpaper.filename}"
                  data-title="${wallpaper.title}"
                  data-id="${wallpaper.id}">
            📥 Download
          </button>
        </div>
      </div>
    </div>
  `,
    )
    .join("")
}

function updateCarousel(wallpapers) {
  const carousel = document.getElementById("carousel")

  carousel.innerHTML = wallpapers
    .map(
      (wallpaper) => `
    <div class="carousel-slide" data-device="${wallpaper.device_type}">
      <img src="/static/wallpapers/${wallpaper.filename}" 
           alt="${wallpaper.title}" 
           loading="lazy"
           class="wallpaper-preview-img"
           data-filename="${wallpaper.filename}"
           data-title="${wallpaper.title}"
           data-category="${wallpaper.category}"
           data-downloads="${wallpaper.download_count || 0}"
           data-id="${wallpaper.id}"
           data-device="${wallpaper.device_type}">
      <div class="carousel-caption">
        <h3>${wallpaper.title}</h3>
        <div class="caption-tags">
          <span class="category-tag">${wallpaper.category}</span>
          <span class="device-tag device-${wallpaper.device_type}">${wallpaper.device_type.toUpperCase()}</span>
        </div>
        <button class="download-btn wallpaper-download-btn"
                data-filename="${wallpaper.filename}"
                data-title="${wallpaper.title}"
                data-id="${wallpaper.id}">
          📥 Download
        </button>
      </div>
    </div>
  `,
    )
    .join("")

  // Reset carousel position
  currentSlide = 0
  updateCarouselPosition()
}

function updateStatistics(stats) {
  animateNumber("total-downloads", stats.total_downloads)
  animateNumber("total-wallpapers", stats.total_wallpapers)
  animateNumber("downloads-24h", stats.downloads_24h)
}

function updateCategories(wallpapers) {
  const categories = [...new Set(wallpapers.map((w) => w.category))].sort()
  const filterButtons = document.querySelector(".filter-buttons")

  filterButtons.innerHTML = `
    <button class="filter-btn ${currentCategory === "all" ? "active" : ""}" onclick="filterWallpapers('all')">All</button>
    ${categories
      .map(
        (category) => `
      <button class="filter-btn ${currentCategory === category ? "active" : ""}" onclick="filterWallpapers('${category.toLowerCase()}')">${category.charAt(0).toUpperCase() + category.slice(1)}</button>
    `,
      )
      .join("")}
  `
}

// Initialize the application
document.addEventListener("DOMContentLoaded", () => {
  // Get device type from URL or default to mobile
  const urlParams = new URLSearchParams(window.location.search)
  const deviceFromUrl = urlParams.get("device")
  if (deviceFromUrl && ["mobile", "pc"].includes(deviceFromUrl)) {
    currentDeviceType = deviceFromUrl
    // Update active button
    document.querySelectorAll(".device-btn").forEach((btn) => {
      btn.classList.remove("active")
    })
    document.querySelector(`[data-device="${currentDeviceType}"]`)?.classList.add("active")
  }

  // Show welcome banner
  setTimeout(() => {
    if (welcomeBanner) {
      welcomeBanner.classList.remove("hidden")
    }
  }, 1000)

  // Show mobile hint for mobile users
  if (isMobile) {
    setTimeout(() => {
      if (mobileHint) {
        mobileHint.classList.remove("hidden")
      }
      showToast("Mobile experience optimized! 📱")
    }, 2000)
  }

  initializeCarousel()
  initializeLazyLoading()
  loadStatistics()
  initializeMobileInteractions()

  // Auto-play carousel
  setInterval(() => {
    moveCarousel(1)
  }, 5000)

  // Update statistics every 30 seconds
  setInterval(() => {
    loadStatistics()
  }, 30000)

  // Auto-hide welcome banner after 5 seconds
  setTimeout(() => {
    if (welcomeBanner && !welcomeBanner.classList.contains("hidden")) {
      closeWelcomeBanner()
    }
  }, 5000)
})

// Mobile-specific interactions - reduced vibration
function initializeMobileInteractions() {
  if (!isMobile) return

  // Add touch feedback to all interactive elements - no vibration for every touch
  const interactiveElements = document.querySelectorAll("button, .wallpaper-card, .popular-card, .filter-btn")

  interactiveElements.forEach((element) => {
    element.addEventListener("touchstart", () => {
      element.classList.add("touch-active")
    })

    element.addEventListener("touchend", () => {
      setTimeout(() => element.classList.remove("touch-active"), 150)
    })
  })

  // Long press for additional options - only vibrate on long press
  let longPressTimer
  document.querySelectorAll(".wallpaper-card").forEach((card) => {
    card.addEventListener("touchstart", (e) => {
      longPressTimer = setTimeout(() => {
        vibrate(vibrationPatterns.medium)
        showMessage("Long press detected! More options coming soon 🚀", "info", 2000)
      }, 800)
    })

    card.addEventListener("touchend", () => {
      clearTimeout(longPressTimer)
    })
  })
}

// Carousel functionality
function initializeCarousel() {
  const slides = document.querySelectorAll(".carousel-slide")
  if (slides.length === 0) return

  // Clone first and last slides for infinite loop effect
  const firstSlide = slides[0].cloneNode(true)
  const lastSlide = slides[slides.length - 1].cloneNode(true)

  carousel.appendChild(firstSlide)
  carousel.insertBefore(lastSlide, slides[0])

  updateCarouselPosition()
}

function moveCarousel(direction) {
  const slides = document.querySelectorAll(".carousel-slide")
  const totalSlides = slides.length

  if (totalSlides === 0) return

  currentSlide += direction

  // Handle infinite loop
  if (currentSlide >= totalSlides - 2) {
    currentSlide = 0
  } else if (currentSlide < 0) {
    currentSlide = totalSlides - 3
  }

  updateCarouselPosition()
  // No vibration for carousel navigation
}

function updateCarouselPosition() {
  const slideWidth = 100
  const offset = -(currentSlide + 1) * slideWidth
  carousel.style.transform = `translateX(${offset}%)`
}

// Filter functionality
function filterWallpapers(category) {
  currentCategory = category

  // Update filter badge
  updateFilterBadge(category)

  // Show category switch message
  const categoryName = category === "all" ? "All Categories" : category.charAt(0).toUpperCase() + category.slice(1)
  showToast(`Browsing ${categoryName} wallpapers 📱`)

  // Update active filter button
  document.querySelectorAll(".filter-btn").forEach((btn) => {
    btn.classList.remove("active")
  })

  // Find the clicked button and make it active
  const clickedButton = Array.from(document.querySelectorAll(".filter-btn")).find(
    (btn) =>
      btn.textContent.toLowerCase() === category.toLowerCase() ||
      (category === "all" && btn.textContent.toLowerCase() === "all"),
  )

  if (clickedButton) {
    clickedButton.classList.add("active")
  }

  // Show loading
  showLoadingOverlay("Filtering wallpapers...")

  // Load filtered wallpapers
  setTimeout(() => {
    loadFilteredWallpapers(category, currentDeviceType)
  }, 500)
}

async function loadFilteredWallpapers(category, deviceType) {
  try {
    const response = await fetch(`/api/wallpapers?device=${deviceType}&category=${category}`)
    const wallpapers = await response.json()

    updateGallery(wallpapers)
    hideLoadingOverlay()

    if (wallpapers.length === 0) {
      gallery.style.display = "none"
      noResults.classList.remove("hidden")
      showMessage("No wallpapers found in this category 😔", "error", 3000)
    } else {
      gallery.style.display = "grid"
      noResults.classList.add("hidden")
      showToast(`Found ${wallpapers.length} wallpapers 🔍`)
    }
  } catch (error) {
    console.error("Error loading filtered wallpapers:", error)
    hideLoadingOverlay()
    showMessage("Failed to load wallpapers 😞", "error", 3000)
  }
}

function resetFilters() {
  currentCategory = "all"
  switchDeviceType("mobile")
  filterWallpapers("all")
}

// Custom Instagram Confirmation Modal
function showInstagramModal(filename, title, wallpaperId) {
  const modal = document.createElement("div")
  modal.className = "instagram-modal"
  modal.innerHTML = `
    <div class="instagram-modal-backdrop" onclick="closeInstagramModal()"></div>
    <div class="instagram-modal-content">
      <div class="instagram-modal-header">
        <h3>🎨 Download "${title}"</h3>
        <button class="instagram-modal-close" onclick="closeInstagramModal()">×</button>
      </div>
      <div class="instagram-modal-body">
        <div class="instagram-info">
          <div class="instagram-icon">📸</div>
          <p>Help us create more amazing wallpapers by following our Instagram page!</p>
          <p class="instagram-subtitle">Following us supports our work and gives you access to exclusive content.</p>
        </div>
        <div class="instagram-checkbox-container">
          <label class="custom-checkbox">
            <input type="checkbox" id="instagram-followed">
            <span class="checkmark"></span>
            <span class="checkbox-text">I have followed your Instagram page</span>
          </label>
        </div>
        <div class="instagram-actions">
          <button class="instagram-btn secondary" onclick="openInstagramPage()">
            📸 Follow Instagram
          </button>
          <button class="instagram-btn primary" onclick="proceedWithDownload('${filename}', '${title}', '${wallpaperId}')" disabled>
            📥 Download Wallpaper
          </button>
        </div>
      </div>
    </div>
  `

  document.body.appendChild(modal)
  document.body.classList.add("modal-open")

  // Add checkbox event listener
  const checkbox = modal.querySelector("#instagram-followed")
  const downloadBtn = modal.querySelector(".instagram-btn.primary")

  checkbox.addEventListener("change", function () {
    downloadBtn.disabled = !this.checked
    if (this.checked) {
      downloadBtn.classList.add("enabled")
      vibrate(vibrationPatterns.light)
    } else {
      downloadBtn.classList.remove("enabled")
    }
  })
}

function closeInstagramModal() {
  const modal = document.querySelector(".instagram-modal")
  if (modal) {
    modal.remove()
    document.body.classList.remove("modal-open")
  }
}

function openInstagramPage() {
  window.open(window.INSTAGRAM_URL, "_blank")
  showToast("Instagram page opened! Please follow us 📸", "info", 3000)
}

function proceedWithDownload(filename, title, wallpaperId) {
  closeInstagramModal()
  trackDownload(wallpaperId, filename, title)
}

// Download functionality with custom Instagram modal
function handleDownload(filename, title, wallpaperId) {
  // Show download start message
  showMessage(`Preparing to download "${title}" 📥`, "info", 2000)

  // Show custom Instagram modal instead of browser confirm
  showInstagramModal(filename, title, wallpaperId)
}

// Track downloads
function trackDownload(wallpaperId, filename, title) {
  // Track the download in backend
  fetch("/api/track-download", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      wallpaper_id: wallpaperId,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        // Proceed with actual download
        downloadWallpaper(filename, title)
        // Update statistics on page
        loadStatistics()
        // Update popular wallpapers
        updatePopularWallpapers()

        // Show success message
        showMessage(`"${title}" downloaded successfully! ✅`, "success", 3000)
      }
    })
    .catch((error) => {
      console.error("Error tracking download:", error)
      showMessage("Oops! Something went wrong. Please try again 😅", "error", 3000)
      // Still allow download even if tracking fails
      downloadWallpaper(filename, title)
    })
}

// Load and display statistics
function loadStatistics() {
  fetch(`/api/stats?device=${currentDeviceType}`)
    .then((response) => response.json())
    .then((stats) => {
      // Update stat numbers with animation
      animateNumber("total-downloads", stats.total_downloads)
      animateNumber("total-wallpapers", stats.total_wallpapers)
      animateNumber("downloads-24h", stats.downloads_24h)

      // Show stats update message less frequently
      if (Math.random() < 0.1) {
        showToast("Statistics updated! 📊")
      }
    })
    .catch((error) => {
      console.error("Error loading statistics:", error)
      showMessage("Failed to load statistics 📊", "error", 2000)
    })
}

// Animate number counting
function animateNumber(elementId, targetNumber) {
  const element = document.getElementById(elementId)
  if (!element) return

  const startNumber = 0
  const duration = 1000
  const increment = targetNumber / (duration / 16)
  let currentNumber = startNumber

  const timer = setInterval(() => {
    currentNumber += increment
    if (currentNumber >= targetNumber) {
      currentNumber = targetNumber
      clearInterval(timer)
    }
    element.textContent = Math.floor(currentNumber).toLocaleString()
  }, 16)
}

// Update popular wallpapers section
function updatePopularWallpapers() {
  fetch(`/api/popular?device=${currentDeviceType}`)
    .then((response) => response.json())
    .then((wallpapers) => {
      updatePopularSection(wallpapers)
    })
    .catch((error) => {
      console.error("Error updating popular wallpapers:", error)
    })
}

function downloadWallpaper(filename, title) {
  // Show download modal with enhanced feedback
  showDownloadModal(title)

  // Vibrate only for actual download
  vibrate(vibrationPatterns.download)

  // Create download link
  const downloadUrl = `/download/${filename}`
  const link = document.createElement("a")
  link.href = downloadUrl
  link.download = filename
  link.style.display = "none"

  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)

  console.log(`Downloaded: ${title} (${filename})`)
}

// Lazy loading implementation
function initializeLazyLoading() {
  const images = document.querySelectorAll('img[loading="lazy"]')

  if ("IntersectionObserver" in window) {
    const imageObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const img = entry.target
          img.src = img.src
          img.classList.add("loaded")
          observer.unobserve(img)
        }
      })
    })

    images.forEach((img) => imageObserver.observe(img))
  }
}

// Loading states
function showLoading() {
  if (loading) {
    loading.style.display = "block"
  }
}

function hideLoading() {
  if (loading) {
    loading.style.display = "none"
  }
}

// Keyboard navigation for carousel
document.addEventListener("keydown", (e) => {
  if (e.key === "ArrowLeft") {
    moveCarousel(-1)
  } else if (e.key === "ArrowRight") {
    moveCarousel(1)
  }
})

// Enhanced touch/swipe support for mobile carousel
let startX = 0
let endX = 0
let startY = 0
let endY = 0

carousel?.addEventListener("touchstart", (e) => {
  startX = e.touches[0].clientX
  startY = e.touches[0].clientY
})

carousel?.addEventListener("touchend", (e) => {
  endX = e.changedTouches[0].clientX
  endY = e.changedTouches[0].clientY
  handleSwipe()
})

function handleSwipe() {
  const threshold = 50
  const diffX = startX - endX
  const diffY = Math.abs(startY - endY)

  if (Math.abs(diffX) > threshold && diffY < threshold) {
    if (diffX > 0) {
      moveCarousel(1)
    } else {
      moveCarousel(-1)
    }
  }
}

// Reduced interaction feedback - no vibration for every click
document.addEventListener("click", (e) => {
  if (e.target.matches("button, .filter-btn")) {
    e.target.classList.add("pulse")
    setTimeout(() => e.target.classList.remove("pulse"), 300)
  }
})

// Page visibility change handling
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    showToast("Welcome back! 👋")
  }
})

// Network status handling
window.addEventListener("online", () => {
  networkStatus.classList.add("online")
  document.getElementById("network-icon").textContent = "🌐"
  document.getElementById("network-text").textContent = "Connection restored!"
  networkStatus.classList.remove("hidden")

  setTimeout(() => {
    networkStatus.classList.add("hidden")
  }, 3000)

  showMessage("Connection restored! 🌐", "success", 2000)
})

window.addEventListener("offline", () => {
  networkStatus.classList.remove("online")
  document.getElementById("network-icon").textContent = "📡"
  document.getElementById("network-text").textContent = "You are offline"
  networkStatus.classList.remove("hidden")

  showMessage("You are offline. Some features may not work 📡", "error", 4000)
})

// Wallpaper Modal Functions
function openWallpaperModal(filename, title, category, downloads, wallpaperId) {
  const modal = document.getElementById("wallpaper-modal")
  const modalImage = document.getElementById("modal-wallpaper-image")
  const modalTitle = document.getElementById("modal-wallpaper-title")
  const modalCategory = document.getElementById("modal-category")
  const modalDownloads = document.getElementById("modal-downloads")
  const modalDownloadBtn = document.getElementById("modal-download-btn")
  const modalLoading = document.querySelector(".modal-loading")

  // Show modal with blur effect
  modal.classList.remove("hidden")
  document.body.classList.add("modal-open")

  // Show loading state
  modalLoading.style.display = "flex"
  modalImage.style.display = "none"

  // Set modal content
  modalTitle.textContent = title
  modalCategory.textContent = category
  modalCategory.className = `category-tag category-${category}`
  modalDownloads.textContent = `${Number.parseInt(downloads).toLocaleString()} downloads`

  // Set download button action
  modalDownloadBtn.onclick = () => {
    handleDownload(filename, title, wallpaperId)
    closeWallpaperModal()
  }

  // Load image
  const img = new Image()
  img.crossOrigin = "anonymous"
  img.onload = () => {
    modalImage.src = img.src
    modalImage.alt = title
    modalLoading.style.display = "none"
    modalImage.style.display = "block"
    modalImage.classList.add("image-loaded")

    showToast(`${title} loaded! 🖼️`, "success", 2000)
  }

  img.onerror = () => {
    modalLoading.style.display = "none"
    showMessage("Failed to load wallpaper image 😞", "error", 3000)
  }

  img.src = `/static/wallpapers/${filename}`

  showMessage(`Opening ${title} preview 🖼️`, "info", 2000)
}

function closeWallpaperModal() {
  const modal = document.getElementById("wallpaper-modal")
  const modalImage = document.getElementById("modal-wallpaper-image")

  modal.classList.add("hidden")
  document.body.classList.remove("modal-open")
  modalImage.classList.remove("image-loaded")

  showToast("Preview closed 👋", "info", 1500)
}

// Close modal on Escape key
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const modal = document.getElementById("wallpaper-modal")
    if (!modal.classList.contains("hidden")) {
      closeWallpaperModal()
    }

    // Close Instagram modal too
    const instagramModal = document.querySelector(".instagram-modal")
    if (instagramModal) {
      closeInstagramModal()
    }
  }
})

// Wallpaper Modal Event Listeners
document.addEventListener("DOMContentLoaded", () => {
  // Add click listeners to all wallpaper preview images
  document.addEventListener("click", (e) => {
    if (e.target.classList.contains("wallpaper-preview-img")) {
      const filename = e.target.dataset.filename
      const title = e.target.dataset.title
      const category = e.target.dataset.category
      const downloads = e.target.dataset.downloads
      const wallpaperId = e.target.dataset.id

      openWallpaperModal(filename, title, category, downloads, wallpaperId)
    }
  })

  // Add click listeners to all download buttons
  document.addEventListener("click", (e) => {
    if (e.target.classList.contains("wallpaper-download-btn")) {
      e.stopPropagation() // Prevent modal from opening
      const filename = e.target.dataset.filename
      const title = e.target.dataset.title
      const wallpaperId = e.target.dataset.id

      handleDownload(filename, title, wallpaperId)
    }
  })
})
