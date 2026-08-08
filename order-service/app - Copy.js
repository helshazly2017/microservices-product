const ORDER_API = 'http://127.0.0.1:8002';
const PRODUCT_API = 'http://127.0.0.1:8001';

// Wait until the browser completely loads the HTML elements before running logic
document.addEventListener('DOMContentLoaded', () => {
    const orderForm = document.getElementById('orderForm');
    const statusMessage = document.getElementById('statusMessage');
    const productGrid = document.getElementById('productGrid');
    const catalogLoading = document.getElementById('catalogLoading');
    const syncBtn = document.getElementById('syncBtn');
    const productIdInput = document.getElementById('productId');

    function showStatus(text, isError = false) {
        statusMessage.innerText = text;
        statusMessage.className = `status ${isError ? 'error' : 'success'}`;
        statusMessage.style.display = 'block';
    }

    // Fetch and dynamically display products directly from the PostgreSQL backend
    async function fetchProductCatalog() {
        try {
            const response = await fetch(`${PRODUCT_API}/debug/db-entries`);
            if (!response.ok) throw new Error('Could not reach Product Service database layer');

            const data = await response.json();
            const products = data.records || [];

            productGrid.innerHTML = '';
            catalogLoading.style.display = 'none';

            if (products.length === 0) {
                productGrid.innerHTML = '<div style="grid-column: 1/-1; color: #64748b;">No products found in the database.</div>';
                return;
            }

            products.forEach(prod => {
                const div = document.createElement('div');
                div.className = `product-item ${!prod.in_stock ? 'out-of-stock' : ''}`;

                // Render internal layout details
                div.innerHTML = `
                    <div class="product-id">ID: ${prod.id}</div>
                    <div class="product-name">${prod.name}</div>
                    <div class="product-price">$${prod.price.toFixed(2)}</div>
                    <div style="font-size: 11px; margin-top: 4px; color: ${prod.in_stock ? '#16a34a' : '#dc2626'}">
                        ${prod.in_stock ? '● In Stock' : '○ Out of Stock'}
                    </div>
                `;

                // NEW: Make item clickable to auto-fill the order form selection
                div.addEventListener('click', () => {
                    productIdInput.value = prod.id;
                    // Optional visual confirmation cue
                    productIdInput.focus();
                });

                productGrid.appendChild(div);
            });
        } catch (error) {
            catalogLoading.innerText = 'Error loading system inventory details.';
            catalogLoading.style.color = '#dc2626';
        }
    }

    // POST Request to submit an order
    orderForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        statusMessage.style.display = 'none';

        const payload = {
            product_id: parseInt(productIdInput.value),
            quantity: parseInt(document.getElementById('quantity').value)
        };

        try {
            const response = await fetch(`${ORDER_API}/orders/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || 'Failed to place order');

            showStatus(`Success! Order verified and placed for product ID ${result.product_id}.`);
            orderForm.reset();
            document.getElementById('quantity').value = 1;
        } catch (error) {
            showStatus(error.message, true);
        }
    });

    // Manual layout shortcut button triggers background cache synchronizer
    syncBtn.addEventListener('click', async () => {
        try {
            syncBtn.innerText = 'Syncing...';
            const response = await fetch(`${ORDER_API}/orders/sync-inventory/`, { method: 'POST' });
            const result = await response.json();

            if (response.ok) {
                alert(`Sync Complete! Loaded ${result.synced_products_count} entries into memory.`);
                // Refresh catalog grid instantly if data structures changed
                fetchProductCatalog();
            } else {
                alert(`Sync Failed: ${result.detail}`);
            }
        } catch (e) {
            alert('Connection failure trying to reach sync engine.');
        } finally {
            syncBtn.innerText = 'Sync Local Order Memory Cache';
        }
    });
   }

// Bootstrap active database pulling routines right when UI renders
document.addEventListener('DOMContentLoaded', fetchProductCatalog);
