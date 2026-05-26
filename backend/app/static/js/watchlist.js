async function fetchWatchlists(silent = false) {
    if(!activePortfolio) return;
    try {
        const res = await fetch(`/api/v1/portfolios/${activePortfolio.id}/watchlists`);
        const data = await res.json();
        if(data.status === 'success') {
            renderWatchlists(data.watchlists);
        }
    } catch(e) {
        console.error("Gagal memuat watchlist", e);
    }
}

function renderWatchlists(watchlists) {
    const tbody = document.getElementById('watchlistTable');
    tbody.innerHTML = '';
    if(!watchlists || watchlists.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-gray-500">Watchlist Anda kosong.</td></tr>';
        return;
    }

    watchlists.forEach(w => {
        const tr = document.createElement('tr');
        tr.className = "hover:bg-gray-50 dark:hover:bg-gray-800/50 transition";
        
        const isSiapSergap = w.distance_to_entry_pct <= 2;
        const statusBadge = isSiapSergap 
            ? `<span class="inline-block px-3 py-1 rounded-full text-xs font-bold bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 border border-green-200 dark:border-green-800 animate-bounce">Siap Sergap!</span>`
            : `<span class="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300 border border-gray-200 dark:border-gray-700">Pantau</span>`;

        const distanceColor = w.distance_to_entry_pct <= 2 ? 'text-green-600 dark:text-green-400 font-bold' : 'text-gray-600 dark:text-gray-400';
        
        tr.innerHTML = `
            <td class="p-3 font-bold text-blue-600 dark:text-blue-400">${w.ticker}</td>
            <td class="p-3 font-medium">${w.ai_recom_price || '-'}</td>
            <td class="p-3 font-semibold">Rp ${w.live_price ? w.live_price.toLocaleString('id-ID') : '-'}</td>
            <td class="p-3 ${distanceColor}">${w.distance_to_entry_pct}%</td>
            <td class="p-3 text-center">${statusBadge}</td>
            <td class="p-3 text-center">
                <div class="flex justify-center gap-2">
                    <button onclick="triggerWatchlistBuy('${w.ticker}', '${w.ai_recom_price}', ${w.live_price})" class="text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded font-medium transition shadow-sm">🛒 BUY</button>
                    <button onclick="triggerWatchlistDelete('${w.ticker}')" class="text-xs bg-red-100 hover:bg-red-200 text-red-600 dark:bg-red-900/20 dark:hover:bg-red-900/40 dark:text-red-400 px-3 py-1 rounded font-medium transition">🗑️ Delete</button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function triggerWatchlistBuy(ticker, buyArea, livePrice) {
    selectedStockData = {
        ticker: ticker,
        ai_analysis: {
            rekomendasi_buy: buyArea,
            take_profit: 0,
            stop_loss: 0,
            risk_reward_ratio: '-'
        },
        filters: {
            price: {
                value: livePrice || 0
            }
        }
    };
    openBuyModal();
}

async function triggerWatchlistDelete(ticker) {
    if(!activePortfolio) return;
    const confirm = window.confirm(`Apakah Anda yakin ingin menghapus ${ticker} dari watchlist?`);
    if(!confirm) return;

    try {
        const res = await fetch(`/api/v1/portfolios/${activePortfolio.id}/watchlists/${ticker}`, {
            method: 'DELETE'
        });
        if(res.ok) {
            alert(`Removed ${ticker} from watchlist.`);
            fetchWatchlists();
        } else {
            alert("Gagal menghapus dari watchlist.");
        }
    } catch(e) {
        alert("Error: " + e.message);
    }
}

async function addToWatchlist() {
    if(!selectedStockData || !activePortfolio) return;
    const payload = {
        ticker: selectedStockData.ticker,
        ai_recom_price: selectedStockData.ai_analysis?.rekomendasi_buy || ''
    };
    try {
        const res = await fetch(`/api/v1/portfolios/${activePortfolio.id}/watchlist`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if(res.ok) {
            alert('📌 ' + data.message);
        } else {
            alert('❌ ' + data.detail);
        }
        closeActionModal();
    } catch(e) {
        alert('Error: ' + e.message);
    }
}
