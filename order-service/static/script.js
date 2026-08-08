// Master client cart tracking state storage object
let cart = {};

document.addEventListener('DOMContentLoaded', async () => {
    // Bind Catalog UI targets
    const catalogItems = document.querySelectorAll('.catalog-item');
    const selectedTitle = document.getElementById('selected-title');
    const selectedDescription = document.getElementById('selected-description');
    const productGrid = document.getElementById('product-grid');

    // Bind Cart Drawer UI elements
    const cartItemsContainer = document.getElementById('cart-items');
    const cartCountElement = document.getElementById('cart-count');
    const checkoutBtn = document.getElementById('checkout-btn');

    // Run inventory data synchronization routine instantly on page mount
    try {
        const syncResponse = await fetch('/orders/sync-inventory/', { method: 'POST' });
        const syncData = await syncResponse.json();
        console.log("System stock synchronization complete:", syncData);
    } catch (e) {
        console.error("Automated database synchronization sequence failed:", e);
    }

    // Attach click event loops targeting your structural sidebar menu layers
    catalogItems.forEach(item => {
        item.addEventListener('click', async () => {
            catalogItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            const layerId = String(item.dataset.id);
            const layerName = item.textContent;

            selectedTitle.textContent = layerName;
            selectedDescription.textContent = `Displaying real-time database entries for ${layerName}.`;
            productGrid.innerHTML = '<p style="color: #64748b; font-size: 14px;">Querying database infrastructure layer...</p>';

            try {
                const response = await fetch(`/api/products?layer_id=${layerId}`);
                if (!response.ok) throw new Error("Server network path unavailable.");

                const items = await response.json();
                renderProducts(items);
            } catch(err) {
                console.error(err);
                productGrid.innerHTML = '<p style="color: #dc2626; font-size: 14px;">Error connecting to API microservice endpoint.</p>';
            }
        });
    });

    // Generate responsive product grid catalog layout blocks
    function renderProducts(items) {
        productGrid.innerHTML = '';

        if (!items || items.length === 0) {
            productGrid.innerHTML = '<p style="color: #94a3b8; font-size: 14px;">No configuration profiles matching this framework found in DB.</p>';
            return;
        }

        items.forEach(product => {
            const card = document.createElement('div');
            card.className = 'product-card';

            // Dynamic card style mutations depending on inventory statuses
            card.style = `border: 1px solid #e2e8f0; padding: 20px; border-radius: 8px; background: ${product.in_stock ? '#fff' : '#f8fafc'}; opacity: ${product.in_stock ? 1 : 0.6}; box-shadow: 0 1px 3px rgba(0,0,0,0.05);`;

            card.innerHTML = `
                <div style="font-size: 11px; color: #94a3b8; margin-bottom: 4px;">SKU: ${product.id}</div>
                <h3 style="margin: 0 0 8px 0; font-size: 1.05rem; color: #1e293b; font-weight: 600;">${product.name}</h3>
                <p style="font-weight: 700; color: #2563eb; margin: 0 0 15px 0;">$${product.price.toFixed(2)}/mo</p>
                <button class="add-to-cart-btn" style="width: 100%; background: ${product.in_stock ? '#2563eb' : '#94a3b8'}; color: #fff; border: none; padding: 10px 12px; border-radius: 6px; cursor: ${product.in_stock ? 'pointer' : 'not-allowed'}; font-weight: 500;" ${!product.in_stock ? 'disabled' : ''}>
                    ${product.in_stock ? 'Add to System Order' : 'Out of Stock'}
                </button>
            `;

            if (product.in_stock) {
                card.querySelector('.add-to-cart-btn').addEventListener('click', () => {
                    addToCart(product);
                });
            }
            productGrid.appendChild(card);
        });
    }

    // Cart modification state routers
    function addToCart(product) {
        const id = product.id;
        if (cart[id]) {
            cart[id].quantity += 1;
        } else {
            cart[id] = { id: product.id, name: product.name, price: product.price, quantity: 1 };
        }
        updateCartUI();
    }

    function changeQuantity(id, change) {
        if (!cart[id]) return;
        cart[id].quantity += change;
        if (cart[id].quantity <= 0) {
            delete cart[id];
        }
        updateCartUI();
    }

    // Refresh structural sidebar checkout container elements
    function updateCartUI() {
        const cartItems = Object.values(cart);

        let totalItemsCount = 0;
        let runningTotalPrice = 0;
        cartItems.forEach(item => {
            totalItemsCount += item.quantity;
            runningTotalPrice += (item.price * item.quantity);
        });

        cartCountElement.textContent = totalItemsCount;

        if (cartItems.length === 0) {
            cartItemsContainer.innerHTML = '<p class="empty-cart-msg" style="color: #94a3b8; text-align: center; padding: 20px 0; font-size: 13px;">Your cart is empty.</p>';
            checkoutBtn.disabled = true;
            return;
        }

        checkoutBtn.disabled = false;
        cartItemsContainer.innerHTML = '';

        cartItems.forEach(item => {
            const row = document.createElement('div');
            row.style = 'border-bottom: 1px solid #f1f5f9; padding: 12px 0; display: flex; flex-direction: column; gap: 4px;';
            row.innerHTML = `
                <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: 500; color: #334155;">
                    <span>${item.name}</span>
                    <span>$${(item.price * item.quantity).toFixed(2)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #64748b;">
                    <span>$${item.price.toFixed(2)} each</span>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <button class="qty-minus-btn" style="background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 6px; cursor: pointer; font-weight: bold;">-</button>
                        <span style="font-weight: 600; color: #1e293b;">${item.quantity}</span>
                        <button class="qty-plus-btn" style="background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 6px; cursor: pointer; font-weight: bold;">+</button>
                    </div>
                </div>
            `;

            row.querySelector('.qty-minus-btn').addEventListener('click', () => changeQuantity(item.id, -1));
            row.querySelector('.qty-plus-btn').addEventListener('click', () => changeQuantity(item.id, 1));
            cartItemsContainer.appendChild(row);
        });

        // Inject computed price summaries at the base of the list node stack
        const totalSummaryLine = document.createElement('div');
        totalSummaryLine.style = 'display: flex; justify-content: space-between; font-weight: 700; font-size: 14px; color: #1e293b; padding-top: 12px; margin-top: 4px; border-top: 2px dashed #e2e8f0;';
        totalSummaryLine.innerHTML = `<span>Estimated Total:</span><span>$${runningTotalPrice.toFixed(2)}</span>`;
        cartItemsContainer.appendChild(totalSummaryLine);
    }

    // Submit complete structured transaction array to your backend database mapping
    if (checkoutBtn) {
        checkoutBtn.addEventListener('click', async () => {
            const cartItems = Object.values(cart);
            const payload = {
                items: cartItems.map(item => ({
                    product_id: parseInt(item.id),
                    quantity: parseInt(item.quantity)
                }))
            };

            try {
                checkoutBtn.innerText = "Processing checkout tables...";
                checkoutBtn.disabled = true;

                const response = await fetch('/orders/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const result = await response.json();
                if (!response.ok) throw new Error(result.detail || "Checkout refused.");

                alert(`Order Verified! ${result.status} (PostgreSQL Tracking Index: #${result.order_id})`);
                cart = {};
                updateCartUI();
            } catch (err) {
                alert(`Order Placement Error: ${err.message}`);
            } finally {
                checkoutBtn.innerText = "Submit Order";
            }
        });
    }

    // FORCE INITIALIZATION: Automatically trigger a click on the first sidebar item to pull data on load
    if (catalogItems.length > 0) {
        console.log("Triggering initialization query sequence...");
        catalogItems[0].click();
    }
});
s