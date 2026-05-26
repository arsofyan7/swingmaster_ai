async function fetchJournals() {
    if(!activePortfolio) return;
    try {
        const res = await fetch(`/api/v1/portfolios/${activePortfolio.id}/journals`);
        const data = await res.json();
        if(data.status === 'success') {
            renderJournals(data.journals);
        }
    } catch(e) {
        console.error("Gagal memuat jurnal trading", e);
    }
}

function renderJournals(journals) {
    const tbody = document.getElementById('journalTable');
    tbody.innerHTML = '';
    if(!journals || journals.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="p-4 text-center text-gray-500">Belum ada riwayat transaksi di jurnal.</td></tr>';
        return;
    }

    journals.forEach(j => {
        const tr = document.createElement('tr');
        tr.className = "hover:bg-gray-50 dark:hover:bg-gray-800/50 transition border-b border-gray-100 dark:border-darkborder";
        
        const pnlColor = j.pnl_amount >= 0 ? 'text-green-600 dark:text-green-400 font-bold' : 'text-red-600 dark:text-red-400 font-bold';
        const pnlSign = j.pnl_amount >= 0 ? '+' : '';
        
        const rColor = j.r_multiple >= 0 ? 'text-green-600 dark:text-green-400 font-bold' : 'text-red-600 dark:text-red-400 font-bold';
        const rSign = j.r_multiple >= 0 ? '+' : '';

        let formattedDate = j.close_date;
        try {
            const dateObj = new Date(j.close_date);
            if (!isNaN(dateObj)) {
                formattedDate = dateObj.toLocaleDateString('id-ID', {day: '2-digit', month: 'short', year: 'numeric'}) + ' ' + dateObj.toLocaleTimeString('id-ID', {hour: '2-digit', minute:'2-digit'});
            }
        } catch(err) {}
        
        tr.innerHTML = `
            <td class="p-3 font-bold text-blue-600 dark:text-blue-400">${j.ticker}</td>
            <td class="p-3 text-xs text-gray-500 dark:text-gray-400">${formattedDate}</td>
            <td class="p-3">
                <div class="text-xs text-gray-500 dark:text-gray-400">Beli: Rp ${j.buy_price.toLocaleString('id-ID')}</div>
                <div class="font-medium text-gray-900 dark:text-white">Jual: Rp ${j.sell_price.toLocaleString('id-ID')}</div>
            </td>
            <td class="p-3">${j.total_lot} Lot</td>
            <td class="p-3 ${pnlColor}">
                <div>${pnlSign}Rp ${j.pnl_amount.toLocaleString('id-ID')}</div>
                <div class="text-xs font-semibold">${pnlSign}${j.pnl_percentage.toFixed(2)}%</div>
            </td>
            <td class="p-3 text-center ${rColor}">${rSign}${j.r_multiple}R</td>
            <td class="p-3">
                <div class="text-xs"><span class="inline-block px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-semibold mb-1">${j.tag || 'No Tag'}</span></div>
                <div class="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px]" title="${j.notes || ''}">${j.notes || '-'}</div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function exportJournalCSV() {
    if(!activePortfolio) return;
    window.location.href = `/api/v1/portfolios/${activePortfolio.id}/journals/export`;
}
