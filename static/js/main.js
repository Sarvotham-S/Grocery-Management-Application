/**
 * FreshMart - Main Interactive Client JavaScript
 * Handles AJAX cart operations, live search, filtering, toasts, and checkout interactions
 */

document.addEventListener('DOMContentLoaded', function () {
  // 1. Initialize live cart count badge
  updateLiveCartCount();

  // 2. Setup auto-dismiss for flash alerts after 3 seconds
  initAutoDismissAlerts();

  // 3. Setup client-side search filtering if search input exists
  initProductSearch();

  // 4. Setup payment method selector toggles on checkout
  initPaymentMethodSelector();

  // 5. Setup demo credential quick-fill helpers
  initDemoCredentials();
});

/* --------------------------------------------------------------------------
   Toast Notification System
   -------------------------------------------------------------------------- */
function showToast(message, type = 'success') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container-custom';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  const typeClass = type === 'danger' || type === 'error' ? 'toast-error' : (type === 'info' ? 'toast-info' : '');
  const icon = type === 'danger' || type === 'error'
    ? '<i class="fa-solid fa-circle-exclamation text-danger me-2"></i>'
    : (type === 'info' ? '<i class="fa-solid fa-circle-info text-info me-2"></i>' : '<i class="fa-solid fa-circle-check text-success me-2"></i>');

  toast.className = `fresh-toast ${typeClass}`;
  toast.innerHTML = `
    <div class="d-flex align-items-center">
      ${icon}
      <span style="font-size: 0.92rem; font-weight: 500;">${message}</span>
    </div>
    <button type="button" class="btn-close ms-3" style="font-size: 0.75rem;" aria-label="Close"></button>
  `;

  const closeBtn = toast.querySelector('.btn-close');
  closeBtn.addEventListener('click', () => {
    toast.remove();
  });

  container.appendChild(toast);

  // Auto remove after 3.5 seconds
  setTimeout(() => {
    toast.style.transition = 'all 0.3s ease';
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(40px)';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* --------------------------------------------------------------------------
   Cart Badge Functions
   -------------------------------------------------------------------------- */
function updateLiveCartCount() {
  fetch('/cart/count', {
    headers: { 'Accept': 'application/json' }
  })
    .then(response => {
      if (response.ok) return response.json();
      return null;
    })
    .then(data => {
      if (data && typeof data.count !== 'undefined') {
        setCartBadge(data.count);
      }
    })
    .catch(err => console.debug('Live cart count fetch omitted for guest/offline.'));
}

function setCartBadge(count) {
  const badges = document.querySelectorAll('.cart-badge');
  badges.forEach(badge => {
    badge.textContent = count;
    if (count > 0) {
      badge.style.display = 'inline-block';
      badge.classList.remove('pop');
      void badge.offsetWidth; // Trigger reflow
      badge.classList.add('pop');
    } else {
      badge.textContent = '0';
    }
  });
}

/* --------------------------------------------------------------------------
   Add To Cart (AJAX)
   -------------------------------------------------------------------------- */
function addToCart(productId, buttonElement) {
  if (!productId) return;

  const originalContent = buttonElement ? buttonElement.innerHTML : '';
  if (buttonElement) {
    buttonElement.disabled = true;
    buttonElement.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-1"></i> Adding...';
  }

  fetch(`/cart/add/${productId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
    .then(async response => {
      // If user redirected to login or unauthorized
      if (response.redirected || response.status === 401) {
        window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
        return;
      }
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.message || 'Could not add to cart.');
      }
      return data;
    })
    .then(data => {
      if (!data) return;
      if (data.success) {
        showToast(data.message, 'success');
        setCartBadge(data.cart_count);
      } else {
        showToast(data.message || 'Unable to add item.', 'error');
      }
    })
    .catch(error => {
      showToast(error.message || 'Error adding item to cart. Please sign in.', 'error');
    })
    .finally(() => {
      if (buttonElement) {
        buttonElement.disabled = false;
        buttonElement.innerHTML = originalContent;
      }
    });
}

/* --------------------------------------------------------------------------
   Update Cart Quantity (AJAX)
   -------------------------------------------------------------------------- */
function updateCartQty(productId, newQty) {
  if (newQty < 0) return;

  const row = document.getElementById(`cart-row-${productId}`);
  const qtyDisplay = document.getElementById(`qty-val-${productId}`);

  fetch(`/cart/update/${productId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest'
    },
    body: JSON.stringify({ quantity: newQty })
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        setCartBadge(data.cart_count);

        if (data.new_qty === 0) {
          // Row was removed
          if (row) {
            row.style.transition = 'all 0.3s ease';
            row.style.opacity = '0';
            row.style.transform = 'scale(0.95)';
            setTimeout(() => {
              row.remove();
              checkEmptyCartState(data.cart_count);
            }, 300);
          }
        } else {
          // Update item row subtotal
          if (qtyDisplay) qtyDisplay.textContent = data.new_qty;
          const itemTotalElem = document.getElementById(`item-total-${productId}`);
          if (itemTotalElem) {
            itemTotalElem.textContent = `₹${data.item_subtotal.toFixed(2)}`;
          }
        }

        // Update overall summary elements
        renderOrderSummary(data);
      } else {
        showToast(data.message || 'Could not update quantity.', 'error');
      }
    })
    .catch(err => {
      showToast('Error updating item quantity.', 'error');
      console.error(err);
    });
}

