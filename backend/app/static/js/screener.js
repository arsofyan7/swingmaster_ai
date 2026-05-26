function switchTab(tab) {
    const btnIndex = document.getElementById('tab-index');
    const btnCustom = document.getElementById('tab-custom');
    const contentIndex = document.getElementById('content-index');
    const contentCustom = document.getElementById('content-custom');

    if(tab === 'index') {
        btnIndex.classList.add('text-blue-600', 'dark:text-blue-400', 'border-blue-600', 'dark:border-blue-400');
        btnIndex.classList.remove('text-gray-500', 'dark:text-gray-400', 'border-transparent');
        
        btnCustom.classList.remove('text-blue-600', 'dark:text-blue-400', 'border-blue-600', 'dark:border-blue-400');
        btnCustom.classList.add('text-gray-500', 'dark:text-gray-400', 'border-transparent');

        contentIndex.classList.remove('hidden');
        contentCustom.classList.add('hidden');
    } else {
        btnCustom.classList.add('text-blue-600', 'dark:text-blue-400', 'border-blue-600', 'dark:border-blue-400');
        btnCustom.classList.remove('text-gray-500', 'dark:text-gray-400', 'border-transparent');
        
        btnIndex.classList.remove('text-blue-600', 'dark:text-blue-400', 'border-blue-600', 'dark:border-blue-400');
        btnIndex.classList.add('text-gray-500', 'dark:text-gray-400', 'border-transparent');

        contentCustom.classList.remove('hidden');
        contentIndex.classList.add('hidden');
    }
}

async function runIndexScreener() {
    const indexName = document.getElementById('indexSelect').value;
    fetchData(`/api/v1/stock/index/${indexName}`, 'GET');
}

async function runCustomScreener() {
    const input = document.getElementById('customTickers').value;
    if(!input.trim()) return alert("Masukkan minimal 1 ticker!");
    
    const tickers = input.split(',').map(t => t.trim().toUpperCase()).filter(t => t);
    fetchData('/api/v1/stock/screen', 'POST', { tickers });
}

async function fetchData(url, method, body = null) {
    // UI States
    document.getElementById('errorState').classList.add('hidden');
    document.getElementById('resultsContainer').classList.remove('hidden');
    
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = `
        <tr class="skeleton-row border-b border-gray-100 dark:border-gray-800">
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-1/2"></div></td>
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-3/4"></div></td>
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-full"></div></td>
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-5/6"></div></td>
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-full"></div></td>
        </tr>
        <tr class="skeleton-row border-b border-gray-100 dark:border-gray-800">
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-3/4"></div></td>
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-1/2"></div></td>
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-5/6"></div></td>
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-full"></div></td>
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-3/4"></div></td>
        </tr>
        <tr class="skeleton-row border-b border-gray-100 dark:border-gray-800">
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-2/3"></div></td>
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-5/6"></div></td>
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-1/2"></div></td>
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-3/4"></div></td>
            <td class="p-4"><div class="skeleton-shimmer h-6 rounded w-full"></div></td>
        </tr>
    `;

    document.getElementById('btnRunIndex').disabled = true;
    document.getElementById('btnRunCustom').disabled = true;
    
    const options = {
        method: method,
        headers: { 'Content-Type': 'application/json' }
    };
    if(body) options.body = JSON.stringify(body);

    try {
        const response = await fetch(url, options);
        const data = await response.json();
        
        if(!response.ok || data.status === 'error') {
            throw new Error(data.message || data.detail || "Terjadi kesalahan pada server");
        }
        
        currentData = data.data;
        renderTable(currentData);
        
        document.getElementById('totalResults').textContent = data.data.length;
        document.getElementById('resultsContainer').classList.remove('hidden');
    } catch (err) {
        document.getElementById('errorMessage').textContent = err.message;
        document.getElementById('errorState').classList.remove('hidden');
    } finally {
        document.getElementById('loadingState')?.classList.add('hidden');
        document.getElementById('btnRunIndex').disabled = false;
        document.getElementById('btnRunCustom').disabled = false;
    }
}

function getBadgeColor(strategi) {
    if(!strategi) return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300';
    const str = strategi.toLowerCase();
    if(str.includes("konfirmasi tren kuat")) return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 border-green-200 dark:border-green-800';
    if(str.includes("akumulasi senyap")) return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800';
    if(str.includes("jebakan euforia")) return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400 border-red-200 dark:border-red-800';
    if(str.includes("wajib dihindari")) return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400 border-red-200 dark:border-red-800';
    return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-700';
}

function renderTable(dataArray) {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';
    
    if(!dataArray || dataArray.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-gray-500">Tidak ada data saham yang lolos filter.</td></tr>';
        return;
    }

    dataArray.forEach(item => {
        const tr = document.createElement('tr');
        tr.className = "hover:bg-gray-50 dark:hover:bg-gray-800/50 transition search-row cursor-pointer";
        tr.onclick = () => openActionMenu(item);
        
        const ai = item.ai_analysis || {};
        const price = item.filters?.price?.value || 0;
        
        tr.innerHTML = `
            <td class="p-4 align-top">
                <div class="font-bold text-blue-600 dark:text-blue-400 text-lg search-text">${item.ticker}</div>
                <div class="text-xs text-gray-500 dark:text-gray-400 search-text">${item.company_name}</div>
            </td>
            <td class="p-4 font-medium align-top">Rp ${price.toLocaleString('id-ID')}</td>
            <td class="p-4 search-text align-top">
                <span class="inline-block px-3 py-1 rounded-full text-xs font-semibold border ${getBadgeColor(ai.matriks_strategi)}">
                    ${ai.matriks_strategi || 'N/A'}
                </span>
            </td>
            <td class="p-4 text-sm text-gray-700 dark:text-gray-300 align-top">
                <div class="mb-1"><span class="font-semibold text-gray-900 dark:text-gray-100">Buy Area:</span> <br> ${ai.rekomendasi_buy || '-'}</div>
                <div class="grid grid-cols-2 gap-2 mt-2">
                    <div><span class="font-semibold text-green-600 dark:text-green-400">TP:</span> Rp ${ai.take_profit ? ai.take_profit.toLocaleString() : '-'}</div>
                    <div><span class="font-semibold text-red-600 dark:text-red-400">SL:</span> Rp ${ai.stop_loss ? ai.stop_loss.toLocaleString() : '-'}</div>
                </div>
                <div class="mt-2"><span class="font-semibold text-indigo-600 dark:text-indigo-400">R/R:</span> ${ai.risk_reward_ratio || '-'}</div>
            </td>
            <td class="p-4 text-sm text-gray-600 dark:text-gray-400 search-text align-top">
                ${ai.alasan_analisis || 'Tidak ada analisis.'}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function sortTable(key) {
    if(!currentData || currentData.length === 0) return;
    
    if(currentSort.key === key) {
        currentSort.asc = !currentSort.asc; // Toggle order
    } else {
        currentSort.key = key;
        currentSort.asc = true; // Default ascending
    }
    
    currentData.sort((a, b) => {
        let valA, valB;
        
        if(key === 'ticker') {
            valA = a.ticker;
            valB = b.ticker;
        } else if(key === 'price') {
            valA = a.filters?.price?.value || 0;
            valB = b.filters?.price?.value || 0;
        } else if(key === 'matriks') {
            valA = a.ai_analysis?.matriks_strategi || '';
            valB = b.ai_analysis?.matriks_strategi || '';
        }
        
        if(valA < valB) return currentSort.asc ? -1 : 1;
        if(valA > valB) return currentSort.asc ? 1 : -1;
        return 0;
    });
    
    renderTable(currentData);
}
