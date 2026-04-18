document.addEventListener('DOMContentLoaded', () => {
    // --- State Management ---
    let state = {
        isLoggedIn: JSON.parse(localStorage.getItem('isLoggedIn')) || false,
        currentUser: JSON.parse(localStorage.getItem('currentUser')) || null,
        users: JSON.parse(localStorage.getItem('users')) || [],
        products: JSON.parse(localStorage.getItem('products')) || [],
        tempImage: null,
        editingProductIndex: -1,
        currentSort: 'recent', // recent, price-asc, price-desc
        currentView: 4 // 2, 4, 6
    };

    // --- DOM Elements ---
    const navActions = document.getElementById('navActions');
    const userActions = document.getElementById('userActions');
    const loginBtn = document.getElementById('loginBtn');
    const signupBtn = document.getElementById('signupBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const avatarBtn = document.getElementById('avatarBtn');
    const avatarMenu = document.getElementById('avatarMenu');
    const avatarInitials = document.getElementById('avatarInitials');
    const avatarMenuEmail = document.getElementById('avatarMenuEmail');
    const avatarMenuName = document.getElementById('avatarMenuName');
    const avatarMenuBadge = document.getElementById('avatarMenuBadge');
    const addProductBtn = document.getElementById('addProductBtn');
    const heroStartBtn = document.getElementById('heroStartBtn');

    const landingPage = document.getElementById('landingPage');
    const featuresSection = document.getElementById('features');
    const dashboard = document.getElementById('dashboard');
    const productGrid = document.getElementById('productGrid');
    const productCount = document.getElementById('productCount');
    const navHome = document.getElementById('navHome');

    // Modals
    const modalOverlay = document.getElementById('modalOverlay');
    const loginModal = document.getElementById('loginModal');
    const signupModal = document.getElementById('signupModal');
    const detailModal = document.getElementById('detailModal');

    // Detail UI Elements
    const detailTitle = document.getElementById('detailTitle');
    const detailPrice = document.getElementById('detailPrice');
    const detailDesc = document.getElementById('detailDesc');
    const detailVisual = document.getElementById('detailVisual');
    const detailUrl = document.getElementById('detailUrl');
    const editProductBtn = document.getElementById('editProductBtn');
    const deleteProductBtn = document.getElementById('deleteProductBtn');

    // Forms
    const productForm = document.getElementById('productForm');
    const loginForm = document.getElementById('loginForm');
    const signupForm = document.getElementById('signupForm');

    // --- Core Functions ---

    function getInitials(user) {
        if (!user) return 'U';
        const first = (user.name || '').charAt(0).toUpperCase();
        const last = (user.surname || '').charAt(0).toUpperCase();
        return (first + last) || first || 'U';
    }

    function updateAvatarUI() {
        if (!state.currentUser) return;
        const initials = getInitials(state.currentUser);
        const fullName = `${state.currentUser.name || ''} ${state.currentUser.surname || ''}`.trim();
        if (avatarInitials) avatarInitials.textContent = initials;
        if (avatarMenuBadge) avatarMenuBadge.textContent = initials;
        if (avatarMenuEmail) avatarMenuEmail.textContent = state.currentUser.email || '';
        if (avatarMenuName) avatarMenuName.textContent = fullName || 'Kullanıcı';
    }

    function updateUI() {
        if (state.isLoggedIn && state.currentUser) {
            navActions.classList.add('hidden');
            userActions.classList.remove('hidden');
            landingPage.classList.add('hidden');
            if (featuresSection) featuresSection.classList.add('hidden');
            dashboard.classList.remove('hidden');
            updateAvatarUI();
            renderProducts();
        } else {
            navActions.classList.remove('hidden');
            userActions.classList.add('hidden');
            landingPage.classList.remove('hidden');
            if (featuresSection) featuresSection.classList.remove('hidden');
            dashboard.classList.add('hidden');
        }
    }
    function renderProducts() {
        productGrid.innerHTML = '';
        const userProducts = state.products.filter(p => p.userId === state.currentUser.email);

        // Sorting logic
        let sortedProducts = [...userProducts];
        if (state.currentSort === 'price-asc') {
            sortedProducts.sort((a, b) => parsePrice(a.botPrice) - parsePrice(b.botPrice));
        } else if (state.currentSort === 'price-desc') {
            sortedProducts.sort((a, b) => parsePrice(b.botPrice) - parsePrice(a.botPrice));
        } else {
            sortedProducts.sort((a, b) => b.timestamp - a.timestamp);
        }

        // Apply grid view class
        productGrid.className = `product-grid grid-${state.currentView}`;

        sortedProducts.forEach((product, index) => {
            const card = document.createElement('div');
            card.className = 'product-card';

            let imgHtml = '';
            if (product.image) {
                imgHtml = `<div class="product-img" style="background-image: url('${product.image}')"></div>`;
            } else if (product.link) {
                // Show branded card with site favicon and domain when no image is available
                let domain = '';
                try { domain = new URL(product.link).hostname; } catch (e) { }
                const faviconUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=64`;
                imgHtml = `<div class="product-img" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px;">
                                <img src="${faviconUrl}" style="width:48px; height:48px; border-radius:8px; background:white; padding:4px;" onerror="this.style.display='none'">
                                <span style="color:white; font-size:11px; font-weight:600; opacity:0.9; max-width:90%; text-align:center; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${domain}</span>
                           </div>`;
            } else {
                imgHtml = `<div class="product-img">
                                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                                    <circle cx="8.5" cy="8.5" r="1.5"/>
                                    <polyline points="21 15 16 10 5 21"/>
                                </svg>
                           </div>`;
            }
            // Price/Link logic
            const hasRealPrice = product.botPrice && product.botPrice !== 'Fiyat bulunamadı.' && product.botPrice.match(/\d/);
            const priceHtml = hasRealPrice ?
                `<span class="product-price">${product.botPrice.toString().startsWith('₺') ? product.botPrice : '₺' + product.botPrice}</span>` :
                `<span class="product-price" style="color: #94a3b8; font-weight:400; font-size: 0.8rem;">Fiyat bulunamadı.</span>`;

            const linkTag = product.link ?
                `<a href="${product.link}" target="_blank" class="product-link">Görüntüle</a>` :
                '';

            card.innerHTML = `
                <div class="product-top">
                    ${imgHtml}
                </div>
                <div class="product-info">
                    <h3 class="product-title">${product.title}</h3>
                    <p class="product-desc">${product.description || 'Açıklama belirtilmedi.'}</p>
                    <div class="product-footer">
                        ${priceHtml}
                        ${linkTag}
                    </div>
                </div>
            `;

            card.onclick = (e) => {
                // Ignore clicks on product links or their children
                if (e.target.closest('.product-link')) return;

                const originalIdx = state.products.indexOf(product);
                if (originalIdx !== -1) {
                    openProductDetail(originalIdx);
                }
            };

            productGrid.appendChild(card);
        });

        productCount.textContent = `${userProducts.length} ürün`;
    }

    function parsePrice(priceStr) {
        if (!priceStr || typeof priceStr !== 'string') return 0;
        const cleaned = priceStr.replace(/[^\d.,]/g, '').replace('.', '').replace(',', '.');
        return parseFloat(cleaned) || 0;
    }

    // --- Modal Helpers ---
    function closeAllModals() {
        [modalOverlay, loginModal, signupModal, detailModal, document.getElementById('confirmDeleteModal')].forEach(m => {
            if (m) m.classList.add('hidden');
        });
        state.editingProductIndex = -1;
        modalOverlay.querySelector('h3').textContent = 'Yeni Ürün Ekle';
    }

    document.querySelectorAll('.close-modal, #cancelBtn').forEach(btn => {
        btn.addEventListener('click', closeAllModals);
    });

    // --- Auth Logic ---

    // Signup submission
    document.getElementById('submitSignup').addEventListener('click', () => {
        const name = document.getElementById('name').value;
        const surname = document.getElementById('surname').value;
        const email = document.getElementById('signupEmail').value;
        const password = document.getElementById('signupPass').value;

        if (!name || !surname || !email || !password) {
            alert('Lütfen tüm alanları doldurun.');
            return;
        }

        if (state.users.find(u => u.email === email)) {
            alert('Bu e-posta adresi zaten kayıtlı.');
            return;
        }

        const newUser = { name, surname, email, password };
        state.users.push(newUser);
        localStorage.setItem('users', JSON.stringify(state.users));

        // Auto login after signup
        state.isLoggedIn = true;
        state.currentUser = newUser;
        localStorage.setItem('isLoggedIn', 'true');
        localStorage.setItem('currentUser', JSON.stringify(newUser));

        closeAllModals();
        updateUI();
        alert(`Hoş geldin, ${name}!`);
    });

    // Login submission
    document.getElementById('submitLogin').addEventListener('click', () => {
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPass').value;

        const user = state.users.find(u => u.email === email && u.password === password);

        if (user) {
            state.isLoggedIn = true;
            state.currentUser = user;
            localStorage.setItem('isLoggedIn', 'true');
            localStorage.setItem('currentUser', JSON.stringify(user));
            closeAllModals();
            updateUI();
        } else {
            alert('Hatalı e-posta veya şifre.');
        }
    });

    // Opening modals
    loginBtn.addEventListener('click', () => {
        loginModal.classList.remove('hidden');
    });

    signupBtn.addEventListener('click', () => {
        signupModal.classList.remove('hidden');
    });

    heroStartBtn.addEventListener('click', () => {
        signupModal.classList.remove('hidden');
    });

    // ── Avatar dropdown toggle ──
    if (avatarBtn && avatarMenu) {
        avatarBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            avatarMenu.classList.toggle('hidden');
        });
    }

    logoutBtn.addEventListener('click', () => {
        if (avatarMenu) avatarMenu.classList.add('hidden');
        state.isLoggedIn = false;
        state.currentUser = null;
        localStorage.setItem('isLoggedIn', 'false');
        localStorage.removeItem('currentUser');
        updateUI();
    });

    if (navHome) {
        navHome.addEventListener('click', (e) => {
            e.preventDefault();
            if (state.isLoggedIn) {
                // If logged in, maybe we still want to see landing page? 
                // Usually "Home" for a logged in user goes to dashboard, 
                // but user requested features only on front page.
                // Let's allow them to see it if they click Home.
                landingPage.classList.remove('hidden');
                if (featuresSection) featuresSection.classList.remove('hidden');
                dashboard.classList.add('hidden');
            } else {
                updateUI();
            }
        });
    }

    // --- Product Logic ---

    addProductBtn.addEventListener('click', () => {
        modalOverlay.classList.remove('hidden');
        productForm.reset();
        document.getElementById('fileName').textContent = '';
        state.tempImage = null;
    });

    // File Upload Handling
    document.getElementById('dropZone').addEventListener('click', () => document.getElementById('fileInput').click());

    document.getElementById('fileInput').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            document.getElementById('fileName').textContent = file.name;
            const reader = new FileReader();
            reader.onload = (event) => {
                state.tempImage = event.target.result;
            };
            reader.readAsDataURL(file);
        }
    });

    function openProductDetail(index) {
        const product = state.products[index];
        state.editingProductIndex = index;

        const priceToShow = product.botPrice || 'Fiyat bulunamadı.';
        const hasPrice = priceToShow !== 'Fiyat bulunamadı.' && priceToShow.match(/\d/);
        detailPrice.textContent = hasPrice ? (priceToShow.startsWith('₺') ? priceToShow : '₺' + priceToShow) : 'Fiyat bulunamadı.';
        detailDesc.textContent = product.description || 'Açıklama belirtilmedi.';
        detailUrl.href = product.link || '#';
        detailUrl.style.display = product.link ? 'block' : 'none';

        if (product.image) {
            detailVisual.style.backgroundImage = `url(${product.image})`;
            detailVisual.innerHTML = '';
        } else {
            detailVisual.style.backgroundImage = 'none';
            detailVisual.innerHTML = `
                <div style="height: 100%; display: flex; align-items: center; justify-content: center; color: #94a3b8;">
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                        <circle cx="8.5" cy="8.5" r="1.5"/>
                        <polyline points="21 15 16 10 5 21"/>
                    </svg>
                </div>`;
        }

        detailModal.classList.remove('hidden');
    }

    deleteProductBtn.addEventListener('click', () => {
        detailModal.classList.add('hidden');
        document.getElementById('confirmDeleteModal').classList.remove('hidden');
    });

    document.getElementById('confirmDeleteBtn').addEventListener('click', () => {
        if (state.editingProductIndex !== -1) {
            state.products.splice(state.editingProductIndex, 1);
            localStorage.setItem('products', JSON.stringify(state.products));
            closeAllModals();
            renderProducts();
        }
    });

    editProductBtn.addEventListener('click', () => {
        const product = state.products[state.editingProductIndex];

        // Fill the add product form with current data
        document.getElementById('title').value = product.title;
        document.getElementById('link').value = product.link || '';
        document.getElementById('description').value = product.description || '';
        document.getElementById('manualPrice').value = product.botPrice || '';
        state.tempImage = product.image;

        fileName.textContent = product.image ? 'Görsel yüklendi' : '';

        // Change modal title for editing context
        modalOverlay.querySelector('h3').textContent = 'Ürünü Düzenle';

        detailModal.classList.add('hidden');
        modalOverlay.classList.remove('hidden');
    });

    document.getElementById('saveBtn').addEventListener('click', async () => {
        const titleInput = document.getElementById('title');
        const linkInput = document.getElementById('link');
        const descInput = document.getElementById('description');
        const priceInput = document.getElementById('manualPrice');

        const title = titleInput.value;
        const link = linkInput.value;
        const description = descInput.value;
        const manualPrice = priceInput.value.trim();

        if (!title.trim()) {
            alert('Lütfen ürün başlığını doldurun.');
            return;
        }

        let botPrice = manualPrice || "Fiyat bulunamadı.";
        let finalTitle = title;
        let saveBtnOriginalText = saveBtn.textContent;

        const isEditing = state.editingProductIndex !== -1;
        const oldProduct = isEditing ? state.products[state.editingProductIndex] : null;

        // Only re-scrape if link changed or if it's a new product with a link
        const shouldScrape = link && (!isEditing || link !== oldProduct.link);

        if (shouldScrape) {
            saveBtn.textContent = 'Kaydediliyor...';
            saveBtn.disabled = true;



            // ── Backend API üzerinden fiyat çek ──────────────────────────
            let fetchedOk = false;
            try {
                const apiUrl = `http://localhost:8000/price?url=${encodeURIComponent(link)}`;
                const controller = new AbortController();
                const timeout = setTimeout(() => controller.abort(), 30000);
                const response = await fetch(apiUrl, { signal: controller.signal });
                clearTimeout(timeout);

                if (response.ok) {
                    const data = await response.json();
                    if (data.ok && data.price_text) {
                        // Backend'in döndürdüğü fiyatı kullan
                        const priceNum = data.price_value;
                        if (priceNum && priceNum > 0) {
                            botPrice = priceNum.toLocaleString('tr-TR', {
                                minimumFractionDigits: 2,
                                maximumFractionDigits: 2
                            }) + ' ₺';
                            fetchedOk = true;
                        }
                        // Backend'den başlık geldiyse ürün adı olarak kullan
                        if (data.title && !title.trim()) {
                            finalTitle = data.title;
                        }
                    }
                }
            } catch (e) {
                // Backend erişilemez durumdaysa sessizce geç
                console.warn('Backend API erişilemedi:', e);
            }

            if (!fetchedOk && !manualPrice) {
                botPrice = 'Fiyat bulunamadı.';
            }
        } else if (isEditing) {
            botPrice = oldProduct.botPrice;
        }

        const productData = {
            userId: state.currentUser.email,
            title: finalTitle,
            link,
            description,
            image: state.tempImage,
            botPrice,
            timestamp: isEditing ? oldProduct.timestamp : Date.now()
        };

        if (isEditing) {
            state.products[state.editingProductIndex] = productData;
        } else {
            state.products.push(productData);
        }

        localStorage.setItem('products', JSON.stringify(state.products));

        saveBtn.textContent = saveBtnOriginalText;
        saveBtn.disabled = false;

        renderProducts();
        closeAllModals();
        state.editingProductIndex = -1; // Reset editing state
    });

    // --- Dashboard Controls Logic ---
    const sortBtn = document.getElementById('sortBtn');
    const viewBtn = document.getElementById('viewBtn');
    const sortMenu = document.getElementById('sortMenu');
    const viewMenu = document.getElementById('viewMenu');

    sortBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        sortBtn.parentElement.classList.toggle('active');
        viewBtn.parentElement.classList.remove('active');
    });

    viewBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        viewBtn.parentElement.classList.toggle('active');
        sortBtn.parentElement.classList.remove('active');
    });

    sortMenu.querySelectorAll('.menu-item').forEach(item => {
        item.addEventListener('click', () => {
            state.currentSort = item.dataset.sort;
            sortMenu.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            renderProducts();
            closeAllModals(); // Close dropdowns
        });
    });

    viewMenu.querySelectorAll('.menu-item').forEach(item => {
        item.addEventListener('click', () => {
            state.currentView = parseInt(item.dataset.view);
            viewMenu.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            renderProducts();
            closeAllModals(); // Close dropdowns
        });
    });

    document.addEventListener('click', () => {
        document.querySelectorAll('.dropdown-container').forEach(c => c.classList.remove('active'));
        // Avatar menüsünü dışarı tıklamada kapat
        if (avatarMenu && !avatarMenu.classList.contains('hidden')) {
            avatarMenu.classList.add('hidden');
        }
    });

    // Close on overlay click for the new modal
    document.getElementById('confirmDeleteModal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeAllModals();
    });

    // ══════════════════════════════════════
    //  Settings Modal
    // ══════════════════════════════════════
    const settingsOverlay      = document.getElementById('settingsOverlay');
    const settingsCloseBtn     = document.getElementById('settingsCloseBtn');
    const settingsNavItems     = document.querySelectorAll('.settings-nav-item');
    const settingsTabs         = document.querySelectorAll('.settings-tab');
    const saveAccountBtn       = document.getElementById('saveAccountBtn');
    const settingsName         = document.getElementById('settingsName');
    const settingsSurname      = document.getElementById('settingsSurname');
    const settingsEmail        = document.getElementById('settingsEmail');
    const settingsCurrentPass  = document.getElementById('settingsCurrentPass');
    const settingsNewPass      = document.getElementById('settingsNewPass');
    const settingsConfirmPass  = document.getElementById('settingsConfirmPass');
    const themeLightBtn        = document.getElementById('themeLightBtn');
    const themeDarkBtn         = document.getElementById('themeDarkBtn');

    // ── Open settings (Ayarlar) ──
    const settingsBtn = document.getElementById('settingsBtn');
    if (settingsBtn) {
        settingsBtn.addEventListener('click', () => {
            if (avatarMenu) avatarMenu.classList.add('hidden');
            openSettings('account');
        });
    }

    // ── Open settings on Kişiselleştirme tab from avatar menu ──
    const customizeBtn = document.getElementById('customizeBtn');
    if (customizeBtn) {
        customizeBtn.addEventListener('click', () => {
            if (avatarMenu) avatarMenu.classList.add('hidden');
            openSettings('personalization');
        });
    }

    function openSettings(tab = 'account') {
        // Pre-fill account fields with current user data
        if (state.currentUser) {
            settingsName.value     = state.currentUser.name    || '';
            settingsSurname.value  = state.currentUser.surname || '';
            settingsEmail.value    = state.currentUser.email   || '';
        }
        settingsCurrentPass.value = '';
        settingsNewPass.value     = '';
        settingsConfirmPass.value = '';

        // Sync theme toggle state
        const savedTheme = localStorage.getItem('theme') || 'light';
        syncThemeButtons(savedTheme);

        // Open on specified tab
        switchSettingsTab(tab);

        settingsOverlay.classList.remove('hidden');
    }

    function closeSettings() {
        settingsOverlay.classList.add('hidden');
    }

    settingsCloseBtn.addEventListener('click', closeSettings);

    // Close on backdrop click
    settingsOverlay.addEventListener('click', (e) => {
        if (e.target === settingsOverlay) closeSettings();
    });

    // ── Sidebar nav ──
    settingsNavItems.forEach(item => {
        item.addEventListener('click', () => {
            switchSettingsTab(item.dataset.tab);
        });
    });

    function switchSettingsTab(tabName) {
        settingsNavItems.forEach(i => i.classList.remove('active'));
        settingsTabs.forEach(t => t.classList.remove('active'));

        const activeNav = document.querySelector(`.settings-nav-item[data-tab="${tabName}"]`);
        const activeTab = tabName === 'account'
            ? document.getElementById('settingsTabAccount')
            : document.getElementById('settingsTabPersonalization');

        if (activeNav) activeNav.classList.add('active');
        if (activeTab) activeTab.classList.add('active');
    }

    // ── Save account info ──
    saveAccountBtn.addEventListener('click', () => {
        const newName    = settingsName.value.trim();
        const newSurname = settingsSurname.value.trim();
        const newEmail   = settingsEmail.value.trim();
        const curPass    = settingsCurrentPass.value;
        const newPass    = settingsNewPass.value;
        const confPass   = settingsConfirmPass.value;

        if (!newName || !newSurname || !newEmail) {
            showSettingsToast('Ad, soyad ve e-posta zorunludur.', 'error');
            return;
        }

        // Password change requested?
        if (curPass || newPass || confPass) {
            if (curPass !== state.currentUser.password) {
                showSettingsToast('Mevcut şifre hatalı.', 'error');
                return;
            }
            if (newPass.length < 6) {
                showSettingsToast('Yeni şifre en az 6 karakter olmalıdır.', 'error');
                return;
            }
            if (newPass !== confPass) {
                showSettingsToast('Yeni şifreler eşleşmiyor.', 'error');
                return;
            }
        }

        // Check email uniqueness (skip for self)
        const emailConflict = state.users.find(
            u => u.email === newEmail && u.email !== state.currentUser.email
        );
        if (emailConflict) {
            showSettingsToast('Bu e-posta başka bir hesaba ait.', 'error');
            return;
        }

        // Apply changes
        const oldEmail = state.currentUser.email;
        state.currentUser.name    = newName;
        state.currentUser.surname = newSurname;
        state.currentUser.email   = newEmail;
        if (newPass) state.currentUser.password = newPass;

        // Update users array
        const idx = state.users.findIndex(u => u.email === oldEmail);
        if (idx !== -1) state.users[idx] = { ...state.currentUser };

        // Migrate products to new email key if email changed
        if (oldEmail !== newEmail) {
            state.products = state.products.map(p =>
                p.userId === oldEmail ? { ...p, userId: newEmail } : p
            );
            localStorage.setItem('products', JSON.stringify(state.products));
        }

        localStorage.setItem('users', JSON.stringify(state.users));
        localStorage.setItem('currentUser', JSON.stringify(state.currentUser));

        updateAvatarUI();
        settingsCurrentPass.value = '';
        settingsNewPass.value     = '';
        settingsConfirmPass.value = '';

        showSettingsToast('Değişiklikler kaydedildi!', 'success');
    });

    // ── Theme toggle ──
    function applyTheme(theme) {
        if (theme === 'dark') {
            document.body.classList.add('dark-theme');
        } else {
            document.body.classList.remove('dark-theme');
        }
        localStorage.setItem('theme', theme);
        syncThemeButtons(theme);
    }

    function syncThemeButtons(theme) {
        themeLightBtn.classList.toggle('active', theme === 'light');
        themeDarkBtn.classList.toggle('active',  theme === 'dark');
    }

    themeLightBtn.addEventListener('click', () => applyTheme('light'));
    themeDarkBtn.addEventListener('click',  () => applyTheme('dark'));

    // ── Toast notification ──
    function showSettingsToast(message, type = 'success') {
        let toast = document.getElementById('settingsToast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'settingsToast';
            toast.style.cssText = `
                position: fixed; bottom: 2rem; left: 50%; transform: translateX(-50%);
                padding: 0.75rem 1.5rem; border-radius: 10px; font-size: 0.9rem;
                font-weight: 600; font-family: inherit; z-index: 9999;
                box-shadow: 0 8px 24px rgba(0,0,0,0.15);
                transition: opacity 0.3s; pointer-events: none;
            `;
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.style.background = type === 'success' ? '#22c55e' : '#ef4444';
        toast.style.color = 'white';
        toast.style.opacity = '1';
        clearTimeout(toast._timer);
        toast._timer = setTimeout(() => { toast.style.opacity = '0'; }, 3000);
    }

    // ── Restore theme on load ──
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);

    // Initialize
    updateUI();
});