/* --------------------------------------------------------------------------
   Remove Cart Item (AJAX)
   -------------------------------------------------------------------------- */
function removeFromCart(productId) {
  if (!confirm('Are you sure you want to remove this item from your cart?')) return;

  const row = document.getElementById(`cart-row-${productId}`);

  fetch(`/cart/remove/${productId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        showToast(data.message, 'info');
        setCartBadge(data.cart_count);

        if (row) {
          row.style.transition = 'all 0.3s ease';
          row.style.opacity = '0';
          row.style.transform = 'scale(0.95)';
          setTimeout(() => {
            row.remove();
            checkEmptyCartState(data.cart_count);
          }, 300);
        }

        renderOrderSummary(data);
      } else {
        showToast(data.message || 'Could not remove item.', 'error');
      }
    })
    .catch(err => {
      showToast('Error removing item from cart.', 'error');
      console.error(err);
    });
}

/* --------------------------------------------------------------------------
   Render Order Summary Updates
   -------------------------------------------------------------------------- */
function renderOrderSummary(totals) {
  const subtotalElem = document.getElementById('summary-subtotal');
  const deliveryElem = document.getElementById('summary-delivery');
  const gstElem = document.getElementById('summary-gst');
  const totalElem = document.getElementById('summary-total');

  if (subtotalElem) subtotalElem.textContent = `₹${totals.subtotal.toFixed(2)}`;
  if (deliveryElem) {
    if (totals.delivery_fee === 0) {
      deliveryElem.innerHTML = '<span class="delivery-free-tag">FREE</span>';
    } else {
      deliveryElem.textContent = `₹${totals.delivery_fee.toFixed(2)}`;
    }
  }
  if (gstElem) gstElem.textContent = `₹${totals.gst.toFixed(2)}`;
  if (totalElem) totalElem.textContent = `₹${totals.total.toFixed(2)}`;
}

function checkEmptyCartState(cartCount) {
  if (cartCount === 0) {
    const tableContainer = document.getElementById('cartTableContainer');
    const summaryCard = document.getElementById('cartSummaryCard');
    const emptyState = document.getElementById('cartEmptyState');

    if (tableContainer) tableContainer.style.display = 'none';
    if (summaryCard) summaryCard.style.display = 'none';
    if (emptyState) emptyState.style.display = 'block';
  }
}

/* --------------------------------------------------------------------------
   Product Search & Category Filter (Client-side fast filter)
   -------------------------------------------------------------------------- */
function initProductSearch() {
  const searchInput = document.getElementById('searchInput');
  if (!searchInput) return;

  const productCards = document.querySelectorAll('.product-card');
  const noMatchBox = document.getElementById('noProductsMatch');

  searchInput.addEventListener('input', function (e) {
    const query = e.target.value.toLowerCase().trim();
    let visibleCount = 0;

    productCards.forEach(card => {
      const name = (card.getAttribute('data-name') || '').toLowerCase();
      const desc = (card.getAttribute('data-desc') || '').toLowerCase();
      const category = (card.getAttribute('data-category') || '').toLowerCase();

      if (name.includes(query) || desc.includes(query) || category.includes(query)) {
        card.closest('.product-col') ? card.closest('.product-col').style.display = '' : card.style.display = '';
        visibleCount++;
      } else {
        card.closest('.product-col') ? card.closest('.product-col').style.display = 'none' : card.style.display = 'none';
      }
    });

    if (noMatchBox) {
      noMatchBox.style.display = visibleCount === 0 ? 'block' : 'none';
    }
  });
}

/* --------------------------------------------------------------------------
   Payment Method Toggle in Checkout
   -------------------------------------------------------------------------- */
function initPaymentMethodSelector() {
  const options = document.querySelectorAll('.payment-card-option');
  if (!options.length) return;

  options.forEach(opt => {
    opt.addEventListener('click', function () {
      options.forEach(o => o.classList.remove('selected'));
      this.classList.add('selected');

      const radio = this.querySelector('input[type="radio"]');
      if (radio) {
        radio.checked = true;
        const method = radio.value;

        // Toggle payment details containers
        document.querySelectorAll('.payment-details-pane').forEach(p => p.classList.remove('active'));
        const activePane = document.getElementById(`pane-${method}`);
        if (activePane) {
          activePane.classList.add('active');
        }
      }
    });
  });
}

/* --------------------------------------------------------------------------
   Auto-Dismiss Flash Alerts
   -------------------------------------------------------------------------- */
function initAutoDismissAlerts() {
  const alerts = document.querySelectorAll('.alert-auto-dismiss');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'all 0.5s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-10px)';
      setTimeout(() => alert.remove(), 500);
    }, 3000);
  });
}

/* --------------------------------------------------------------------------
   Demo Credentials Quick-Fill (Login Page)
   -------------------------------------------------------------------------- */
function initDemoCredentials() {
  window.fillDemoLogin = function (username, password) {
    const userField = document.getElementById('username');
    const passField = document.getElementById('password');
    if (userField && passField) {
      userField.value = username;
      passField.value = password;
      showToast(`Filled credentials for: ${username}`, 'info');
    }
  };
}

/* --------------------------------------------------------------------------
   Delete Confirmation Helper
   -------------------------------------------------------------------------- */
function confirmItemDelete(productName) {
  return confirm(`Are you sure you want to remove "${productName}" from the store catalog? This action cannot be undone.`);
}
