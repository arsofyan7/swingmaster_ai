// --- App Routing & Auth Globals ---
let activeUser = null;
let activePortfolio = null;
let portfolios = [];

// --- Global Data for Sorting ---
let currentData = [];
let currentSort = { key: '', asc: true };

// --- Theme Toggle ---
const htmlDoc = document.documentElement;
const themeIcon = document.getElementById('themeIcon');

document.getElementById('themeToggle').addEventListener('click', () => {
    htmlDoc.classList.toggle('dark');
    if(htmlDoc.classList.contains('dark')) {
        themeIcon.textContent = '🌙';
    } else {
        themeIcon.textContent = '☀️';
    }
});

// --- Portfolio Logic ---
function togglePortfolioDropdown() {
    document.getElementById("portfolio-dropdown").classList.toggle("hidden");
}

// Close dropdown when clicking outside
document.addEventListener('click', function(event) {
    const dropdown = document.getElementById('portfolio-dropdown');
    const button = document.getElementById('active-portfolio-label').parentElement;
    if (button && !button.contains(event.target) && dropdown && !dropdown.contains(event.target)) {
        dropdown.classList.add('hidden');
    }
});

async function loadPortfolios() {
    try {
        const res = await fetch(`/api/v1/users/${activeUser.id}/portfolios`);
        const data = await res.json();
        portfolios = data.portfolios;
        
        if(portfolios.length > 0) {
            const savedId = localStorage.getItem("active_portfolio");
            activePortfolio = portfolios.find(p => p.id == savedId) || portfolios[0];
            localStorage.setItem("active_portfolio", activePortfolio.id);
            renderHeaderPortfolio();
            renderPortfolioDropdown();
            
            // Reload active tab
            const tabs = ['dashboard', 'screener', 'watchlist', 'journal', 'profile'];
            for (const t of tabs) {
                const view = document.getElementById(`view-${t}`);
                if (view && !view.classList.contains('hidden')) {
                    if (t === 'dashboard') fetchDashboard();
                    if (t === 'watchlist') fetchWatchlists();
                    if (t === 'journal') fetchJournals();
                    if (t === 'profile') fetchProfile();
                    break;
                }
            }
        }
    } catch (e) {
        console.error("Gagal load portfolio", e);
    }
}

function renderHeaderPortfolio() {
    if(!activePortfolio) return;
    const label = document.getElementById("active-portfolio-label");
    label.textContent = `${activePortfolio.name} - Rp ${activePortfolio.current_balance.toLocaleString('id-ID')}`;
}

function renderPortfolioDropdown() {
    const list = document.getElementById("portfolio-list");
    list.innerHTML = "";
    portfolios.forEach(p => {
        const isAktif = (p.id === activePortfolio.id);
        const cls = isAktif ? "bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white" : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600";
        const a = document.createElement("a");
        a.href = "#";
        a.className = `block px-4 py-2 text-sm ${cls}`;
        a.textContent = p.name;
        a.onclick = (e) => {
            e.preventDefault();
            switchPortfolio(p.id);
        };
        list.appendChild(a);
    });
}

function switchPortfolio(id) {
    activePortfolio = portfolios.find(p => p.id === id);
    localStorage.setItem("active_portfolio", id);
    renderHeaderPortfolio();
    renderPortfolioDropdown();
    togglePortfolioDropdown();
    
    // Reload active tab
    const tabs = ['dashboard', 'screener', 'watchlist', 'journal', 'profile'];
    for (const t of tabs) {
        const view = document.getElementById(`view-${t}`);
        if (view && !view.classList.contains('hidden')) {
            if (t === 'dashboard') fetchDashboard();
            if (t === 'watchlist') fetchWatchlists();
            if (t === 'journal') fetchJournals();
            if (t === 'profile') fetchProfile();
            break;
        }
    }
}

async function promptCreatePortfolio() {
    togglePortfolioDropdown();
    const name = prompt("Masukkan nama Portofolio Baru:");
    if(!name) return;
    const balanceStr = prompt("Masukkan Modal Awal (contoh: 50000000):", "100000000");
    if(!balanceStr) return;
    
    const balance = parseFloat(balanceStr);
    if(isNaN(balance)) return alert("Modal harus berupa angka!");
    
    try {
        const res = await fetch(`/api/v1/users/${activeUser.id}/portfolios`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({name: name, initial_balance: balance})
        });
        if(res.ok) {
            await loadPortfolios();
            const data = await res.json();
            switchPortfolio(data.portfolio.id);
        } else {
            alert("Gagal membuat portofolio.");
        }
    } catch(e) {
        alert(e.message);
    }
}

async function promptTransaction() {
    const type = prompt("Ketik 'deposit' atau 'withdraw':", "deposit");
    if(!type || (type !== 'deposit' && type !== 'withdraw')) return;
    const amountStr = prompt(`Masukkan jumlah uang untuk ${type}:`, "1000000");
    if(!amountStr) return;
    const amount = parseFloat(amountStr);
    if(isNaN(amount)) return alert("Jumlah harus berupa angka!");

    try {
        const res = await fetch(`/api/v1/portfolios/${activePortfolio.id}/transaction`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({type: type, amount: amount})
        });
        if(res.ok) {
            alert("Transaksi berhasil!");
            await loadPortfolios(); // Reload balances
            fetchDashboard();
        } else {
            const data = await res.json();
            alert(data.detail);
        }
    } catch(e) { alert(e.message); }
}

async function promptReset() {
    const confirm = window.confirm("PERINGATAN: Aksi ini akan menghapus semua posisi aktif dan jurnal trading pada portofolio ini, serta mereset saldo kembali ke modal awal. Lanjutkan?");
    if(!confirm) return;

    try {
        const res = await fetch(`/api/v1/portfolios/${activePortfolio.id}/reset`, { method: 'POST' });
        if(res.ok) {
            alert("Portfolio berhasil di-reset!");
            await loadPortfolios();
            fetchDashboard();
        }
    } catch(e) { alert(e.message); }
}

// --- Dashboard / Nav Logic ---
function switchNav(nav) {
    const tabs = ['dashboard', 'screener', 'watchlist', 'journal', 'profile'];
    
    tabs.forEach(t => {
        const btn = document.getElementById(`nav-${t}`);
        const view = document.getElementById(`view-${t}`);
        const mobBtn = document.getElementById(`mob-nav-${t}`);
        if(t === nav) {
            btn.classList.add('border-blue-500', 'text-blue-600', 'dark:text-blue-400');
            btn.classList.remove('border-transparent', 'text-gray-500', 'dark:text-gray-400');
            if(mobBtn) { mobBtn.classList.add('text-blue-600', 'dark:text-blue-400'); mobBtn.classList.remove('text-gray-500', 'dark:text-gray-400'); }
            view.classList.remove('hidden');
        } else {
            btn.classList.remove('border-blue-500', 'text-blue-600', 'dark:text-blue-400');
            btn.classList.add('border-transparent', 'text-gray-500', 'dark:text-gray-400');
            if(mobBtn) { mobBtn.classList.remove('text-blue-600', 'dark:text-blue-400'); mobBtn.classList.add('text-gray-500', 'dark:text-gray-400'); }
            view.classList.add('hidden');
        }
    });

    if(nav === 'dashboard') {
        fetchDashboard();
    } else if(nav === 'watchlist') {
        fetchWatchlists();
    } else if(nav === 'journal') {
        fetchJournals();
    } else if(nav === 'profile') {
        fetchProfile();
    }
}

// --- Search/Filter Logic ---
const searchInput = document.getElementById('searchInput');
if (searchInput) {
    searchInput.addEventListener('keyup', function(e) {
        const keyword = e.target.value.toLowerCase();
        const rows = document.querySelectorAll('.search-row');
        
        rows.forEach(row => {
            const textContent = Array.from(row.querySelectorAll('.search-text'))
                                    .map(el => el.textContent.toLowerCase())
                                    .join(' ');
                                    
            if(textContent.includes(keyword)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });
}

// --- Service Worker Registration ---
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register("/service-worker.js").then((reg) => {
            console.log('Service Worker registered with scope:', reg.scope);
        }).catch((err) => {
            console.error('Service Worker registration failed:', err);
    });
}

// --- Auto-Refresh Logic ---
// Secara otomatis me-refresh data di tab yang sedang aktif setiap 15 detik (background sync)
setInterval(() => {
    if (!activeUser || !activePortfolio) return;
    
    // Periksa view mana yang sedang aktif
    const tabs = ['dashboard', 'watchlist'];
    for (const t of tabs) {
        const view = document.getElementById(`view-${t}`);
        if (view && !view.classList.contains('hidden')) {
            if (t === 'dashboard' && typeof fetchDashboard === 'function') fetchDashboard(true);
            if (t === 'watchlist' && typeof fetchWatchlists === 'function') fetchWatchlists(true);
            break;
        }
    }
}, 15000); // 15 detik
